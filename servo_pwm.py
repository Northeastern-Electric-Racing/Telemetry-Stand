#!/usr/bin/env python3

import argparse
import time
import sys
from rpi_hardware_pwm import HardwarePWM


max_frequency = 500  # 900 us
min_frequency = 200 # 1 / 0.0021  # 2100 us

def parse_args():
    p = argparse.ArgumentParser(description="Set PWM on a GPIO pin (BCM numbering).")
    p.add_argument(
        "--freq", type=float, default=max_frequency, help="Frequency in Hz (default: 900us)"
    )
    p.add_argument(
        "--duty",
        type=float,
        default=50.0,
        help="Duty cycle percent 0-100 (default: 50)",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Duration in seconds to run PWM (default: 5). Use 0 for indefinite",
    )
    # Options specific to rpi-hardware-pwm: chip/pwm_channel
    p.add_argument(
        "--chip", type=int, default=0, help="PWM chip number (rpi-hardware-pwm)"
    )
    p.add_argument(
        "--pwm-channel",
        type=int,
        default=0,
        help="PWM channel (0 or 1) (rpi-hardware-pwm)",
    )

    return p.parse_args()


def main():
    args = parse_args()

    # Validate values
    if not (0.0 <= args.duty <= 100.0):
        print("Error: --duty must be between 0 and 100")
        sys.exit(2)

    print("min frequency: %.2f Hz" % min_frequency)
    print("max frequency: %.2f Hz" % max_frequency)

    pwm = None
    try:
        pwm = HardwarePWM(
            pwm_channel=int(args.pwm_channel),
            hz=int(args.freq),
            chip=int(args.chip),
        )
        pwm.start(int(args.duty))

        freq = int(args.freq)
        freq_delta = 10

        start = time.time()
        while True:
            elapsed = time.time() - start
            if args.duration > 0 and elapsed >= args.duration:
                break
            freq = freq + freq_delta
            pwm.change_frequency(int(freq))
            print(f"Changed frequency to: {freq} Hz")
            if freq > max_frequency:
                freq_delta = -10
            elif freq < min_frequency:
                freq_delta = 10
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error while running PWM: {e}")
    finally:
        # Stop PWM/cleanup
        pwm.stop()

        print("Done")


if __name__ == "__main__":
    main()
