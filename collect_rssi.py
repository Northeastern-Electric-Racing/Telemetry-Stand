import gmqtt
import asyncio
import server_data_pb2
from collections import deque

client = gmqtt.Client("telemetry-stand")
TOPIC = "/Base/HaLow/RSSI"


async def on_message(
    client,
    topic,
    payload,
    qos,
    properties,
    buffer_to_populate: deque,
    rssi_lock: asyncio.Lock,
):
    # Decode Protobuf message
    try:
        rssi_msg = server_data_pb2.ServerData()
        rssi_msg.ParseFromString(payload)

        rssi_value = rssi_msg.value[0]

        print("Received RSSI:", rssi_value)

        # Append to buffer with lock
        async with rssi_lock:
            buffer_to_populate.append(rssi_value)
    except Exception as e:
        print(f"Failed to parse message: {e}")
    finally:
        return 0


async def collect_rssi_data(host, buffer_to_populate: deque, rssi_lock: asyncio.Lock):
    client.on_message = lambda c, t, p, q, pr: on_message(
        c, t, p, q, pr, buffer_to_populate, rssi_lock
    )
    client.on_connect = lambda c, flags, rc, properties: print(
        "Connected to MQTT broker"
    )
    client.on_disconnect = lambda c, rc, properties: print(
        "Disconnected from MQTT broker"
    )
    await client.connect(host, 1883)

    client.subscribe(TOPIC, qos=1)

    # Keep the connection alive
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("Disconnecting...")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(collect_rssi_data("192.168.100.11", []))
