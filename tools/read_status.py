"""Developer tool: read the raw status of the Tuya device.

Prints the full status and tries to refresh the known data points (DPS).
Useful for diagnostics and for re-discovering the device's DP map.
"""

import json
import os
import sys

import tinytuya

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fakro_config import DEVICE_ID, LOCAL_KEY, DEVICE_IP, TUYA_VERSION

d = tinytuya.Device(
    dev_id=DEVICE_ID,
    address=DEVICE_IP,
    local_key=LOCAL_KEY,
    version=TUYA_VERSION
)

d.set_socketPersistent(False)
d.set_socketTimeout(8)

print("Raw status:")
status = d.status()
print(json.dumps(status, indent=2, ensure_ascii=False))

print("\nTrying to refresh known DPS:")
try:
    d.updatedps([2, 7, 19, 101, 102, 106, 111, 120, 140, 141, 179, 180, 181, 182, 184, 185, 186])
    refreshed = d.status()
    print(json.dumps(refreshed, indent=2, ensure_ascii=False))
except Exception as e:
    print("updatedps error:", e)
