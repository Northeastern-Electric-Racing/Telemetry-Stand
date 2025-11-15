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
    RSSI,
)
from collections import deque

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
    Positive means turn clockwise (to the right), negative means turn counter-clockwise.
    Result in range (-180, 180]."""
    diff = (bearing_deg - heading_deg + 540.0) % 360.0 - 180.0
    return diff


async def get_latest_value(
    data_store: dict[str, deque], data_lock: asyncio.Lock, key: str
):
    async with data_lock:
        dq = data_store.get(key)
        if dq and len(dq) > 0:
            return dq[-1]
        return None


async def point_at_car(data_store: dict[str, deque], data_lock: asyncio.Lock):
    last_rssi = -100.0  # initial low value

    # Uncalibrated
    QMC = QMC5883P(SMBus(I2C_BUS))

    # Set to max frequency to just spin in a circle for calibration
    pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=int(MAX_FREQ), chip=PWM_CHIP)

    print("Starting Calibration")

    min_x, max_x, min_y, max_y = await calibrate_compass(QMC, pwm)
    QMC = QMC5883P(SMBus(I2C_BUS), max_x, min_x, max_y, min_y)

    await asyncio.sleep(1)

    target_angle = 0.0

    heading_pid = PIDController(kp=0.5, ki=0.1, kd=0.0)

    pwm.start(50)

    current_heading = point_at_heading(pwm, QMC, NEUTRAL_FREQ)

    print("Starting main control loop...")

    log_index = 0
    dt = 0.01

    try:
        while True:
            # --- PID CONTROL ---
            error = heading_difference(target_angle, current_heading)

            raw_control = heading_pid.update(error, dt)

            # --- Smooth ramp-down ---
            normalized_error = raw_control / 90.0
            control_signal = math.tanh(
                normalized_error * 1.5
            )  # smooth nonlinear compression

            # Deadband to avoid jitter near target
            if abs(error) < 2:
                control_signal = 0.0

            current_heading = point_at_heading(pwm, QMC, control_signal)

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

            if (
                remote_latitude is not None
                and remote_longitude is not None
                and base_latitude is not None
                and base_longitude is not None
            ):
                target_angle = bearing_between(
                    remote_latitude, remote_longitude, base_latitude, base_longitude
                )
                print(
                    f"Remote lat: {remote_latitude} remote lon: {remote_longitude} base lat: {base_latitude} base lon: {base_longitude}"
                )
            elif rssi is not None and rssi > last_rssi:  # found better signal
                target_angle = current_heading
                print(f"New best RSSI: {rssi:.2f} dBm at {target_angle:.1f}°")
            elif (
                rssi is not None and rssi < last_rssi - 5
            ):  # signal dropped significantly
                # Go the other direction
                direction = (target_angle - current_heading + 360) % 360
                if direction < 180:
                    target_angle = (current_heading - 90) % 360
                else:
                    target_angle = (current_heading + 90) % 360
                print(
                    f"RSSI dropped to {rssi:.2f} dBm, changing target to {target_angle:.1f}°"
                )

            if log_index % 50 == 0:
                print(
                    f"Angle: {current_heading:.1f}°, Error: {error:.2f} Control: {control_signal:.2f} rssi: {last_rssi:.2f} {base_latitude}, {base_longitude}"
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
