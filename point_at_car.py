from qmc5883p import QMC5883P
import time
from smbus2 import SMBus
from rpi_hardware_pwm import HardwarePWM
from calibrate_compass import calibrate_compass
from collect_rssi import collect_rssi_data
import asyncio
from pid_controller import PIDController
from point_at_heading import point_at_heading
import math
from servo_config import MAX_FREQ, MIN_FREQ, NEUTRAL_FREQ
from collections import deque

PWM_CHANNEL = 0  # GPIO 12
PWM_CHIP = 0
I2C_BUS = 1


HOST = "192.168.100.11"


async def point_at_car(rssi_buffer: deque, rssi_lock: asyncio.Lock):
    best_rssi = -100.0  # initial low value

    QMC = QMC5883P(SMBus(I2C_BUS))

    # Set to max frequency to just spin in a circle for calibration
    pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=int(MAX_FREQ), chip=PWM_CHIP)

    time.sleep(1)

    min_x, max_x, min_y, max_y = calibrate_compass(QMC, pwm)
    QMC = QMC5883P(SMBus(I2C_BUS), max_x, min_x, max_y, min_y)

    target_angle = 0.0

    heading_pid = PIDController(
        kp=0.8, ki=0.1, kd=0.0, output_limits=(MIN_FREQ, MAX_FREQ)
    )

    current_heading = point_at_heading(pwm, QMC, NEUTRAL_FREQ)

    print("Starting main control loop...")

    while True:
        dt = 0.01
        # --- PID CONTROL ---
        error = (current_heading - target_angle + 540) % 360 - 180

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

        # Check RSSI, maybe retarget if we find improvement
        async with rssi_lock:
            rssi = rssi_buffer[-1] if rssi_buffer else None
        if rssi is not None and rssi > best_rssi + 0.5:  # hysteresis threshold
            best_rssi = rssi
            target_angle = current_heading
            print(f"New best RSSI: {rssi:.2f} dBm at {target_angle:.1f}°")

        print(
            f"Angle: {current_heading:.1f}°, Error: {error:.2f} Control: {control_signal:.2f}"
        )

        await asyncio.sleep(dt)


# Initialize tasks and await for them to end
async def main():
    rssi_buffer = deque(maxlen=16)
    rssi_lock = asyncio.Lock()

    rssi_handle = asyncio.create_task(collect_rssi_data(HOST, rssi_buffer, rssi_lock))
    point_handle = asyncio.create_task(point_at_car(rssi_buffer, rssi_lock))

    tasks = [rssi_handle, point_handle]

    try:
        await asyncio.gather(*tasks)
    except (asyncio.CancelledError, KeyboardInterrupt):
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
