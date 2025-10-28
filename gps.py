import serial
from pyubx2 import UBXReader

port = "/dev/ttyUSB0"
baudrate = 9600  # try 9600 first if 38400 gives nothing

with serial.Serial(port, baudrate, timeout=2) as stream:
    print(f"Connected to {port} at {baudrate} baud.")
    ubr = UBXReader(stream)

    try:
        while True:
            (raw_data, parsed_data) = ubr.read()
            if parsed_data:
                if parsed_data.identity == "NAV-PVT":
                    print(
                        f"Lat: {parsed_data.lat / 1e7:.6f}, "
                        f"Lon: {parsed_data.lon / 1e7:.6f}, "
                        f"FixType: {parsed_data.fixType}"
                    )
    except KeyboardInterrupt:
        print("\nStopped.")
