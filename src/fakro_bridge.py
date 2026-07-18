"""Fakro-Tuya <-> MQTT bridge (persistent / push-based).

Holds a single persistent local connection to the Fakro roof window (Tuya local
protocol, no cloud) and reacts to the device's real-time pushes: whenever a data
point changes, it is published to MQTT immediately. Commands from MQTT
(open/close/stop, position, speed, rain protection) are queued and sent over the
same persistent socket — Tuya allows only one local connection at a time.

Robustness:
  * a keepalive heartbeat keeps the socket alive;
  * on any socket error the connection is torn down and re-established;
  * a slow safety poll re-reads the full status periodically, in case a push was
    missed;
  * an MQTT Last Will marks the device offline if the bridge process dies;
  * an external healthcheck (systemd timer) restarts the service if the MQTT
    heartbeat goes stale — the ultimate backstop.

Because pushes are partial (e.g. just ``{"106": 1}``), we keep a merged view of
all data points and compute the cover motion state from that.
"""

import json
import os
import queue
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
from discovery.ha_discovery import publish_discovery

# MQTT quality of service: 1 = "at least once" (broker acks), so commands and
# state are not silently lost during reconnects.
QOS = 1

# Persistent connection timing.
RECEIVE_TIMEOUT = 1      # seconds to block in receive() before looping
HEARTBEAT_SECONDS = 10   # keepalive interval to hold the socket open
SAFETY_POLL_SECONDS = 60 # periodic full status re-read (catches missed pushes)
RECONNECT_DELAY = 5      # wait before reconnecting after a socket error

# Cover motion state. The motor DP (106) is the authority on whether the window
# is moving now. Direction is resolved from (in order): the position change, the
# physical extremes (at 0 it can only open, at 100 only close), and finally a
# recent MQTT movement command. The command is only trusted for a short window
# and is cleared when movement ends, so it never leaks onto an unrelated move
# triggered from the Tuya app or a remote.
MOVE_COMMAND_TTL_SECONDS = 60
CLOSED_POSITION_THRESHOLD = 2

# Map of Tuya data points to their MQTT sub-topics. Responses (and especially
# pushes) can be partial, so we publish only the keys actually present.
DP_TOPICS = [
    ("2", "control"),
    ("7", "position"),
    ("19", "speed"),
    ("101", "flagserwis"),
    ("102", "type"),
    ("106", "motor"),
    ("111", "noposition"),
    ("120", "errors"),
    ("121", "pozikon"),
    ("122", "spare"),
    ("123", "spare2"),
    ("124", "spare3"),
    ("140", "rain_state"),
    ("141", "rain_use"),
    ("179", "load_close"),
    ("180", "load_open"),
    ("181", "current"),
    ("182", "voltage"),
    ("184", "cnt_up"),
    ("185", "cnt_down"),
    ("186", "cnt_work"),
]

command_queue = queue.Queue()

current_dps = {}            # merged view of all known data points
previous_position = None
last_move_command = None    # {"direction": "opening"|"closing", "ts": float}
last_cover_state = None
was_online = False           # tracks availability transitions (for last_seen)
discovery_published = False  # publish HA discovery once per process


def log(*args):
    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]",
        *args,
        flush=True
    )


# --- MQTT ---

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
# Last Will: if the bridge dies, the broker marks the device offline.
client.will_set(f"{BASE_TOPIC}/availability", "offline", qos=QOS, retain=True)


def pub(topic, value, retain=True):
    if isinstance(value, (dict, list)):
        payload = json.dumps(value, ensure_ascii=False)
    elif isinstance(value, bool):
        payload = "ON" if value else "OFF"
    else:
        payload = str(value)

    client.publish(f"{BASE_TOPIC}/{topic}", payload, qos=QOS, retain=retain)


def note_move_command(direction):
    """Record the direction of the last movement command (for cover state)."""
    global last_move_command
    last_move_command = {"direction": direction, "ts": time.time()}


def clear_move_command():
    """Forget the last movement command (e.g. after an explicit stop)."""
    global last_move_command
    last_move_command = None


