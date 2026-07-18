"""Healthcheck for the Fakro-Tuya bridge.

Runs periodically via a systemd timer. Checks whether a fresh `heartbeat`
published by the bridge service has appeared on MQTT. If the heartbeat is older
than `MAX_AGE_SECONDS` (or missing entirely), it restarts the `fakro-bridge`
service.
"""

import os
import sys
import time
import subprocess

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fakro_config import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS, BASE_TOPIC

TOPIC = f"{BASE_TOPIC}/heartbeat"
MAX_AGE_SECONDS = 300

heartbeat = None


def on_connect(client, userdata, flags, reason_code, properties):
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    global heartbeat
    try:
        heartbeat = int(msg.payload.decode().strip())
    except Exception:
        heartbeat = None


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()

time.sleep(5)
client.loop_stop()
client.disconnect()

now = int(time.time())

if heartbeat is None or now - heartbeat > MAX_AGE_SECONDS:
    subprocess.run(["systemctl", "restart", "fakro-bridge"])
