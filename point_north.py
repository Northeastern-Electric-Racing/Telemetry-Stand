from smbus2 import SMBus
from qmc5883p import QMC5883P
import time
import math
from rpi_hardware_pwm import HardwarePWM

import traceback

PWM_CHANNEL = 0  # This uses GPIO 12
PWM_CHIP = 0
I2C_BUS = 1

QMC5883P = QMC5883P(SMBus(I2C_BUS))
prev_freq = None
min_freq = 200
max_freq = 1000

pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=int(min_freq), chip=PWM_CHIP)
pwm.start(50)
while True:

    try:
        x_gauss, y_gauss, z_gauss, extra = QMC5883P.read_scaled()

        print(f"X: {x_gauss}, Y: {y_gauss}, Z: {z_gauss}")

        heading_rad = math.atan2(x_gauss, y_gauss)
        heading_deg = math.degrees(heading_rad)

        if heading_deg < 0:
            heading_deg += 360

        print(f"Heading: {heading_deg}°")

        heading_deg = heading_deg % 360  # 0-360° compass heading


        # Map 0-360° to min_freq-max_freq
        servo_freq = min_freq + (heading_deg / 360.0) * (max_freq - min_freq)

        # if prev_freq is None:
        #     prev_freq = servo_freq
        # servo_freq = prev_freq + 0.1 * (servo_freq - prev_freq)  # smooth transition

        print(f"Setting servo frequency to: {int(servo_freq)} Hz")

        pwm.change_frequency(int(servo_freq))

        time.sleep(0.2)
    except Exception as e:
        traceback.print_exc()
        print(f"Error: {e}")
