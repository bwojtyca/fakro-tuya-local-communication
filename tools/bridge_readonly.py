"""Narzędzie deweloperskie: uproszczony most tylko do odczytu.

Wcześniejsza, jednowątkowa wersja mostu — odpytuje urządzenie co 10 sekund i
publikuje podzbiór wartości na MQTT, bez obsługi komend i bez izolacji operacji
w osobnym procesie. Zachowane do szybkiej diagnozy; w produkcji używaj
`src/fakro_bridge.py`.
"""

import json
import os
import sys
import time

import tinytuya
import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fakro_config import (
    DEVICE_ID,
    LOCAL_KEY,
    DEVICE_IP,
    TUYA_VERSION,
    MQTT_HOST,
    MQTT_PORT,
    MQTT_USER,
    MQTT_PASS,
    BASE_TOPIC,
)

d = tinytuya.Device(
    dev_id=DEVICE_ID,
    address=DEVICE_IP,
    local_key=LOCAL_KEY,
    version=TUYA_VERSION
)

d.set_socketPersistent(False)
d.set_socketTimeout(8)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()


def publish(topic, value, retain=True):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    elif isinstance(value, bool):
        value = "ON" if value else "OFF"
    else:
        value = str(value)

    client.publish(f"{BASE_TOPIC}/{topic}", value, retain=retain)


while True:
    try:
        status = d.status()
        dps = status.get("dps", {})

        publish("raw", dps)
        publish("position", dps.get("7", "unknown"))
        publish("speed", dps.get("19", "unknown"))
        publish("rain_state", dps.get("140", False))
        publish("rain_use", dps.get("141", False))
        publish("motor", dps.get("106", "unknown"))
        publish("noposition", dps.get("111", "unknown"))
        publish("errors", dps.get("120", "unknown"))
        publish("current", dps.get("181", "unknown"))

        publish("availability", "online")
        print(json.dumps(dps, indent=2, ensure_ascii=False))

    except Exception as e:
        publish("availability", "offline")
        print("ERROR:", e)

    time.sleep(10)
