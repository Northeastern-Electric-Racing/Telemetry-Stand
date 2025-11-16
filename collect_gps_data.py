import gps
from constants import BASE_LATITUDE, BASE_LONGITUDE
from collections import deque
import threading
import time

session = gps.gps(mode=gps.WATCH_ENABLE)


async def collect_gps_data(
    data_store: dict[str, deque], data_lock: threading.Lock, maxlen=50
):
    print("Beginning GPS Thread")
    try:
        while True:
            read_ret = session.read()

            if read_ret != 0 or not session.valid:
                continue
            if not (gps.MODE_SET & session.valid):
                # not useful, probably not a TPV message
                continue

            if gps.isfinite(session.fix.latitude) and gps.isfinite(
                session.fix.longitude
            ):
                print(
                    " Lat %.6f Lon %.6f" % (session.fix.latitude, session.fix.longitude)
                )
                with data_lock:
                    if BASE_LATITUDE not in data_store:
                        data_store[BASE_LATITUDE] = deque(maxlen=maxlen)
                    if BASE_LONGITUDE not in data_store:
                        data_store[BASE_LONGITUDE] = deque(maxlen=maxlen)

                    data_store[BASE_LATITUDE].append(session.fix.latitude)
                    data_store[BASE_LONGITUDE].append(session.fix.longitude)

            await time.sleep(100)
    except KeyboardInterrupt:
        print("Keyboard Interrupted GPS Thread")
        pass
    except Exception as e:
        print("GPS Thread Exception: ", e)
    finally:
        print("Ending GPS Thread")
        session.close()
