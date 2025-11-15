import gmqtt
import asyncio
import server_data_pb2
from collections import deque
from typing import Dict
from constants import RSSI, REMOTE_LATITUDE, REMOTE_LONGITUDE

client = gmqtt.Client("telemetry-stand")
RSSI_TOPIC = "Base/HaLow/RSSI"
GPS_TOPIC = "TPU/GPS/Location"


def make_on_message(
    data_store: Dict[str, deque], data_lock: asyncio.Lock, maxlen: int = 50
):
    async def _on_message(client, topic, payload, qos, properties):
        try:
            server_msg = server_data_pb2.ServerData()
            server_msg.ParseFromString(payload)

            # Route values into named deques keeping only the most recent `maxlen` items
            if topic == RSSI_TOPIC:
                # RSSI messages contain a single value
                rssi_value = server_msg.values[0]
                async with data_lock:
                    # ensure deque exists
                    if RSSI not in data_store:
                        data_store[RSSI] = deque(maxlen=maxlen)
                    data_store[RSSI].append(rssi_value)

            elif topic == GPS_TOPIC:
                # GPS messages contain latitude, longitude
                latitude = server_msg.values[0]
                longitude = server_msg.values[1]
                async with data_lock:
                    if REMOTE_LATITUDE not in data_store:
                        data_store[REMOTE_LATITUDE] = deque(maxlen=maxlen)
                    if REMOTE_LONGITUDE not in data_store:
                        data_store[REMOTE_LONGITUDE] = deque(maxlen=maxlen)
                    data_store[REMOTE_LATITUDE].append(latitude)
                    data_store[REMOTE_LONGITUDE].append(longitude)

        except Exception as e:
            print(f"Failed to parse message: {e}")

    return _on_message


async def obtain_client_connection(client: gmqtt.Client, host: str, backoff: float):
    try:
        await client.connect(host, 1883)
        # subscribe to topics we care about
        client.subscribe(RSSI_TOPIC, qos=1)
        client.subscribe(GPS_TOPIC, qos=1)
    except:
        print(f"Failed to connect to client, retrying in {backoff} seconds")
        await asyncio.sleep(backoff)
        await obtain_client_connection(client, host, min(backoff * 2, 30))


async def collect_location_data(
    host: str, data_store: Dict[str, deque], data_lock: asyncio.Lock
):
    client.on_message = make_on_message(data_store, data_lock)
    client.on_connect = lambda c, flags, rc, properties: print(
        "Connected to MQTT broker"
    )
    client.on_disconnect = lambda c, rc, properties: obtain_client_connection(
        c, host, 2
    )

    print("Attempting to connect to MQTT broker...")
    await obtain_client_connection(client, host, 2)

    # Keep the connection alive until cancelled
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("Disconnecting...")
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
