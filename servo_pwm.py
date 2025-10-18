#!/usr/bin/env python3

import argparse
import time
import sys


def parse_args():
    p = argparse.ArgumentParser(description="Set PWM on a GPIO pin (BCM numbering).")
    p.add_argument(
        "--pin", type=int, default=12, help="BCM pin number to use (default: 12)"
    )
    p.add_argument(
        "--freq", type=float, default=1000.0, help="Frequency in Hz (default: 1000)"
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
    p.add_argument(
        "--hardware",
        type=bool,
        default=True,
        help="Use hardware PWM if available (default: True)",
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

    if (args.freq <= 200):
         print("Error: --freq must be greater than 200 Hz for servo positional")
         sys.exit(2)

    if (args.freq >= 1000):
         print("Error: --freq must be less than 1000 Hz for servo positional")
         sys.exit(2)

    GPIO = None
    rpi_hw = None

    # Auto-detect drivers if requested
    if args.hardware:
        try:
            from rpi_hardware_pwm import HardwarePWM as _HardwarePWM

            rpi_hw = _HardwarePWM
        except Exception:
            rpi_hw = None
    else:
        try:
            import RPi.GPIO as _GPIO

            GPIO = _GPIO
        except Exception:
            GPIO = None

    pwm = None
    try:
        if GPIO != None:
            # Use BCM numbering
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(args.pin, GPIO.OUT)
            pwm = GPIO.PWM(args.pin, args.freq)
            pwm.start(args.duty)

        elif rpi_hw != None:
            # Use rpi-hardware-pwm: map chip + channel to start/stop
            # The library expects (pwm_channel, hz, chip)
            try:
                pwm = rpi_hw(
                    pwm_channel=int(args.pwm_channel),
                    hz=int(args.freq),
                    chip=int(args.chip),
                )
                pwm.start(int(args.duty))
            except Exception as e:
                raise RuntimeError(f"Failed to start rpi-hardware-pwm: {e}")

        start = time.time()
        while True:
            elapsed = time.time() - start
            if args.duration > 0 and elapsed >= args.duration:
                break
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error while running PWM: {e}")
    finally:
        # Stop PWM/cleanup
        if pwm:
            try:
                pwm.stop()
            except Exception:
                pass

        if GPIO != None:
            try:
                GPIO.cleanup()
            except Exception:
                pass

        print("Done")


if __name__ == "__main__":
    main()
