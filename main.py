from collections import deque
import asyncio
from collect_location_data import collect_location_data
from collect_gps_data import collect_gps_data
from point_at_car import point_at_car
from constants import DATA_STORE_TOPICS

HOST = "192.168.100.11"


# Initialize tasks and await for them to end
async def main():
    maxlen = 50
    data_store = {}
    for topic in DATA_STORE_TOPICS:
        data_store[topic] = deque(maxlen=maxlen)
    data_lock = asyncio.Lock()

    remote_handle = asyncio.create_task(
        collect_location_data(HOST, data_store, data_lock)
    )
    gps_handle = asyncio.create_task(collect_gps_data(data_store, data_lock, maxlen))
    point_handle = asyncio.create_task(point_at_car(data_store, data_lock))

    tasks = [remote_handle, gps_handle, point_handle]

    try:
        await asyncio.gather(*tasks)
    except (asyncio.CancelledError, KeyboardInterrupt):
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
