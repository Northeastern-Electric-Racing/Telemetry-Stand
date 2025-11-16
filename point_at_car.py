from qmc5883p import QMC5883P
from smbus2 import SMBus
from rpi_hardware_pwm import HardwarePWM
from calibrate_compass import calibrate_compass
import asyncio
from pid_controller import PIDController
from point_at_heading import point_at_heading
import math
from constants import (
    MAX_FREQ,
    NEUTRAL_FREQ,
    BASE_LONGITUDE,
    BASE_LATITUDE,
    REMOTE_LATITUDE,
    REMOTE_LONGITUDE,
    REMOTE_CONNECTION,
    RSSI,
)
from collections import deque
from data_store import get_latest_value, get_latest_n
import statistics

PWM_CHANNEL = 0  # GPIO 12
PWM_CHIP = 0
I2C_BUS = 1


def bearing_between(lat1, lon1, lat2, lon2):
    """Return initial bearing (degrees) from point1 to point2 (0..360)."""
    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)
    y = math.sin(Δλ) * math.cos(φ2)
    x = math.cos(φ1) * math.sin(φ2) - math.sin(φ1) * math.cos(φ2) * math.cos(Δλ)
    θ = math.atan2(y, x)
    bearing = (math.degrees(θ) + 360.0) % 360.0
    return bearing


def heading_difference(bearing_deg, heading_deg):
    """Return signed smallest difference (degrees) to turn from heading -> bearing.
    Uses a numerically stable atan2(sin,cos) formulation to avoid +/-180 flips.
    Positive means turn clockwise (to the right), negative means turn counter-clockwise.
    Result is in (-180, 180].
    """
    # Convert to radians and compute wrapped difference via atan2(sin, cos)
    br = math.radians(bearing_deg)
    hr = math.radians(heading_deg)
    d = math.atan2(math.sin(br - hr), math.cos(br - hr))
    return math.degrees(d)


def nearest_equivalent_angle(target_deg: float, reference_deg: float) -> float:
    """Return an equivalent angle to target_deg that is closest to reference_deg.
    This avoids large 360-degree jumps when the heading crosses the -180/180 boundary.
    """
    # shift both into a common range around reference
    diff = (target_deg - reference_deg + 180.0) % 360.0 - 180.0
    return reference_deg + diff


async def probe_rssi_directions(
    pwm,
    qmc,
    data_store: dict[str, deque],
    data_lock: asyncio.Lock,
    center_angle: float,
    max_offset: float = 90.0,
    step: float = 15.0,
    samples_per_angle: int = 5,
    settle_time: float = 0.5,
):
    """Probe outward from center_angle in increasing offsets (0, +step, -step, +2*step, -2*step...) up to max_offset.
    For each candidate angle, move the actuator toward it, wait settle_time, sample recent RSSI values and compute the mean.
    Returns the absolute angle (0..360) with the highest mean RSSI.
    """

    # Generate offset sequence: 0, +s, -s, +2s, -2s, ...
    offsets = [0]
    k = 1
    while k * step <= max_offset:
        offsets.append(k * step)
        offsets.append(-k * step)
        k += 1

    best_angle = center_angle
    best_score = -float("inf")

    for off in offsets:
        candidate = center_angle + off
        # normalize candidate to range (-180,180] near previous best to avoid flips
        candidate = nearest_equivalent_angle(candidate, best_angle)

        # Move toward candidate by commanding the actuator until within tolerance
        # Use a simple bang-bang control to move; rely on point_at_heading to command PWM
        for _ in range(200):
            # read heading and command a moderate control signal toward candidate
            current = point_at_heading(
                pwm, qmc, 0
            )  # read current heading without changing freq
            err = heading_difference(candidate, current)
            if abs(err) <= 3.0:
                break
            # command moderate motion in the needed direction
            ctrl = math.copysign(0.6, err)
            point_at_heading(pwm, qmc, ctrl)
            await asyncio.sleep(0.05)

        # settled near candidate; wait additional settle_time for RSSI to stabilize
        await asyncio.sleep(settle_time)

        # sample recent RSSI values
        vals = await get_latest_n(data_store, data_lock, RSSI, samples_per_angle)
        if not vals:
            score = -float("inf")
        else:
            try:
                score = statistics.mean(vals)
            except Exception:
                score = -float("inf")

        connected = await get_latest_value(data_store, data_lock, REMOTE_CONNECTION)
        if connected:
            best_angle = candidate % 360.0
            return best_angle

        # choose the best
        if score > best_score:
            best_score = score
            # keep the best in a 0..360 normalized form
            best_angle = candidate % 360.0

    return best_angle


