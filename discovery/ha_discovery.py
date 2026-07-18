"""Publish MQTT Discovery for Home Assistant.

Sends retained entity configs (cover, sensors, binary_sensors, switch, select)
to the broker once, so Home Assistant automatically creates the "Okno dachowe
Fakro" device and all its entities. Run it after changing entity definitions or
after a fresh HA installation.

Entities for data points the device never reports over local polling
(101, 121, 122-124, 182, 184-186) are published as `enabled_by_default: false`
so they exist but stay hidden unless the device ever starts reporting them.
"""

import json
import os
import sys

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fakro_config import (
    DEVICE_ID,
    MQTT_HOST,
    MQTT_PORT,
    MQTT_USER,
    MQTT_PASS,
    BASE_TOPIC,
    BRIDGE_VERSION,
)

BASE = BASE_TOPIC

# If the bridge publishes nothing for this long, entities go "unavailable".
# Complements the availability topic; idle poll interval is 60 s.
EXPIRE_AFTER = 180

DEVICE = {
    "identifiers": [f"fakro_tuya_window_{DEVICE_ID}"],
    "name": "Okno dachowe Fakro",
    "manufacturer": "Fakro / Tuya",
    "model": "Tuya mc window",
    "sw_version": BRIDGE_VERSION,
}

AVAILABILITY = [{"topic": f"{BASE}/availability"}]

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.connect(MQTT_HOST, MQTT_PORT, 60)

# Remove discovery configs for entities that no longer exist, so they do not
# linger as orphaned retained messages (and orphaned entities) in HA.
# Empty retained payload on a .../config topic deletes the entity.
REMOVED_ENTITIES = [
    ("sensor", "fakro_window_raw_dps"),  # replaced by cover json_attributes
]
for domain, object_id in REMOVED_ENTITIES:
    client.publish(f"homeassistant/{domain}/{object_id}/config", "", qos=1, retain=True)


def publish_config(domain, object_id, payload):
    topic = f"homeassistant/{domain}/{object_id}/config"
    payload["device"] = DEVICE
    payload["availability"] = AVAILABILITY
    client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1, retain=True)


def sensor(object_id, name, topic, icon=None, unit=None, category=None,
           device_class=None, state_class=None, expire_after=EXPIRE_AFTER,
           enabled_by_default=None):
    payload = {
        "name": name,
        "unique_id": object_id,
        "state_topic": topic,
    }
    if icon:
        payload["icon"] = icon
    if unit:
        payload["unit_of_measurement"] = unit
    if category:
        payload["entity_category"] = category
    if device_class:
        payload["device_class"] = device_class
    if state_class:
        payload["state_class"] = state_class
    if expire_after is not None:
        payload["expire_after"] = expire_after
    if enabled_by_default is not None:
        payload["enabled_by_default"] = enabled_by_default
    publish_config("sensor", object_id, payload)


def binary_sensor(object_id, name, topic, icon=None, category=None,
                  device_class=None, expire_after=EXPIRE_AFTER,
                  enabled_by_default=None):
    payload = {
        "name": name,
        "unique_id": object_id,
        "state_topic": topic,
        "payload_on": "ON",
        "payload_off": "OFF",
    }
    if icon:
        payload["icon"] = icon
    if category:
        payload["entity_category"] = category
    if device_class:
        payload["device_class"] = device_class
    if expire_after is not None:
        payload["expire_after"] = expire_after
    if enabled_by_default is not None:
        payload["enabled_by_default"] = enabled_by_default
    publish_config("binary_sensor", object_id, payload)


def switch(object_id, name, state_topic, command_topic, icon=None, category=None):
    payload = {
        "name": name,
        "unique_id": object_id,
        "state_topic": state_topic,
        "command_topic": command_topic,
        "payload_on": "ON",
        "payload_off": "OFF",
    }
    if icon:
        payload["icon"] = icon
    if category:
        payload["entity_category"] = category
    publish_config("switch", object_id, payload)


def select(object_id, name, state_topic, command_topic, options, icon=None, category=None):
    payload = {
        "name": name,
        "unique_id": object_id,
        "state_topic": state_topic,
        "command_topic": command_topic,
        "options": options,
    }
    if icon:
        payload["icon"] = icon
    if category:
        payload["entity_category"] = category
    publish_config("select", object_id, payload)


# --- Cover: position + motion state (opening/closing/stopped) ---
# Raw DPS are exposed as attributes of the cover (json_attributes_topic) instead
# of a dedicated sensor, to avoid the 255-char limit on sensor state.
publish_config("cover", "fakro_window", {
    "name": "Okno dachowe",
    "unique_id": "fakro_window_cover",
    "device_class": "window",
    "position_topic": f"{BASE}/position",
    "position_template": "{{ value | int(0) }}",
    "set_position_topic": f"{BASE}/position/set",
    "command_topic": f"{BASE}/set",
    "payload_open": "open",
    "payload_close": "close",
    "payload_stop": "stop",
    "state_topic": f"{BASE}/state",
    "state_open": "open",
    "state_opening": "opening",
    "state_closed": "closed",
    "state_closing": "closing",
    "state_stopped": "stopped",
    "json_attributes_topic": f"{BASE}/raw",
})

