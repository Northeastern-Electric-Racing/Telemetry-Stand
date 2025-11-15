from qmc5883p import QMC5883P
import asyncio
from rpi_hardware_pwm import HardwarePWM
import time

async def calibrate_compass(
    qmc5883p_handle: QMC5883P,
    pwm: HardwarePWM,
    distance_at_max_speed=240.0,
    gear_ratio=2.3,
    amount_to_rotate_deg=540,
) -> tuple[int, int, int, int]:
    """
    Calibrates the compass by rotating the sensor and recording min/max values.
    """

    # DISTANCE_AT_MAX_SPEED is the motor speed (deg/sec) and gear ratio = motor_rev / output_rev
    output_deg_per_sec_B = distance_at_max_speed / gear_ratio
    time_to_rotate_B = amount_to_rotate_deg / output_deg_per_sec_B  # seconds

    print("Case B (speed is motor):", time_to_rotate_B, "s")  # -> ~6.903 s

    min_x, max_x = 32768, -32768
    min_y, max_y = 32768, -32768

    # Start PWM to rotate
    pwm.start(50)

    start_time = time.time()
    time_elapsed = 0
    try:
        while time_elapsed < time_to_rotate_B:
            x_gauss, y_gauss, z_gauss = qmc5883p_handle.read_raw()

            print(f"X: {x_gauss}, Y: {y_gauss}, Z: {z_gauss}")

            min_x = min(min_x, x_gauss)
            max_x = max(max_x, x_gauss)
            min_y = min(min_y, y_gauss)
            max_y = max(max_y, y_gauss)

            time_elapsed = time.time() - start_time
            await asyncio.sleep(0.01)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        pwm.stop()

    # Write min/max values to file
    with open("compass_calibration.json", "w") as f:
        text = f'{{"min_x": {min_x}, "max_x": {max_x}, "min_y": {min_y}, "max_y": {max_y}}}\n'
        f.write(text)

        print(f"Wrote calibration data to compass_calibration.json: {text}")

    return min_x, max_x, min_y, max_y
