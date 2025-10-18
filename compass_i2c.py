from smbus2 import SMBus
from qmc5883p import QMC5883P
import time

I2C_BUS = 1

QMC5883P = QMC5883P(SMBus(I2C_BUS))

while True:
    x, y, z = QMC5883P.read_raw()
    print(f"X: {x}, Y: {y}, Z: {z}")
    time.sleep(1)
