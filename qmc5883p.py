import time
import struct
from mag_base import mag_base

# https://github.com/ChangboBro/QMC5883-3-Axis-magnetic-Sensor-micropython


class QMC5883P(mag_base):
    ADDR = 0x2C

    CONFIG_2GAUSS = 3
    CONFIG_8GAUSS = 2
    CONFIG_12GAUSS = 1
    CONFIG_30GAUSS = 0

    CR2_SOFT_RESET = 0x80

    CR1_MODE_SUSPEND = 0
    CR1_MODE_NORMAL = 1
    CR1_MODE_SINGLE = 2
    CR1_MODE_CONT = 3

    CR1_ODR_10HZ = 0
    CR1_ODR_50HZ = 1 << 2
    CR1_ODR_100HZ = 2 << 2
    CR1_ODR_200HZ = 3 << 2

    CR1_OVR_SMPL8 = 0
    CR1_OVR_SMPL4 = 1 << 4
    CR1_OVR_SMPL2 = 2 << 4
    CR1_OVR_SMPL1 = 3 << 4

    CR1_DOWN_SMPL1 = 0
    CR1_DOWN_SMPL2 = 1 << 6
    CR1_DOWN_SMPL4 = 2 << 6
    CR1_DOWN_SMPL8 = 3 << 6

    x_max = 6341
    x_min = -880

    y_max = 4130
    y_min = -4013

    x_offset = (x_max + x_min) / 2
    y_offset = (y_max + y_min) / 2 

    _lsb_per_G = [1000, 2500, 3750, 15000]

    def __init__(self, i2c, temp_offset=0):
        super().__init__(i2c)
        self.reset()

        self.i2c_writereg(0x29, b"\x06")  # define the sign for syz axis
        self.set_range(0)
        self.i2c_writereg(
            0x0A,
            QMC5883P.CR1_DOWN_SMPL8
            | QMC5883P.CR1_OVR_SMPL8
            | QMC5883P.CR1_ODR_200HZ
            | QMC5883P.CR1_MODE_CONT,
        )
        self.ready()
        self.set_range(0)

    def i2c_readregs(self, regAddr, bytenum):  # int,int,int
        return bytes(self.i2c.read_i2c_block_data(QMC5883P.ADDR, regAddr, bytenum))

    def i2c_writereg(self, regAddr, buff):  # int,int,bytes
        if isinstance(buff, int):
            # Single byte write
            self.i2c.write_byte_data(QMC5883P.ADDR, regAddr, buff)
        elif isinstance(buff, (bytes, bytearray, list)):
            # Multi-byte write
            data = list(buff)  # Must be list of ints
            self.i2c.write_i2c_block_data(QMC5883P.ADDR, regAddr, data)
        else:
            raise TypeError("buff must be int, bytes, bytearray, or list")

    def range_sel(self):
        self.range = QMC5883P.CONFIG_2GAUSS
        status = self.i2c_readregs(0x09, 1)
        if status[0] & 0x02 != 0x00:
            if self.range == 0:
                return
            else:
                self.range -= 1
                self.i2c_writereg(0x0B, bytes([self.range << 2]))

    def _set_cnf(self, val, offset, sz):
        cur = self.i2c_readregs(0x0A, 1)[0]
        cur &= ~(((1 << sz) - 1) << offset)
        cur |= val << offset
        self.i2c_writereg(0x0A, cur)

    def set_samplingrate(self, rate):
        self._set_cnf(rate, 6, 2)

    def set_oversampling(self, val):
        self._set_cnf(val, 4, 2)

    def set_range(self, val):
        self.range = QMC5883P.CONFIG_2GAUSS - val
        self.i2c_writereg(0x0B, self.range << 2)

    def reset(self):
        self.i2c_writereg(0x0B, QMC5883P.CR2_SOFT_RESET)
        time.sleep(0.001)

    def ready(self):
        status = b"\x02"
        i = 0
        while status[0] & 0x01 == 0x00:
            i += 1
            time.sleep(0.001)
            status = self.i2c_readregs(0x09, 1)
            if i > 100:
                raise IOError("request timeout")

    def read_raw(self):
        return struct.unpack("<hhh", self.i2c_readregs(0x01, 6))

    def read_scaled(self):
        x, y, z = self.read_raw()
        scale = QMC5883P._lsb_per_G[self.range]
        x_cal = (x - self.x_offset) / scale
        y_cal = (y - self.y_offset) / scale
        return (x_cal, y_cal, z / scale, 0)
