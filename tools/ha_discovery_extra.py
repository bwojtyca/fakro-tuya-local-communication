"""Narzędzie deweloperskie: wcześniejsza wersja MQTT Discovery.

Starszy, częściowo dublujący się zestaw encji diagnostycznych z anglojęzycznymi
nazwami. Zachowane jako referencja z etapu reverse-engineeringu. Wersją docelową
jest `discovery/ha_discovery.py` — nie uruchamiaj obu naraz, bo utworzą
nakładające się encje w Home Assistancie.
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
    "name": "Fakro Tuya Window",
    "manufacturer": "Fakro / Tuya",
    "model": "Tuya mc window",
}

availability = [{"topic": f"{BASE}/availability"}]

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.connect(MQTT_HOST, MQTT_PORT, 60)


def cfg(domain, object_id, payload):
    topic = f"homeassistant/{domain}/{object_id}/config"
    payload["device"] = DEVICE
    payload["availability"] = availability
    client.publish(topic, json.dumps(payload), retain=True)


def sensor(object_id, name, state_topic, icon=None, unit=None):
    payload = {
        "name": name,
        "unique_id": object_id,
        "state_topic": state_topic,
    }
    if icon:
        payload["icon"] = icon
    if unit:
        payload["unit_of_measurement"] = unit
    cfg("sensor", object_id, payload)


def binary_sensor(object_id, name, state_topic, icon=None, device_class=None):
    payload = {
        "name": name,
        "unique_id": object_id,
        "state_topic": state_topic,
        "payload_on": "ON",
        "payload_off": "OFF",
    }
    if icon:
        payload["icon"] = icon
    if device_class:
        payload["device_class"] = device_class
    cfg("binary_sensor", object_id, payload)


sensor("fakro_window_control", "Fakro Window Control", f"{BASE}/control", "mdi:gesture-tap-button")
sensor("fakro_window_motor", "Fakro Window Motor", f"{BASE}/motor", "mdi:engine")
sensor("fakro_window_noposition", "Fakro Window No Position", f"{BASE}/noposition", "mdi:map-marker-question")
sensor("fakro_window_errors", "Fakro Window Errors", f"{BASE}/errors", "mdi:alert-circle")

binary_sensor("fakro_window_flagserwis", "Fakro Window Service Flag", f"{BASE}/flagserwis", "mdi:wrench")
sensor("fakro_window_type", "Fakro Window Type", f"{BASE}/type", "mdi:identifier")
sensor("fakro_window_pozikon", "Fakro Window Pozikon", f"{BASE}/pozikon", "mdi:counter")
sensor("fakro_window_spare", "Fakro Window Spare", f"{BASE}/spare", "mdi:dots-horizontal")
sensor("fakro_window_spare2", "Fakro Window Spare 2", f"{BASE}/spare2", "mdi:dots-horizontal")
sensor("fakro_window_spare3", "Fakro Window Spare 3", f"{BASE}/spare3", "mdi:dots-horizontal")

sensor("fakro_window_load_close", "Fakro Window Load Close", f"{BASE}/load_close", "mdi:arrow-down-bold-box", "raw")
sensor("fakro_window_load_open", "Fakro Window Load Open", f"{BASE}/load_open", "mdi:arrow-up-bold-box", "raw")
sensor("fakro_window_voltage", "Fakro Window Voltage", f"{BASE}/voltage", "mdi:sine-wave", "raw")

sensor("fakro_window_cnt_up", "Fakro Window Count Up", f"{BASE}/cnt_up", "mdi:counter")
sensor("fakro_window_cnt_down", "Fakro Window Count Down", f"{BASE}/cnt_down", "mdi:counter")
sensor("fakro_window_cnt_work", "Fakro Window Count Work", f"{BASE}/cnt_work", "mdi:counter")

sensor("fakro_window_raw", "Fakro Window Raw DPS", f"{BASE}/raw", "mdi:code-json")

client.disconnect()
print("Extra discovery published.")
