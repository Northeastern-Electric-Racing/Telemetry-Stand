import gmqtt
import asyncio
import server_data_pb2

client = gmqtt.Client("telemetry-stand")
TOPIC = "/TPU/HaLow/RSSI"


def on_message(client, topic, payload, qos, properties, buffer_to_populate: list):
    # Decode Protobuf message
    try:
        rssi_msg = server_data_pb2.ServerData()
        rssi_msg.ParseFromString(payload)

        rssi_value = rssi_msg.value[0]

        buffer_to_populate.append(rssi_value)
    except Exception as e:
        print(f"Failed to parse message: {e}")


async def collect_rssi_data(host, buffer_to_populate: list):
    await client.connect(host, 1883)
    client.on_message = lambda c, t, p, q, pr: on_message(
        c, t, p, q, pr, buffer_to_populate
    )

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
