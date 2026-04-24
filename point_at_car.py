from qmc5883p import QMC5883P
from smbus2 import SMBus
from rpi_hardware_pwm import HardwarePWM
from calibrate_compass import calibrate_compass
import asyncio
import threading
from pid_controller import PIDController
from point_at_heading import point_at_heading
import math
from constants import (
    MAX_FREQ,
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
    return (math.degrees(θ) + 360.0) % 360.0


def heading_difference(bearing_deg, heading_deg):
    """Return signed smallest difference (degrees) to turn from heading -> bearing.
    Positive means turn clockwise, negative means counter-clockwise. Result in (-180, 180].
    """
    br = math.radians(bearing_deg)
    hr = math.radians(heading_deg)
    return math.degrees(math.atan2(math.sin(br - hr), math.cos(br - hr)))


def nearest_equivalent_angle(target_deg: float, reference_deg: float) -> float:
    """Return an equivalent angle to target_deg that is closest to reference_deg.
    Avoids large 360-degree jumps when the heading crosses the -180/180 boundary.
    """
    diff = (target_deg - reference_deg + 180.0) % 360.0 - 180.0
    return reference_deg + diff


async def probe_rssi_directions(
    pwm,
    qmc,
    data_store: dict[str, deque],
    data_lock: threading.Lock,
    center_angle: float,
    max_offset: float = 180.0,
    step: float = 90.0,
    samples_per_angle: int = 5,
    settle_time: float = 0.5,
):
    """Probe outward from center_angle in increasing offsets (0, +step, -step, +2*step, -2*step...)
    up to max_offset. Returns the angle (0..360) with the highest mean RSSI.
    """
    print("Probing on RSSI")

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
        candidate = nearest_equivalent_angle(candidate, best_angle)

        for _ in range(10):
            current = point_at_heading(pwm, qmc, 0.0)
            err = heading_difference(candidate, current)
            if abs(err) <= 3.0:
                break
            point_at_heading(pwm, qmc, math.copysign(0.6, err))
            await asyncio.sleep(0.05)

        await asyncio.sleep(settle_time)

        vals = get_latest_n(data_store, data_lock, RSSI, samples_per_angle)
        score = statistics.mean(vals) if vals else -float("inf")

        connected = get_latest_value(data_store, data_lock, REMOTE_CONNECTION)
        if connected:
            print("Now connected, pointing at ", best_angle)
            return candidate % 360.0

        if score > best_score:
            best_score = score
            best_angle = candidate % 360.0

    print("Best Angle: ", best_angle)
    return best_angle


async def point_at_car(data_store: dict[str, deque], data_lock: threading.Lock):
    last_rssi = -100.0

    qmc_handle = QMC5883P(SMBus(I2C_BUS))
    pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=int(MAX_FREQ), chip=PWM_CHIP)

    print("Starting Calibration")
    min_x, max_x, min_y, max_y = await calibrate_compass(qmc_handle, pwm)
    qmc_handle = QMC5883P(SMBus(I2C_BUS), max_x, min_x, max_y, min_y)

    await asyncio.sleep(1)

    target_angle = 0.0
    heading_pid = PIDController(kp=0.5, ki=0.1, kd=0.05)
    log_index = 0
    dt = 0.01

    pwm.start(50)
    current_heading = point_at_heading(pwm, qmc_handle, 0.0)

    print("Starting main control loop...")

    try:
        while True:
            error = heading_difference(target_angle, current_heading)

            raw_control = -heading_pid.update(error, dt)
            normalized_error = raw_control / 90.0
            control_signal = math.tanh(normalized_error * 1.5)

            if abs(error) < 2:
                control_signal = 0.0

            try:
                current_heading = point_at_heading(pwm, qmc_handle, control_signal)
            except Exception as e:
                print("Failed to get current heading: ", e)

            rssi = get_latest_value(data_store, data_lock, RSSI)
            remote_latitude = get_latest_value(data_store, data_lock, REMOTE_LATITUDE)
            remote_longitude = get_latest_value(data_store, data_lock, REMOTE_LONGITUDE)
            base_latitude = get_latest_value(data_store, data_lock, BASE_LATITUDE)
            base_longitude = get_latest_value(data_store, data_lock, BASE_LONGITUDE)
            remote_conn = get_latest_value(data_store, data_lock, REMOTE_CONNECTION)

            if not remote_conn:
                try:
                    target_angle = await probe_rssi_directions(
                        pwm, qmc_handle, data_store, data_lock, current_heading
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print("Error encountered while probing rssi: ", e)
                continue

            if (
                remote_latitude is not None
                and remote_longitude is not None
                and base_latitude is not None
                and base_longitude is not None
            ):
                target_angle = bearing_between(
                    base_latitude, base_longitude, remote_latitude, remote_longitude
                )
                print("bearing", target_angle)

            if log_index % 50 == 0:
                print(
                    f"Angle: {current_heading:.1f}°, target: {target_angle:.1f}°, "
                    f"Error: {error:.2f} Control: {control_signal:.2f} rssi: {last_rssi:.2f} "
                    f"base=({base_latitude}, {base_longitude}) remote=({remote_latitude}, {remote_longitude})"
                )

            if rssi is not None:
                last_rssi = rssi

            log_index += 1
            await asyncio.sleep(dt)
    finally:
        print("Exiting Point at Car")
        pwm.stop()