def publish_cover_state():
    """Derive and publish the cover motion state from the merged data points.

    The motor DP is the sole authority on whether the window is moving now. A
    position change while the motor is already stopped means the movement
    finished, so we report the resting state instead of a stale opening/closing.
    """
    global previous_position, last_cover_state

    try:
        position = int(current_dps.get("7"))
    except (TypeError, ValueError):
        return  # no position known yet — leave the state untouched

    motor = current_dps.get("106", 0)
    motor_running = str(motor) not in ("0", "", "None", "False")

    now = time.time()
    recent_command = (
        last_move_command is not None
        and now - last_move_command["ts"] < MOVE_COMMAND_TTL_SECONDS
    )
    position_changed = previous_position is not None and position != previous_position

    if motor_running:
        if position_changed:
            state = "opening" if position > previous_position else "closing"
        elif position <= 0:
            # At fully closed it can only open — unless the motor is just
            # braking at the end of a close (transient DP 106 == 2), in which
            # case keep "closing" so it doesn't flicker to "opening".
            state = "closing" if last_cover_state == "closing" else "opening"
        elif position >= 100:
            state = "opening" if last_cover_state == "opening" else "closing"
        elif recent_command:
            state = last_move_command["direction"]
        elif last_cover_state in ("opening", "closing"):
            state = last_cover_state
        else:
            state = "opening"
    else:
        # Movement just ended -> a queued MQTT command no longer applies, so it
        # cannot leak onto a later move triggered outside HA.
        if last_cover_state in ("opening", "closing"):
            clear_move_command()
        state = "closed" if position <= CLOSED_POSITION_THRESHOLD else "open"

    pub("state", state)
    last_cover_state = state
    previous_position = position


def publish_dps(dps):
    """Merge a (possibly partial) dps dict into the state and publish changes."""
    if not dps:
        return

    current_dps.update(dps)

    pub("raw", current_dps)

    # Publish only the data points that arrived in this update.
    for dp, topic in DP_TOPICS:
        if dp in dps:
            pub(topic, dps[dp])

    publish_cover_state()


def publish_alive():
    """Mark the device online and refresh heartbeat / last_seen."""
    global was_online

    if not was_online:
        # ISO 8601 UTC timestamp for the HA "connected since" timestamp sensor.
        pub("last_seen", time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()))
        was_online = True

    pub("availability", "online")
    pub("heartbeat", int(time.time()))
    pub("heartbeat_iso", time.strftime("%Y-%m-%d %H:%M:%S"))


def go_offline():
    global was_online
    was_online = False
    pub("availability", "offline")


# --- MQTT callbacks ---

def on_connect(client, userdata, flags, reason_code, properties):
    global discovery_published

    log("MQTT connected:", reason_code)

    client.subscribe(f"{BASE_TOPIC}/set", qos=QOS)
    client.subscribe(f"{BASE_TOPIC}/position/set", qos=QOS)
    client.subscribe(f"{BASE_TOPIC}/speed/set", qos=QOS)
    client.subscribe(f"{BASE_TOPIC}/rain_use/set", qos=QOS)

    # Publish HA discovery once; guarded so it can never take the bridge down.
    if not discovery_published:
        try:
            publish_discovery(client)
            discovery_published = True
            log("MQTT discovery published")
        except Exception as e:
            log("Discovery publish failed:", repr(e))


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    log("MQTT disconnected:", reason_code)


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode().strip()

    log("COMMAND:", topic, payload)

    if topic == f"{BASE_TOPIC}/set":
        if payload in ["open", "close", "stop"]:
            if payload == "open":
                note_move_command("opening")
            elif payload == "close":
                note_move_command("closing")
            else:
                clear_move_command()
            command_queue.put((2, payload, "SET DP2"))
        else:
            log("IGNORED invalid cover command:", payload)

    elif topic == f"{BASE_TOPIC}/position/set":
        try:
            position = max(0, min(100, int(payload)))
            if previous_position is not None:
                note_move_command(
                    "opening" if position > previous_position else "closing"
                )
            command_queue.put((7, position, "SET DP7"))
        except ValueError:
            log("IGNORED invalid position:", payload)

    elif topic == f"{BASE_TOPIC}/speed/set":
        if payload in ["soft", "normal", "quick"]:
            command_queue.put((19, payload, "SET DP19"))
        else:
            log("IGNORED invalid speed:", payload)

    elif topic == f"{BASE_TOPIC}/rain_use/set":
        if payload in ["ON", "true", "1"]:
            command_queue.put((141, True, "SET DP141"))
        elif payload in ["OFF", "false", "0"]:
            command_queue.put((141, False, "SET DP141"))
        else:
            log("IGNORED invalid rain_use:", payload)


