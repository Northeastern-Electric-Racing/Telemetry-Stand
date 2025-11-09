from smbus2 import SMBus
from qmc5883p import QMC5883P
import time
import math
from rpi_hardware_pwm import HardwarePWM
from smbus2 import SMBus
from calibrate_compass import calibrate_compass

PWM_CHANNEL = 0  # GPIO 12
PWM_CHIP = 0
I2C_BUS = 1
TARGET_HEADING = 0

# Frequency range (Hz) and center frequency for neutral stop
min_freq = 200  # 2100 us pulse
max_freq = 500  # 900 us pulse

neutral_freq = (max_freq + min_freq) / 2

Kp = 0.8
Ki = 0.1
Kd = 0

prev_error = 0.0
integral = 0.0

QMC = QMC5883P(SMBus(I2C_BUS))
# Set to max frequency to just spin in a circle for calibration
pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=int(max_freq), chip=PWM_CHIP)

min_x, max_x, min_y, max_y = calibrate_compass(QMC, pwm)

time.sleep(1)

QMC = QMC5883P(SMBus(I2C_BUS), max_x, min_x, max_y, min_y)

pwm.change_frequency(int(neutral_freq))
pwm.start(50)

try:
    while True:
        # --- SENSOR READING ---
        x_gauss, y_gauss, z_gauss, extra = QMC.read_scaled()

        heading_rad = math.atan2(x_gauss, y_gauss)
        heading_deg = math.degrees(heading_rad)
        if heading_deg < 0:
            heading_deg += 360
        heading_deg %= 360

        # --- PID CONTROL ---
        error = (heading_deg - TARGET_HEADING + 540) % 360 - 180

        integral += error
        integral = max(min(integral, 100), -100)
        derivative = error - prev_error
        prev_error = error

        # Base PID output
        raw_control = Kp * error + Ki * integral + Kd * derivative

        # --- Smooth ramp-down ---
        normalized_error = raw_control / 90.0
        control_signal = math.tanh(
            normalized_error * 1.5
        )  # smooth nonlinear compression

        # Deadband to avoid jitter near target
        if abs(error) < 2:
            control_signal = 0.0

        # --- Map to frequency range ---
        if control_signal >= 0:
            servo_freq = neutral_freq + (max_freq - neutral_freq) * control_signal
        else:
            servo_freq = neutral_freq + (neutral_freq - min_freq) * control_signal

        servo_freq = max(min_freq, min(max_freq, servo_freq))

        print(
            f"Heading: {heading_deg:.1f}°, Error: {error:.1f}, Control: {control_signal:.2f}, Freq: {servo_freq:.1f} Hz"
        )

        pwm.change_frequency(int(servo_freq))
        time.sleep(0.01)

except KeyboardInterrupt:
    print("Stopping PWM...")
finally:
    pwm.stop()
