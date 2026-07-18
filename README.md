# Fakro Tuya Local Communication

A bridge for **local** communication with an electric Fakro roof window
controlled via Tuya — no cloud. It polls the device using the Tuya local
protocol (`tinytuya`, version 3.3), publishes its state to MQTT and accepts
commands, so the window shows up in Home Assistant as a native device (via MQTT
Discovery).

```
Fakro window (Tuya, local) ──tinytuya──► fakro_bridge ──MQTT──► Home Assistant
                                             ▲                        │
                                             └──── commands ◄─────────┘
```

## Features

- **Control:** open / close / stop, position `0–100%`, speed (`soft`/`normal`/`quick`), rain protection.
- **Telemetry:** ~25 values (position, rain, current, voltage, counters, errors, service flags...).
- **Resilience:** every Tuya operation runs in a separate process with a hard timeout; the service is restarted automatically when the heartbeat disappears (healthcheck every minute).
- **HA integration:** entities are created automatically via MQTT Discovery.

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
