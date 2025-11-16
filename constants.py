# Frequency range (Hz) and center frequency for neutral stop
MIN_FREQ = 200  # 2100 us pulse
MAX_FREQ = 500  # 900 us pulse

NEUTRAL_FREQ = (MAX_FREQ + MIN_FREQ) / 2

BASE_LATITUDE = "base_latitude"
BASE_LONGITUDE = "base_longitude"
REMOTE_LATITUDE = "remote_latitude"
REMOTE_LONGITUDE = "remote_longitude"
RSSI = "rssi"
REMOTE_CONNECTION = "remote_connection"
LAST_CONNECTION_TIME = "last_connection"

DATA_STORE_TOPICS = [
    BASE_LATITUDE,
    BASE_LONGITUDE,
    REMOTE_LATITUDE,
    REMOTE_LONGITUDE,
    RSSI,
    REMOTE_CONNECTION,
    LAST_CONNECTION_TIME,
]