async def point_at_car(data_store: dict[str, deque], data_lock: asyncio.Lock):
    last_rssi = -100.0  # initial low value

    # Uncalibrated
    qmc_handle = QMC5883P(SMBus(I2C_BUS))

    # Set to max frequency to just spin in a circle for calibration
    pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=int(MAX_FREQ), chip=PWM_CHIP)

    print("Starting Calibration")

    min_x, max_x, min_y, max_y = await calibrate_compass(qmc_handle, pwm)
    qmc_handle = QMC5883P(SMBus(I2C_BUS), max_x, min_x, max_y, min_y)

    await asyncio.sleep(1)

    target_angle = 0.0

    heading_pid = PIDController(kp=0.5, ki=0.01, kd=0.05)

    pwm.start(50)

    current_heading = point_at_heading(pwm, qmc_handle, NEUTRAL_FREQ)

    print("Starting main control loop...")

    log_index = 0
    dt = 0.01

    try:
        while True:
            # --- PID CONTROL ---
            error = heading_difference(target_angle, current_heading)

            raw_control = -heading_pid.update(error, dt)

            # --- Smooth ramp-down ---
            normalized_error = raw_control / 90.0
            control_signal = math.tanh(
                normalized_error * 1.5
            )  # smooth nonlinear compression

            # Deadband to avoid jitter near target
            if abs(error) < 2:
                control_signal = 0.0

            try:
                current_heading = point_at_heading(pwm, qmc_handle, control_signal)
            except Exception as e:
                print("Failed to get current heading: ", e)

            # get_latest_value already acquires the lock internally; do not
            # hold the shared lock while calling it (would deadlock).
            rssi = await get_latest_value(data_store, data_lock, RSSI)

            remote_latitude = await get_latest_value(
                data_store, data_lock, REMOTE_LATITUDE
            )
            remote_longitude = await get_latest_value(
                data_store, data_lock, REMOTE_LONGITUDE
            )
            base_latitude = await get_latest_value(data_store, data_lock, BASE_LATITUDE)
            base_longitude = await get_latest_value(
                data_store, data_lock, BASE_LONGITUDE
            )

            # If a remote connection flag is reported, lock onto that signal
            # and hold the target pointing to the remote until the flag goes false.
            remote_conn = await get_latest_value(
                data_store, data_lock, REMOTE_CONNECTION
            )

            if not remote_conn:
                try:
                    target_angle = await probe_rssi_directions(
                        pwm, qmc_handle, data_store, data_lock, current_heading
                    )
                except Exception as e:
                    print("Error encountered while probing rssi: ", e)
                finally:
                    continue

            if (
                remote_latitude is not None
                and remote_longitude is not None
                and base_latitude is not None
                and base_longitude is not None
            ):
                bearing = bearing_between(
                    base_latitude,
                    base_longitude,
                    remote_latitude,
                    remote_longitude,
                )

                target_angle = nearest_equivalent_angle(bearing, target_angle)

            if log_index % 50 == 0:
                print(
                    f"Angle: {current_heading:.1f}°, target: {target_angle}, Error: {error:.2f} Control: {control_signal:.2f} rssi: {last_rssi:.2f} {base_latitude}, {base_longitude} {remote_latitude} {remote_longitude}"
                )

            if rssi is not None:
                last_rssi = rssi

            log_index += 1

            await asyncio.sleep(dt)
    except KeyboardInterrupt:
        pass
    finally:
        print("Exiting Point at Car")
        pwm.stop()
