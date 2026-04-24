import gmqtt
import asyncio
import server_data_pb2
from collections import deque
from typing import Dict
from constants import (
    RSSI,
    REMOTE_LATITUDE,
    REMOTE_LONGITUDE,
    REMOTE_CONNECTION,
    LAST_CONNECTION_TIME,
)
import time
from data_store import get_latest_value
import threading

client = gmqtt.Client("telemetry-stand")
RSSI_TOPIC = "AP/HaLow/RSSI"
GPS_TOPIC = "TPU/GPS2/Location"

TIMEOUT_DURATION = 5  # seconds


def make_on_message(
    data_store: Dict[str, deque], data_lock: threading.Lock, maxlen: int = 50
):
    def _on_message(client, topic, payload, qos, properties):
        try:
            server_msg = server_data_pb2.ServerData()
            server_msg.ParseFromString(payload)

            # Route values into named deques keeping only the most recent `maxlen` items
            if topic == RSSI_TOPIC:
                # RSSI messages contain a single value
                rssi_value = server_msg.values[0]
                with data_lock:
                    data_store[RSSI].append(rssi_value)

            elif topic == GPS_TOPIC:
                # GPS messages contain latitude, longitude
                latitude = server_msg.values[0]
                longitude = server_msg.values[1]
                with data_lock:
                    data_store[REMOTE_LATITUDE].append(latitude)
                    data_store[REMOTE_LONGITUDE].append(longitude)
                    data_store[REMOTE_CONNECTION].append(True)
                    data_store[LAST_CONNECTION_TIME].append(time.time())

        except Exception as e:
            print(f"Failed to parse message: {e}")

    return _on_message


def make_on_disconnect(host: str):
    def _on_disconnect(client, packet):
        asyncio.create_task(obtain_client_connection(client, host))

    return _on_disconnect


async def obtain_client_connection(client: gmqtt.Client, host: str):
    backoff = 2.0
    while True:
        try:
            await client.connect(host, 1883)
            client.subscribe(RSSI_TOPIC, qos=1)
            client.subscribe(GPS_TOPIC, qos=1)
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"MQTT connection failed: {e}, retrying in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


async def collect_location_data(
    host: str, data_store: Dict[str, deque], data_lock: threading.Lock
):
    client.on_message = make_on_message(data_store, data_lock)
    client.on_connect = lambda c, flags, rc, properties: print(
        "Connected to MQTT broker"
    )
    client.on_disconnect = make_on_disconnect(host)

    print("Attempting to connect to MQTT broker...")

    await obtain_client_connection(client, host)

    # Keep the connection alive until cancelled
    try:
        while True:
            # Check the last connected message and wipe data if missing
            last_connection_time = get_latest_value(
                data_store, data_lock, LAST_CONNECTION_TIME
            )

            if (
                last_connection_time is None
                or time.time() - last_connection_time > TIMEOUT_DURATION
            ):
                print("No data received within ", TIMEOUT_DURATION)
                with data_lock:
                    data_store[REMOTE_LATITUDE].append(None)
                    data_store[REMOTE_LONGITUDE].append(None)
                    data_store[REMOTE_CONNECTION].append(False)

            await asyncio.sleep(TIMEOUT_DURATION)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    # initialize a small rolling buffer (deque) per key to store the most recent 50 values
    maxlen = 50
    data_store = {
        RSSI: deque(maxlen=maxlen),
        REMOTE_LATITUDE: deque(maxlen=maxlen),
        REMOTE_LONGITUDE: deque(maxlen=maxlen),
    }
    data_lock = asyncio.Lock()

    asyncio.run(collect_location_data("192.168.100.11", data_store, data_lock))
