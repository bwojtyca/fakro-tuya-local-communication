"""One-off tool: flip the "ghost" entities to disabled in an existing HA.

Home Assistant applies `enabled_by_default` only when an entity is first created
via discovery. Entities that were already created (enabled, showing "unknown"
for data points the device never reports) will not become disabled just by
re-publishing the config with `enabled_by_default: false`.

This tool removes those entities (empty retained config) and immediately
recreates the full discovery, so the ghost entities come back disabled. Only the
ghost entities are deleted — the cover and other real entities are only
re-published, never removed.

Run once after upgrading:  /opt/tuya-env/bin/python tools/disable_ghost_entities.py
"""

import os
import sys
import time

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fakro_config import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS
from discovery.ha_discovery import publish_discovery

# (domain, object_id) of entities for data points the device never reports.
GHOST_ENTITIES = [
    ("sensor", "fakro_window_voltage"),
    ("binary_sensor", "fakro_window_service_flag"),
    ("sensor", "fakro_window_pozikon"),
    ("sensor", "fakro_window_count_up"),
    ("sensor", "fakro_window_count_down"),
    ("sensor", "fakro_window_count_work"),
    ("sensor", "fakro_window_spare"),
    ("sensor", "fakro_window_spare2"),
    ("sensor", "fakro_window_spare3"),
]

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()

# 1. Remove the ghost entities (empty retained payload on their config topic).
for domain, object_id in GHOST_ENTITIES:
    client.publish(f"homeassistant/{domain}/{object_id}/config", "", qos=1, retain=True)

time.sleep(1)

# 2. Recreate the full discovery — ghosts come back with enabled_by_default:false.
publish_discovery(client)

time.sleep(1)
client.loop_stop()
client.disconnect()
print(f"Recreated {len(GHOST_ENTITIES)} ghost entities as disabled-by-default.")
