# Tuya data-point map (DPS) — Fakro roof window

Reverse-engineered from the device's local communication (Tuya protocol 3.3).
The "MQTT topic" column is relative to the `fakro/window` base
(the `FAKRO_BASE_TOPIC` variable).

## Control (writable)

| DP  | MQTT topic           | Write (command)             | Values                            | Description |
|-----|----------------------|-----------------------------|-----------------------------------|-------------|
| 2   | `control`            | `fakro/window/set`          | `open` / `close` / `stop`         | Basic window command |
| 7   | `position`           | `fakro/window/position/set` | `0`–`100` (%)                     | Target / current position |
| 19  | `speed`              | `fakro/window/speed/set`    | `soft` / `normal` / `quick`       | Movement speed |
| 141 | `rain_use`           | `fakro/window/rain_use/set` | `ON` / `OFF`                      | Enable rain protection |

## Read — state and sensors

| DP  | MQTT topic     | Description |
|-----|----------------|-------------|
| 140 | `rain_state`   | Rain detected (bool) |
| 106 | `motor`        | Motor state — multi-valued: `0` = stopped, `1`/`2` = running (observed `1` while moving, `2` transiently on stop). Any non-zero is treated as "moving". |
| 111 | `noposition`   | No position / calibrating |
| 120 | `errors`       | Error code |
| 181 | `current`      | Current draw (raw value) |
| 182 | `voltage`      | Voltage (raw value) |
| 179 | `load_close`   | Load threshold when closing |
| 180 | `load_open`    | Load threshold when opening |

## Read — diagnostics and counters

| DP  | MQTT topic   | Description |
|-----|--------------|-------------|
| 101 | `flagserwis` | Service flag |
| 102 | `type`       | Device type |
| 121 | `pozikon`    | Pozikon (counter) |
| 122 | `spare`      | Spare / unknown |
| 123 | `spare2`     | Spare / unknown |
| 124 | `spare3`     | Spare / unknown |
| 184 | `cnt_up`     | Open counter |
| 185 | `cnt_down`   | Close counter |
| 186 | `cnt_work`   | Motor work counter |

## Helper topics (published by the bridge)

| MQTT topic      | Description |
|-----------------|-------------|
| `raw`           | Full raw `dps` dictionary (JSON) |
| `availability`  | `online` / `offline` |
| `heartbeat`     | Unix timestamp of the last refresh — used by the healthcheck |
| `heartbeat_iso` | Human-readable timestamp of the last refresh |
