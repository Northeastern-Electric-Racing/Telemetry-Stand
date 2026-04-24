import gps
from constants import BASE_LATITUDE, BASE_LONGITUDE
from collections import deque
import threading
import time


def collect_gps_data(
    data_store: dict[str, deque], data_lock: threading.Lock
):
    print("Beginning GPS Thread")
    session = gps.gps(mode=gps.WATCH_ENABLE)
    try:
        while True:
            read_ret = session.read()

            if read_ret != 0 or not session.valid:
                print("Invalid read")
                continue

            if gps.isfinite(session.fix.latitude) and gps.isfinite(
                session.fix.longitude
            ):
                with data_lock:
                    data_store[BASE_LATITUDE].append(session.fix.latitude)
                    data_store[BASE_LONGITUDE].append(session.fix.longitude)

            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Keyboard Interrupted GPS Thread")
    except Exception as e:
        print("GPS Thread Exception: ", e)
    finally:
        print("Ending GPS Thread")
        session.close()
