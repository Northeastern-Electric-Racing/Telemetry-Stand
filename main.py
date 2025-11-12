from collections import deque
import asyncio
from collect_rssi import collect_rssi_data
from point_at_car import point_at_car

HOST = "192.168.100.11"


# Initialize tasks and await for them to end
async def main():
    rssi_buffer = deque(maxlen=16)
    rssi_lock = asyncio.Lock()

    rssi_handle = asyncio.create_task(collect_rssi_data(HOST, rssi_buffer, rssi_lock))
    point_handle = asyncio.create_task(point_at_car(rssi_buffer, rssi_lock))

    tasks = [rssi_handle, point_handle]

    try:
        await asyncio.gather(*tasks)
    except (asyncio.CancelledError, KeyboardInterrupt):
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
