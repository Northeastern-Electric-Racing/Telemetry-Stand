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

PWM_CHANNEL = 0  # GPIO 12
PWM_CHIP = 0
I2C_BUS = 1

# Frequency range (Hz) and center frequency for neutral stop
MIN_FREQ = 200  # 2100 us pulse
MAX_FREQ = 500  # 900 us pulse

NEUTRAL_FREQ = (MAX_FREQ + MIN_FREQ) / 2

QMC = QMC5883P(SMBus(I2C_BUS))

HOST = "192.168.100.11"
# Set to max frequency to just spin in a circle for calibration
pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=int(MAX_FREQ), chip=PWM_CHIP)


def point_at_car():
    min_x, max_x, min_y, max_y = calibrate_compass(QMC, pwm)
    QMC = QMC5883P(SMBus(I2C_BUS), max_x, min_x, max_y, min_y)
    time.sleep(1)

    # Start a thread to read rssi values and populate a buffer
    rssi_buffer = []

    asyncio.run(collect_rssi_data(HOST, rssi_buffer))

    target_angle = 0.0

    heading_pid = PIDController(
        kp=0.8, ki=0.1, kd=0.0, output_limits=(MIN_FREQ, MAX_FREQ)
    )

    current_heading = point_at_heading(target_angle, pwm, QMC, NEUTRAL_FREQ)

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
        rssi = rssi_buffer[-1]
        if rssi > best_rssi + 0.5:  # hysteresis threshold
            best_rssi = rssi
            target_angle = current_heading
            print(f"New best RSSI: {rssi:.2f} dBm at {target_angle:.1f}°")

        print(
            f"Angle: {current_heading:.1f}°, RSSI: {rssi:.2f}, Control: {control_signal:.2f}"
        )

        time.sleep(dt)
