from collections import deque
import asyncio
from collect_location_data import collect_location_data
from collect_gps_data import collect_gps_data
from point_at_car import point_at_car
from constants import DATA_STORE_TOPICS
import threading

HOST = "192.168.100.11"


# Initialize tasks and await for them to end
async def main():
    maxlen = 50
    data_store = {}
    for topic in DATA_STORE_TOPICS:
        data_store[topic] = deque(maxlen=maxlen)
    data_lock = threading.Lock()

    gps_thread = threading.Thread(
        target=collect_gps_data, args=(data_store, data_lock), daemon=True
    )
    gps_thread.start()

    remote_handle = asyncio.create_task(
        collect_location_data(HOST, data_store, data_lock)
    )
    # point_handle = asyncio.create_task(point_at_car(data_store, data_lock))

    tasks = [
        remote_handle,
    ]

    try:
        await asyncio.gather(*tasks)
    except (asyncio.CancelledError, KeyboardInterrupt):
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
