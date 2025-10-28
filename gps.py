import serial
from pyubx2 import UBXReader

# Configure the serial port for your device.
# For Windows, it might be 'COM3'.
# For Linux/macOS, it might be '/dev/ttyACM0' or '/dev/ttyUSB0'.
# You can find the correct port in your system's device manager or by using tools.
port = "/dev/ttyUBS0"
baudrate = 38400  # Default baud rate for many UBLOX modules

# Create a serial connection object
try:
    with serial.Serial(port, baudrate, timeout=1) as stream:
        print(f"Connected to {port} at {baudrate} baud.")
        # Create a UBXReader instance with the serial stream
        ubr = UBXReader(stream)

        print("Reading UBX messages. Press Ctrl+C to stop.")
        while True:
            # The read() function handles the message parsing
            try:
                (raw_data, parsed_data) = ubr.read()
                if parsed_data:
                    # You can check the message type and process it
                    # For example, look for UBX-NAV-PVT message for navigation data
                    if parsed_data.identity == "NAV-PVT":
                        print(f"NAV-PVT Message Received:")
                        print(f"  Latitude:  {parsed_data.lat / 1e7:.6f} degrees")
                        print(f"  Longitude: {parsed_data.lon / 1e7:.6f} degrees")
                        print(f"  Fix Type:  {parsed_data.fixType}")
                        print("-" * 20)
                    else:
                        # Print other parsed UBX messages for debugging
                        # print(f"Received UBX Message: {parsed_data.identity}")
                        pass
            except Exception as e:
                # Catch parsing errors or timeouts
                pass

except serial.SerialException as e:
    print(f"Serial port error: {e}")
except KeyboardInterrupt:
    print("Streaming stopped by user.")
except FileNotFoundError:
    print(f"Error: Serial port {port} not found. Please check your port name.")
