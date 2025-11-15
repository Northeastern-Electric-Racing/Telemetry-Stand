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
    diff = (bearing_deg - heading_deg + 180.0) % 360.0 - 180.0
    return diff


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

    heading_pid = PIDController(kp=0.8, ki=0.1, kd=0.0)

    pwm.start(50)

    current_heading = point_at_heading(pwm, QMC, NEUTRAL_FREQ)

    print("Starting main control loop...")

    log_index = 0

    try:
        while True:
            dt = 0.01
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

            async with data_lock:
                rssi = data_store[RSSI][-1]
                remote_latitude = data_store[REMOTE_LATITUDE][-1]
                remote_longitude = data_store[REMOTE_LONGITUDE][-1]
                base_latitude = data_store[BASE_LATITUDE][-1]
                base_longitude = data_store[BASE_LONGITUDE][-1]

            if (
                remote_latitude is not None
                and remote_longitude is not None
                and base_latitude is not None
                and base_longitude is not None
            ):
                target_angle = bearing_between(
                    remote_latitude, remote_longitude, base_latitude, base_longitude
                )
            elif rssi is not None and rssi > last_rssi:  # found better signal
                target_angle = current_heading
                print(f"New best RSSI: {rssi:.2f} dBm at {target_angle:.1f}°")
            elif rssi is not None and rssi < last_rssi:  # signal dropped significantly
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
                    f"Angle: {current_heading:.1f}°, Error: {error:.2f} Control: {control_signal:.2f} rssi: {last_rssi:.2f}"
                )

            if rssi is not None:
                last_rssi = rssi

            await asyncio.sleep(dt)
    except KeyboardInterrupt:
        pass
    finally:
        pwm.stop()
