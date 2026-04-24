from smbus2 import SMBus
from qmc5883p import QMC5883P
import time

I2C_BUS = 1

compass = QMC5883P(SMBus(I2C_BUS))

min_x, max_x = 32768, -32768
min_y, max_y = 32768, -32768

while True:
    x_gauss, y_gauss, z_gauss = compass.read_raw()

    print(f"X: {x_gauss}, Y: {y_gauss}, Z: {z_gauss}")

    min_x = min(min_x, x_gauss)
    max_x = max(max_x, x_gauss)
    min_y = min(min_y, y_gauss)
    max_y = max(max_y, y_gauss)

    print(f"X min: {min_x}, X max: {max_x}")
    print(f"Y min: {min_y}, Y max: {max_y}")

    time.sleep(0.2)
