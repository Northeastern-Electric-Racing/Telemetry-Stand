# Telemetry-Stand

This repository now includes a small PWM controller script `main.py` which can be used on a Raspberry Pi (Pi3) to drive PWM on BCM pin 26 (PWM0).

### Running PWM on a Raspberry Pi

Use sudo to run the script and specify frequency, duty cycle, and duration. Example:

```bash
sudo python3 main.py --pin 26 --freq 1000 --duty 50 --duration 10
```

### Using rpi-hardware-pwm (sysfs hardware PWM)

This project also supports the `rpi-hardware-pwm` library which exposes the Pi's hardware PWM channels via the kernel PWM driver. To use it:

1. Enable the kernel overlay by adding to `/boot/firmware/config.txt`:

```
dtoverlay=pwm-2chan
```

Then reboot. Confirm the kernel module is present: `lsmod | grep pwm` and look for `pwm_bcm2835`.

2. Use Venv

`python -m venv venv`

`source ./venv/bin/activate`

3. Install packages

`./venv/bin/pip3 install -r requirements.txt`

4. Run the script with the `rpi-hw` driver and supply `--chip` and `--pwm-channel` if needed (defaults are chip=0, pwm-channel=0):

```bash
./venv/bin/python3 servo_pwm.py --driver rpi-hw --chip 0 --pwm-channel 0 --freq 1000 --duty 50 --duration 10
```

This uses the library's HardwarePWM API which maps to the platform PWM channels (commonly PWM0 -> GPIO18).

### Configuring I2C

Run `sudo raspi-config`

Then do `Interface Options → I2C → Enable`


