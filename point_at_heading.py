from qmc5883p import QMC5883P
import math
from rpi_hardware_pwm import HardwarePWM
from constants import MIN_FREQ, MAX_FREQ, NEUTRAL_FREQ


def point_at_heading(
    pwm: HardwarePWM,
    qmc5883p_handle: QMC5883P,
    control_signal: float,
) -> float:
    # --- SENSOR READING ---
    x_gauss, y_gauss, _, _ = qmc5883p_handle.read_scaled()

    heading_deg = math.degrees(math.atan2(x_gauss, y_gauss)) % 360

    # --- Map to frequency range ---
    if control_signal >= 0:
        servo_freq = NEUTRAL_FREQ + (MAX_FREQ - NEUTRAL_FREQ) * control_signal
    else:
        servo_freq = NEUTRAL_FREQ + (NEUTRAL_FREQ - MIN_FREQ) * control_signal

    servo_freq = max(MIN_FREQ, min(MAX_FREQ, servo_freq))
    pwm.change_frequency(int(servo_freq))

    return heading_deg
