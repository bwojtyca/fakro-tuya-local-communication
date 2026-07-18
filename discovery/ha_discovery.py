"""Publish MQTT Discovery for Home Assistant.

Sends retained entity configs (cover, sensors, binary_sensors, switch, select)
to the broker once, so Home Assistant automatically creates the "Okno dachowe
Fakro" device and all its entities. Run it after changing entity definitions or
after a fresh HA installation.
"""

import json
import os
import sys

import paho.mqtt.client as mqtt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fakro_config import DEVICE_ID, MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS, BASE_TOPIC

BASE = BASE_TOPIC

DEVICE = {
    "identifiers": [f"fakro_tuya_window_{DEVICE_ID}"],
    "name": "Okno dachowe Fakro",
    "manufacturer": "Fakro / Tuya",
    "model": "Tuya mc window",
}

AVAILABILITY = [{"topic": f"{BASE}/availability"}]

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.connect(MQTT_HOST, MQTT_PORT, 60)


def publish_config(domain, object_id, payload):
    topic = f"homeassistant/{domain}/{object_id}/config"
    payload["device"] = DEVICE
    payload["availability"] = AVAILABILITY
    client.publish(topic, json.dumps(payload, ensure_ascii=False), retain=True)


def sensor(object_id, name, topic, icon=None, unit=None, category=None, device_class=None, state_class=None):
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
    publish_config("sensor", object_id, payload)


def binary_sensor(object_id, name, topic, icon=None, category=None, device_class=None):
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


publish_config("cover", "fakro_window", {
    "name": "Okno dachowe",
    "unique_id": "fakro_window_cover",
    "device_class": "window",
    "position_topic": f"{BASE}/position",
    "position_template": "{{ value | int(0) }}",
    "command_topic": f"{BASE}/set",
    "payload_open": "open",
    "payload_close": "close",
    "payload_stop": "stop",
    "set_position_topic": f"{BASE}/position/set",
})

sensor(
    "fakro_window_position",
    "Pozycja okna",
    f"{BASE}/position",
    icon="mdi:window-open-variant",
    unit="%",
    device_class=None,
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
    category="diagnostic",
)

sensor(
    "fakro_window_load_open",
    "Próg obciążenia otwierania",
    f"{BASE}/load_open",
    icon="mdi:arrow-up-bold-box",
    unit="raw",
    category="diagnostic",
)

sensor(
    "fakro_window_voltage",
    "Napięcie / DP182",
    f"{BASE}/voltage",
    icon="mdi:sine-wave",
    unit="raw",
    category="diagnostic",
)

binary_sensor(
    "fakro_window_service_flag",
    "Flaga serwisowa",
    f"{BASE}/flagserwis",
    icon="mdi:wrench",
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

sensor(
    "fakro_window_pozikon",
    "Pozikon / DP121",
    f"{BASE}/pozikon",
    icon="mdi:counter",
    category="diagnostic",
)

sensor(
    "fakro_window_count_up",
    "Licznik otwarć",
    f"{BASE}/cnt_up",
    icon="mdi:counter",
    category="diagnostic",
)

sensor(
    "fakro_window_count_down",
    "Licznik zamknięć",
    f"{BASE}/cnt_down",
    icon="mdi:counter",
    category="diagnostic",
)

sensor(
    "fakro_window_count_work",
    "Licznik pracy",
    f"{BASE}/cnt_work",
    icon="mdi:counter",
    category="diagnostic",
)

sensor(
    "fakro_window_spare",
    "Spare / DP122",
    f"{BASE}/spare",
    icon="mdi:dots-horizontal",
    category="diagnostic",
)

sensor(
    "fakro_window_spare2",
    "Spare 2 / DP123",
    f"{BASE}/spare2",
    icon="mdi:dots-horizontal",
    category="diagnostic",
)

sensor(
    "fakro_window_spare3",
    "Spare 3 / DP124",
    f"{BASE}/spare3",
    icon="mdi:dots-horizontal",
    category="diagnostic",
)

sensor(
    "fakro_window_raw_dps",
    "Raw DPS",
    f"{BASE}/raw",
    icon="mdi:code-json",
    category="diagnostic",
)

client.disconnect()
print("Final Fakro MQTT discovery published.")