# --- Tuya persistent connection ---

def make_device():
    d = tinytuya.Device(
        dev_id=DEVICE_ID,
        address=DEVICE_IP,
        local_key=LOCAL_KEY,
        version=TUYA_VERSION,
    )
    d.set_socketPersistent(True)
    d.set_socketTimeout(RECEIVE_TIMEOUT)
    return d


def drain_commands(device):
    """Send all queued commands over the persistent socket. Returns False on error."""
    while True:
        try:
            dp, value, label = command_queue.get_nowait()
        except queue.Empty:
            return True

        try:
            result = device.set_value(dp, value)
            log(label, "->", result)
            if isinstance(result, dict) and "dps" in result:
                publish_dps(result["dps"])
        except Exception as e:
            log(label, "ERROR:", repr(e))
            # Put the command back so it is retried after reconnect.
            command_queue.put((dp, value, label))
            return False


def tuya_loop():
    device = None
    last_heartbeat = 0.0
    last_poll = 0.0

    while True:
        # (Re)connect if needed.
        if device is None:
            try:
                device = make_device()
                status = device.status()
                if isinstance(status, dict) and "dps" in status:
                    publish_dps(status["dps"])
                    publish_alive()
                    log("Tuya connected (persistent):", json.dumps(status["dps"], ensure_ascii=False))
                else:
                    log("Tuya connect: unexpected status:", status)
                last_heartbeat = time.monotonic()
                last_poll = time.monotonic()
            except Exception as e:
                log("Tuya connect ERROR:", repr(e))
                go_offline()
                device = None
                time.sleep(RECONNECT_DELAY)
                continue

        # Send any pending commands first (responsive control).
        if not drain_commands(device):
            device = None
            go_offline()
            time.sleep(RECONNECT_DELAY)
            continue

        # Wait for a push (blocks up to RECEIVE_TIMEOUT).
        try:
            data = device.receive()
        except Exception as e:
            log("Tuya receive ERROR:", repr(e))
            device = None
            go_offline()
            time.sleep(RECONNECT_DELAY)
            continue

        if isinstance(data, dict) and "dps" in data:
            publish_dps(data["dps"])
            publish_alive()

        now = time.monotonic()

        # Keepalive to hold the socket open.
        if now - last_heartbeat > HEARTBEAT_SECONDS:
            try:
                device.heartbeat()
            except Exception as e:
                log("Tuya heartbeat ERROR:", repr(e))
                device = None
                go_offline()
                time.sleep(RECONNECT_DELAY)
                continue
            last_heartbeat = now

        # Safety poll: re-read the full status in case a push was missed.
        if now - last_poll > SAFETY_POLL_SECONDS:
            try:
                status = device.status()
                if isinstance(status, dict) and "dps" in status:
                    publish_dps(status["dps"])
                    publish_alive()
            except Exception as e:
                log("Tuya poll ERROR:", repr(e))
                device = None
                go_offline()
                time.sleep(RECONNECT_DELAY)
                continue
            last_poll = now


# --- Main ---

client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

log("Starting Fakro bridge (persistent/push)...")

client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()

try:
    tuya_loop()
except KeyboardInterrupt:
    log("Stopping bridge...")
    go_offline()
    client.loop_stop()
    client.disconnect()
