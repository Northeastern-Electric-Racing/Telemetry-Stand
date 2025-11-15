import gps
import asyncio
from constants import BASE_LATITUDE, BASE_LONGITUDE
from collections import deque

session = gps.gps(mode=gps.WATCH_ENABLE)


async def collect_gps_data(
    data_store: dict[str, deque], data_lock: asyncio.Lock, maxlen=50
):
    print("Beginning GPS Task")
    try:
        while True:
            # session.read() is a blocking call; run it in the default executor
            # with a short timeout so this task doesn't block the event loop.
            loop = asyncio.get_running_loop()
            try:
                read_ret = await asyncio.wait_for(
                    loop.run_in_executor(None, session.read), timeout=0.01
                )
            except asyncio.TimeoutError:
                # no data available within 10 ms, try again
                continue

            if read_ret != 0:
                continue
            if not (gps.MODE_SET & session.valid):
                # not useful, probably not a TPV message
                continue

            # print(
            #     "Mode: %s(%d) Time: "
            #     % (
            #         ("Invalid", "NO_FIX", "2D", "3D")[session.fix.mode],
            #         session.fix.mode,
            #     ),
            #     end="",
            # )
            # print time, if we have it
            # if gps.TIME_SET & session.valid:
            #     print(session.fix.time, end="")
            # else:
            #     print("n/a", end="")

            if gps.isfinite(session.fix.latitude) and gps.isfinite(
                session.fix.longitude
            ):
                print(
                    " Lat %.6f Lon %.6f" % (session.fix.latitude, session.fix.longitude)
                )
                async with data_lock:
                    if BASE_LATITUDE not in data_store:
                        data_store[BASE_LATITUDE] = deque(maxlen=maxlen)
                    if BASE_LONGITUDE not in data_store:
                        data_store[BASE_LONGITUDE] = deque(maxlen=maxlen)

                    data_store[BASE_LATITUDE].append(session.fix.latitude)
                    data_store[BASE_LONGITUDE].append(session.fix.longitude)

            await asyncio.sleep(1000)
    except KeyboardInterrupt:
        print("Keyboard Interrupted GPS Task")
        pass
    except Exception as e:
        print("GPS Task Exception: ", e)
    finally:
        print("Ending GPS Task")
        session.close()
