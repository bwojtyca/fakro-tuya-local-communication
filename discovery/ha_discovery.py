"""MQTT Discovery for Home Assistant.

Defines all HA entities (cover, sensors, binary_sensors, switch, select) and
publishes them as retained discovery configs, so Home Assistant automatically
creates the "Okno dachowe Fakro" device.

Two ways to use it:
  * The bridge imports `publish_discovery(client)` and calls it on connect, so
    the entities are always in sync with the running code.
  * Run this file directly (or `deploy/deploy.sh --discovery`) to force a
    one-off republish using a standalone MQTT connection.

Data points the device never reports over local polling (101, 121, 122-124,
182, 184-186) have NO entities — they are listed in REMOVED_ENTITIES so their
discovery configs and orphaned state topics get cleared. If the device ever
starts reporting them, add the entities back and drop them from the removal list.
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

# Discovery configs for entities that no longer exist. An empty retained payload
# on a .../config topic deletes the entity, so it does not linger in HA.
REMOVED_ENTITIES = [
    ("sensor", "fakro_window_raw_dps"),        # replaced by cover json_attributes
    # Data points the device never reports over local polling -> no entity.
    ("sensor", "fakro_window_voltage"),        # DP182
    ("binary_sensor", "fakro_window_service_flag"),  # DP101
    ("sensor", "fakro_window_pozikon"),        # DP121
    ("sensor", "fakro_window_count_up"),       # DP184
    ("sensor", "fakro_window_count_down"),     # DP185
    ("sensor", "fakro_window_count_work"),     # DP186
    ("sensor", "fakro_window_spare"),          # DP122
    ("sensor", "fakro_window_spare2"),         # DP123
    ("sensor", "fakro_window_spare3"),         # DP124
]

# Orphaned retained STATE topics to clear (earlier code published "unknown" here
# every poll for the never-reported DPs above).
REMOVED_STATE_TOPICS = [
    "flagserwis", "voltage", "pozikon",
    "spare", "spare2", "spare3",
    "cnt_up", "cnt_down", "cnt_work",
]

# Set by publish_discovery() for the duration of a publish run.
_client = None


def _publish_config(domain, object_id, payload):
    topic = f"homeassistant/{domain}/{object_id}/config"
    payload["device"] = DEVICE
    payload["availability"] = AVAILABILITY
    _client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1, retain=True)


def _sensor(object_id, name, topic, icon=None, unit=None, category=None,
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
    _publish_config("sensor", object_id, payload)


def _binary_sensor(object_id, name, topic, icon=None, category=None,
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
    _publish_config("binary_sensor", object_id, payload)


def _switch(object_id, name, state_topic, command_topic, icon=None, category=None):
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
    _publish_config("switch", object_id, payload)


def _select(object_id, name, state_topic, command_topic, options, icon=None, category=None):
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
    _publish_config("select", object_id, payload)


def publish_discovery(client):
    """Publish all HA discovery configs using the given connected MQTT client."""
    global _client
    _client = client

    # Remove entities that no longer exist (clear orphaned retained configs).
    for domain, object_id in REMOVED_ENTITIES:
        client.publish(f"homeassistant/{domain}/{object_id}/config", "", qos=1, retain=True)

    # Clear orphaned retained state topics for those removed entities.
    for topic in REMOVED_STATE_TOPICS:
        client.publish(f"{BASE}/{topic}", "", qos=1, retain=True)

    # --- Cover: position + motion state (opening/closing/stopped) ---
    # Raw DPS are exposed as attributes of the cover (json_attributes_topic)
    # instead of a dedicated sensor, to avoid the 255-char limit on sensor state.
    _publish_config("cover", "fakro_window", {
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

    _sensor(
        "fakro_window_position",
        "Pozycja okna",
        f"{BASE}/position",
        icon="mdi:window-open-variant",
        unit="%",
        state_class="measurement",
    )

    _binary_sensor(
        "fakro_rain_detected",
        "Wykryto deszcz",
        f"{BASE}/rain_state",
        icon="mdi:weather-rainy",
        device_class="moisture",
    )

    _switch(
        "fakro_rain_protection",
        "Ochrona przed deszczem",
        f"{BASE}/rain_use",
        f"{BASE}/rain_use/set",
        icon="mdi:weather-pouring",
    )

    _select(
        "fakro_window_speed",
        "Prędkość okna",
        f"{BASE}/speed",
        f"{BASE}/speed/set",
        ["soft", "normal", "quick"],
        icon="mdi:speedometer",
    )

    _sensor(
        "fakro_window_last_seen",
        "Połączono od",
        f"{BASE}/last_seen",
        icon="mdi:lan-connect",
        device_class="timestamp",
        category="diagnostic",
        expire_after=None,
    )

    # --- Reported diagnostics (device actually sends these) ---
    _sensor(
        "fakro_window_control",
        "Ostatnia komenda",
        f"{BASE}/control",
        icon="mdi:gesture-tap-button",
        category="diagnostic",
    )

    _sensor(
        "fakro_window_motor",
        "Stan silnika",
        f"{BASE}/motor",
        icon="mdi:engine",
        category="diagnostic",
    )

    _sensor(
        "fakro_window_current",
        "Pobór prądu / DP181",
        f"{BASE}/current",
        icon="mdi:current-ac",
        state_class="measurement",
        category="diagnostic",
    )

    _sensor(
        "fakro_window_errors",
        "Błędy",
        f"{BASE}/errors",
        icon="mdi:alert-circle",
        category="diagnostic",
    )

    _sensor(
        "fakro_window_load_close",
        "Próg obciążenia zamykania",
        f"{BASE}/load_close",
        icon="mdi:arrow-down-bold-box",
        unit="raw",
        state_class="measurement",
        category="diagnostic",
    )

    _sensor(
        "fakro_window_load_open",
        "Próg obciążenia otwierania",
        f"{BASE}/load_open",
        icon="mdi:arrow-up-bold-box",
        unit="raw",
        state_class="measurement",
        category="diagnostic",
    )

    _sensor(
        "fakro_window_type",
        "Typ urządzenia",
        f"{BASE}/type",
        icon="mdi:identifier",
        category="diagnostic",
    )

    _sensor(
        "fakro_window_noposition",
        "No Position / DP111",
        f"{BASE}/noposition",
        icon="mdi:map-marker-question",
        category="diagnostic",
    )

    # Note: data points 101, 121, 122-124, 182, 184-186 are never reported by
    # the device over local polling, so they have no entities here. They are
    # cleared via REMOVED_ENTITIES / REMOVED_STATE_TOPICS above. If the device
    # ever starts reporting them, add the entities back and drop them from the
    # removal lists.


def _main():
    """Standalone entry point: connect, publish once, disconnect."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    publish_discovery(client)
    client.disconnect()
    print("Final Fakro MQTT discovery published.")


if __name__ == "__main__":
    _main()
