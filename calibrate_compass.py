from qmc5883p import QMC5883P
import asyncio
import json
from rpi_hardware_pwm import HardwarePWM
import time


async def calibrate_compass(
    qmc5883p_handle: QMC5883P,
    pwm: HardwarePWM,
    distance_at_max_speed=240.0,
    gear_ratio=2.3,
    amount_to_rotate_deg=540,
) -> tuple[int, int, int, int]:
    """Calibrate by spinning the actuator and recording magnetometer min/max for hard-iron offset."""
    output_deg_per_sec = distance_at_max_speed / gear_ratio
    time_to_rotate = amount_to_rotate_deg / output_deg_per_sec

    min_x, max_x = 32768, -32768
    min_y, max_y = 32768, -32768

    pwm.start(50)

    start_time = time.time()
    try:
        while time.time() - start_time < time_to_rotate:
            x_gauss, y_gauss, z_gauss = qmc5883p_handle.read_raw()

            print(f"X: {x_gauss}, Y: {y_gauss}, Z: {z_gauss}")

            min_x = min(min_x, x_gauss)
            max_x = max(max_x, x_gauss)
            min_y = min(min_y, y_gauss)
            max_y = max(max_y, y_gauss)

            await asyncio.sleep(0.01)
    finally:
        pwm.stop()

    calibration = {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y}
    with open("compass_calibration.json", "w") as f:
        json.dump(calibration, f)

    print(f"Wrote calibration data to compass_calibration.json: {calibration}")

    return min_x, max_x, min_y, max_y
