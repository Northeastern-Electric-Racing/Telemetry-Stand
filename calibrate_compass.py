from smbus2 import SMBus
from qmc5883p import QMC5883P
import time
import math
from rpi_hardware_pwm import HardwarePWM

PWM_CHANNEL = 0  # GPIO 12
PWM_CHIP = 0
I2C_BUS = 1
TARGET_HEADING = 0

DISTANCE_AT_MAX_SPEED = 0.150 # Degrees per microsecond at max speed
GEAR_RATIO = 2.3

ROTATION_PER_SECOND = 1000000 / (DISTANCE_AT_MAX_SPEED * GEAR_RATIO)

AMOUNT_TO_ROTATE = 360 * 2

TIME_TO_ROTATE = AMOUNT_TO_ROTATE / ROTATION_PER_SECOND

# Frequency range (Hz) and center frequency for neutral stop
min_freq = 200  # 2100 us pulse
max_freq = 500  # 900 us pulse

QMC5883P = QMC5883P(SMBus(I2C_BUS))

min_x, max_x = 32768, -32768
min_y, max_y = 32768, -32768

neutral_freq = (max_freq + min_freq) / 2
# Set to max frequency to just spin in a circle
pwm = HardwarePWM(pwm_channel=PWM_CHANNEL, hz=int(max_freq), chip=PWM_CHIP)
pwm.start(50)

time_elapsed = 0

while time_elapsed < TIME_TO_ROTATE:
    x_gauss, y_gauss, z_gauss = QMC5883P.read_raw()

    print(f"X: {x_gauss}, Y: {y_gauss}, Z: {z_gauss}")

    min_x = min(min_x, x_gauss)
    max_x = max(max_x, x_gauss)
    min_y = min(min_y, y_gauss)
    max_y = max(max_y, y_gauss)


    time_elapsed += 0.2
    time.sleep(0.2)

pwm.stop()

print(f"X min: {min_x}, X max: {max_x}")
print(f"Y min: {min_y}, Y max: {max_y}")
