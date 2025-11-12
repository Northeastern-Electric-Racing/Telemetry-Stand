from qmc5883p import QMC5883P
import math
from rpi_hardware_pwm import HardwarePWM
from point_at_car import MIN_FREQ, MAX_FREQ, NEUTRAL_FREQ


def point_with_control(
    pwm: HardwarePWM,
    qmc5883p_handle: QMC5883P,
    control_signal: float,
) -> float:
    # --- SENSOR READING ---
    x_gauss, y_gauss, _, _ = qmc5883p_handle.read_scaled()

    heading_rad = math.atan2(x_gauss, y_gauss)
    heading_deg = math.degrees(heading_rad)
    if heading_deg < 0:
        heading_deg += 360
    heading_deg %= 360

    # --- Map to frequency range ---
    if control_signal >= 0:
        servo_freq = NEUTRAL_FREQ + (MAX_FREQ - NEUTRAL_FREQ) * control_signal
    else:
        servo_freq = NEUTRAL_FREQ + (NEUTRAL_FREQ - MIN_FREQ) * control_signal

    servo_freq = max(MIN_FREQ, min(MAX_FREQ, servo_freq))

    print(
        f"Heading: {heading_deg:.1f}°, Control: {control_signal:.2f}, Freq: {servo_freq:.1f} Hz"
    )

    pwm.change_frequency(int(servo_freq))

    return heading_deg
