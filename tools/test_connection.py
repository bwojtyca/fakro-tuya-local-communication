"""Developer tool: minimal connection test for the Tuya device.

Opens a local connection and prints a single status — the fastest way to check
whether DEVICE_IP / LOCAL_KEY / DEVICE_ID are correct.
"""

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

print("STATUS:")
print(d.status())