sensor(
    "fakro_window_position",
    "Pozycja okna",
    f"{BASE}/position",
    icon="mdi:window-open-variant",
    unit="%",
    state_class="measurement",
)

binary_sensor(
    "fakro_rain_detected",
    "Wykryto deszcz",
    f"{BASE}/rain_state",
    icon="mdi:weather-rainy",
    device_class="moisture",
)

switch(
    "fakro_rain_protection",
    "Ochrona przed deszczem",
    f"{BASE}/rain_use",
    f"{BASE}/rain_use/set",
    icon="mdi:weather-pouring",
)

select(
    "fakro_window_speed",
    "Prędkość okna",
    f"{BASE}/speed",
    f"{BASE}/speed/set",
    ["soft", "normal", "quick"],
    icon="mdi:speedometer",
)

sensor(
    "fakro_window_last_seen",
    "Połączono od",
    f"{BASE}/last_seen",
    icon="mdi:lan-connect",
    device_class="timestamp",
    category="diagnostic",
    expire_after=None,
)

# --- Reported diagnostics (device actually sends these) ---
sensor(
    "fakro_window_control",
    "Ostatnia komenda",
    f"{BASE}/control",
    icon="mdi:gesture-tap-button",
    category="diagnostic",
)

sensor(
    "fakro_window_motor",
    "Stan silnika",
    f"{BASE}/motor",
    icon="mdi:engine",
    category="diagnostic",
)

sensor(
    "fakro_window_current",
    "Pobór prądu / DP181",
    f"{BASE}/current",
    icon="mdi:current-ac",
    state_class="measurement",
    category="diagnostic",
)

sensor(
    "fakro_window_errors",
    "Błędy",
    f"{BASE}/errors",
    icon="mdi:alert-circle",
    category="diagnostic",
)

sensor(
    "fakro_window_load_close",
    "Próg obciążenia zamykania",
    f"{BASE}/load_close",
    icon="mdi:arrow-down-bold-box",
    unit="raw",
    state_class="measurement",
    category="diagnostic",
)

sensor(
    "fakro_window_load_open",
    "Próg obciążenia otwierania",
    f"{BASE}/load_open",
    icon="mdi:arrow-up-bold-box",
    unit="raw",
    state_class="measurement",
    category="diagnostic",
)

sensor(
    "fakro_window_type",
    "Typ urządzenia",
    f"{BASE}/type",
    icon="mdi:identifier",
    category="diagnostic",
)

sensor(
    "fakro_window_noposition",
    "No Position / DP111",
    f"{BASE}/noposition",
    icon="mdi:map-marker-question",
    category="diagnostic",
)

# --- Optional: data points the device does NOT report over local polling ---
# Kept for completeness but disabled by default (would stay "unknown").
sensor(
    "fakro_window_voltage",
    "Napięcie / DP182",
    f"{BASE}/voltage",
    icon="mdi:sine-wave",
    unit="raw",
    state_class="measurement",
    category="diagnostic",
    enabled_by_default=False,
)

binary_sensor(
    "fakro_window_service_flag",
    "Flaga serwisowa",
    f"{BASE}/flagserwis",
    icon="mdi:wrench",
    category="diagnostic",
    enabled_by_default=False,
)

sensor(
    "fakro_window_pozikon",
    "Pozikon / DP121",
    f"{BASE}/pozikon",
    icon="mdi:counter",
    category="diagnostic",
    enabled_by_default=False,
)

sensor(
    "fakro_window_count_up",
    "Licznik otwarć",
    f"{BASE}/cnt_up",
    icon="mdi:counter",
    state_class="total_increasing",
    category="diagnostic",
    enabled_by_default=False,
)

sensor(
    "fakro_window_count_down",
    "Licznik zamknięć",
    f"{BASE}/cnt_down",
    icon="mdi:counter",
    state_class="total_increasing",
    category="diagnostic",
    enabled_by_default=False,
)

sensor(
    "fakro_window_count_work",
    "Licznik pracy",
    f"{BASE}/cnt_work",
    icon="mdi:counter",
    state_class="total_increasing",
    category="diagnostic",
    enabled_by_default=False,
)

sensor(
    "fakro_window_spare",
    "Spare / DP122",
    f"{BASE}/spare",
    icon="mdi:dots-horizontal",
    category="diagnostic",
    enabled_by_default=False,
)

sensor(
    "fakro_window_spare2",
    "Spare 2 / DP123",
    f"{BASE}/spare2",
    icon="mdi:dots-horizontal",
    category="diagnostic",
    enabled_by_default=False,
)

sensor(
    "fakro_window_spare3",
    "Spare 3 / DP124",
    f"{BASE}/spare3",
    icon="mdi:dots-horizontal",
    category="diagnostic",
    enabled_by_default=False,
)

client.disconnect()
print("Final Fakro MQTT discovery published.")
