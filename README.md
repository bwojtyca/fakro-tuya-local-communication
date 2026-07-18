# Fakro Tuya Local Communication

A bridge for **local** communication with an electric Fakro roof window
controlled via Tuya — no cloud. It keeps a persistent local connection to the
device (`tinytuya`, protocol 3.3), reacts to the device's real-time pushes and
publishes state to MQTT, and accepts commands — so the window shows up in Home
Assistant as a native device (via MQTT Discovery) and reflects changes within
about a second, including movements triggered outside HA (Tuya app, remote).

```
Fakro window (Tuya, local) ──tinytuya──► fakro_bridge ──MQTT──► Home Assistant
                                             ▲                        │
                                             └──── commands ◄─────────┘
```

## Features

- **Control:** open / close / stop, position `0–100%`, speed (`soft`/`normal`/`quick`), rain protection.
- **Real-time:** the device pushes data-point changes over a persistent connection; state (position, motor, commands) is reflected in HA within ~1s, including changes made outside HA.
- **Cover motion state:** reports `opening` / `closing` / `open` / `closed`, with direction inferred from the movement command, the position change and the physical extremes.
- **Telemetry:** position, rain, current, load thresholds, last command, motor state, errors, etc.
- **Resilience:** keepalive + automatic reconnect on socket errors; a slow safety poll catches missed pushes; an MQTT Last Will marks the device offline if the bridge dies; a systemd healthcheck restarts the service if the heartbeat goes stale.
- **HA integration:** entities are created automatically via MQTT Discovery (published by the bridge on connect).

Full data-point map of the device: [`docs/dps-map.md`](docs/dps-map.md).

## Repository layout

```
fakro_config.py              # shared configuration (reads environment variables / .env)
.env.example                 # configuration template — copy to .env and fill in
requirements.txt             # dependencies (tinytuya, paho-mqtt)
src/
  fakro_bridge.py            # main service: Tuya <-> MQTT (+ commands)
  fakro_healthcheck.py       # restarts the service when the heartbeat is missing
discovery/
  ha_discovery.py            # publishes MQTT Discovery to Home Assistant
tools/                       # developer / diagnostic scripts
  test_connection.py         # quick device connection test
  read_status.py             # read raw status + refresh DPS
  bridge_readonly.py         # simplified read-only bridge (older)
  ha_discovery_extra.py      # earlier version of discovery (reference)
deploy/
  deploy.sh                  # deploy from a Mac to the LXC container over SSH
  systemd/                   # systemd units (service + healthcheck + timer)
docs/
  dps-map.md                 # Tuya data-point (DPS) map
```

## Configuration

All secrets (Tuya local key, MQTT password, etc.) come from environment
variables — **nothing sensitive is stored in the code or the repository**.

```bash
cp .env.example .env
# fill in .env with the real values (see the comments in the file)
```

The `.env` file is git-ignored. When run under systemd it is loaded as an
`EnvironmentFile`; when run manually, `fakro_config.py` loads it itself from the
project directory.

## Running locally (for testing)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python tools/test_connection.py     # check the connection to the window
python src/fakro_bridge.py          # run the bridge (Ctrl+C to stop)
```

## Deploy to the LXC container (Proxmox)

The deploy runs from a Mac over SSH — it copies the code and `.env`, installs
dependencies, configures systemd and restarts the service. Target location on
the container: `/opt/fakro-bridge`, Python environment: `/opt/tuya-env`.

```bash
./deploy/deploy.sh              # deploy + restart the service
./deploy/deploy.sh --discovery  # force a one-off discovery republish (optional)
```

The bridge publishes MQTT Discovery automatically on every (re)connect, so the
entities always match the running code — `--discovery` is only needed to force a
republish without restarting.

Deploy parameters (container host, directories) are read from the `.env` file
(`FAKRO_DEPLOY_HOST`, `FAKRO_DEPLOY_DIR`, `FAKRO_VENV_DIR`) and can be overridden
ad hoc with an environment variable:

```bash
FAKRO_DEPLOY_HOST=root@192.168.x.x ./deploy/deploy.sh
```

### Useful commands on the container

```bash
systemctl status fakro-bridge           # service state
tail -f /opt/fakro-bridge/logs/fakro_bridge.log   # live logs
systemctl list-timers fakro-healthcheck # next healthcheck
```

## Dependencies

- Python 3.13
- [`tinytuya`](https://github.com/jasonacox/tinytuya) — Tuya local protocol
- [`paho-mqtt`](https://github.com/eclipse/paho.mqtt.python) — MQTT client
