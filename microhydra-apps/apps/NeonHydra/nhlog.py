"""NEON HYDRA debug log: free memory at every step + full errors.

Written to the SD card (readable on a phone) or to flash if there is no card.
"""

import gc
import os
import sys

try:
    LOG = "/sd/neonhydra_log.txt" if "sd" in os.listdir("/") else "/neonhydra_log.txt"
except Exception:  # noqa: BLE001
    LOG = "/neonhydra_log.txt"


def log(msg, err=None):
    try:
        gc.collect()
        with open(LOG, "a") as f:
            f.write("%s | free %d B\n" % (msg, gc.mem_free()))
            if err is not None:
                sys.print_exception(err, f)
    except Exception:  # noqa: BLE001
        pass


def reset_log():
    try:
        with open(LOG, "w") as f:
            f.write("NEON HYDRA debug log\n")
    except Exception:  # noqa: BLE001
        pass
