"""Most Fakro-Tuya <-> MQTT.

Łączy się lokalnie z oknem dachowym Fakro sterowanym przez Tuya (protokół
lokalny, bez chmury), cyklicznie odpytuje jego status i publikuje wartości na
brokerze MQTT. Przyjmuje też komendy z MQTT (otwórz/zamknij/stop, pozycja,
prędkość, ochrona przed deszczem) i przekazuje je do urządzenia.

Każda operacja Tuya jest wykonywana w osobnym procesie z twardym timeoutem —
biblioteka tinytuya potrafi się zawiesić na gnieździe, a to izoluje takie
przypadki i chroni pętlę główną przed zablokowaniem.
"""

import json
import os
import sys
import time
import threading
import multiprocessing as mp

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

POLL_IDLE_SECONDS = 60
POLL_AFTER_COMMAND_SECONDS = 3
FAST_POLLS_AFTER_COMMAND = 10
TUYA_OPERATION_TIMEOUT = 12

fast_poll_counter = 0
lock = threading.Lock()
wake_event = threading.Event()


def log(*args):
    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]",
        *args,
        flush=True
    )


def make_device():
    d = tinytuya.Device(
        dev_id=DEVICE_ID,
        address=DEVICE_IP,
        local_key=LOCAL_KEY,
        version=TUYA_VERSION
    )

    d.set_socketPersistent(False)
    d.set_socketTimeout(5)

    return d


def tuya_worker(queue, operation, dp=None, value=None):
    try:
        d = make_device()

        if operation == "status":
            result = d.status()

        elif operation == "set":
            result = d.set_value(dp, value)

        else:
            result = {
                "error": f"unknown operation {operation}"
            }

        queue.put(("ok", result))

    except Exception as e:
        queue.put(("error", repr(e)))


def run_tuya(operation, dp=None, value=None, timeout=TUYA_OPERATION_TIMEOUT):
    queue = mp.Queue()

    process = mp.Process(
        target=tuya_worker,
        args=(queue, operation, dp, value)
    )

    process.start()
    process.join(timeout)

    if process.is_alive():
        process.terminate()
        process.join(2)

        if process.is_alive():
            process.kill()
            process.join()

        return False, f"TIMEOUT after {timeout}s"

    if queue.empty():
        return False, "NO RESULT"

    status, result = queue.get()

    if status == "ok":
        return True, result

    return False, result


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)


def pub(topic, value, retain=True):
    if isinstance(value, (dict, list)):
        payload = json.dumps(value, ensure_ascii=False)

    elif isinstance(value, bool):
        payload = "ON" if value else "OFF"

    else:
        payload = str(value)

    client.publish(
        f"{BASE_TOPIC}/{topic}",
        payload,
        retain=retain
    )


def refresh():
    ok, result = run_tuya("status")

    if not ok:
        pub("availability", "offline")
        log("REFRESH ERROR:", result)
        return False

    dps = result.get("dps", {})

    pub("raw", dps)

    pub("control", dps.get("2", "unknown"))
    pub("position", dps.get("7", "unknown"))
    pub("speed", dps.get("19", "unknown"))

    pub("flagserwis", dps.get("101", "unknown"))
    pub("type", dps.get("102", "unknown"))

    pub("motor", dps.get("106", "unknown"))
    pub("noposition", dps.get("111", "unknown"))

    pub("errors", dps.get("120", "unknown"))
    pub("pozikon", dps.get("121", "unknown"))
    pub("spare", dps.get("122", "unknown"))
    pub("spare2", dps.get("123", "unknown"))
    pub("spare3", dps.get("124", "unknown"))

    pub("rain_state", dps.get("140", False))
    pub("rain_use", dps.get("141", False))

    pub("load_close", dps.get("179", "unknown"))
    pub("load_open", dps.get("180", "unknown"))

    pub("current", dps.get("181", "unknown"))
    pub("voltage", dps.get("182", "unknown"))

    pub("cnt_up", dps.get("184", "unknown"))
    pub("cnt_down", dps.get("185", "unknown"))
    pub("cnt_work", dps.get("186", "unknown"))

    pub("availability", "online")
    pub("heartbeat", int(time.time()))
    pub("heartbeat_iso", time.strftime("%Y-%m-%d %H:%M:%S"))

    log("REFRESH:", json.dumps(dps, ensure_ascii=False))

    return True


def mark_fast_poll():
    global fast_poll_counter

    with lock:
        fast_poll_counter = FAST_POLLS_AFTER_COMMAND

    wake_event.set()


def set_dp(dp, value, label):
    ok, result = run_tuya(
        "set",
        dp=dp,
        value=value
    )

    if ok:
        log(label, "RESULT:", result)
        pub("availability", "online")
        mark_fast_poll()

    else:
        log(label, "ERROR:", result)
        pub("availability", "offline")


def on_connect(client, userdata, flags, reason_code, properties):
    log("MQTT connected:", reason_code)

    client.subscribe(f"{BASE_TOPIC}/set")
    client.subscribe(f"{BASE_TOPIC}/position/set")
    client.subscribe(f"{BASE_TOPIC}/speed/set")
    client.subscribe(f"{BASE_TOPIC}/rain_use/set")

    pub("availability", "online")

    mark_fast_poll()


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    log("MQTT disconnected:", reason_code)


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode().strip()

    log("COMMAND:", topic, payload)

    if topic == f"{BASE_TOPIC}/set":

        if payload in ["open", "close", "stop"]:
            set_dp(2, payload, "SET DP2")

        else:
            log("IGNORED invalid cover command:", payload)

    elif topic == f"{BASE_TOPIC}/position/set":

        try:
            position = int(payload)
            position = max(0, min(100, position))

            set_dp(7, position, "SET DP7")

        except ValueError:
            log("IGNORED invalid position:", payload)

    elif topic == f"{BASE_TOPIC}/speed/set":

        if payload in ["soft", "normal", "quick"]:
            set_dp(19, payload, "SET DP19")

        else:
            log("IGNORED invalid speed:", payload)

    elif topic == f"{BASE_TOPIC}/rain_use/set":

        if payload in ["ON", "true", "1"]:
            set_dp(141, True, "SET DP141")

        elif payload in ["OFF", "false", "0"]:
            set_dp(141, False, "SET DP141")

        else:
            log("IGNORED invalid rain_use:", payload)


client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

log("Starting Fakro bridge...")

client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()

try:
    while True:

        with lock:

            if fast_poll_counter > 0:
                fast_poll_counter -= 1
                interval = POLL_AFTER_COMMAND_SECONDS

            else:
                interval = POLL_IDLE_SECONDS

        refresh()

        wake_event.wait(interval)
        wake_event.clear()

except KeyboardInterrupt:

    log("Stopping bridge...")

    pub("availability", "offline")

    client.loop_stop()
    client.disconnect()
