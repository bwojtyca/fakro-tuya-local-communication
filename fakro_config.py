"""Central configuration for the Fakro-Tuya-MQTT bridge.

All secrets and network parameters come from environment variables, so nothing
sensitive is ever stored in the repository.

When running locally (without systemd) the values can be kept in a `.env` file
in the project root. It is loaded automatically but does NOT override variables
already present in the environment — this way systemd's `EnvironmentFile` takes
precedence over the `.env` file.

See `.env.example` for the full list of required variables.
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv():
    """Load `.env` from the project root without overriding existing variables."""
    env_path = os.path.join(PROJECT_ROOT, ".env")
    if not os.path.isfile(env_path):
        return

    with open(env_path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


def _required(name):
    """Return an environment variable or raise a clear error when it is missing."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Set it in the environment or in a .env file (see .env.example)."
        )
    return value


_load_dotenv()

# --- Tuya device (local communication) ---
DEVICE_ID = _required("FAKRO_DEVICE_ID")
LOCAL_KEY = _required("FAKRO_LOCAL_KEY")
DEVICE_IP = _required("FAKRO_DEVICE_IP")
TUYA_VERSION = float(os.environ.get("FAKRO_TUYA_VERSION", "3.3"))

# --- MQTT broker ---
MQTT_HOST = _required("FAKRO_MQTT_HOST")
MQTT_PORT = int(os.environ.get("FAKRO_MQTT_PORT", "1883"))
MQTT_USER = _required("FAKRO_MQTT_USER")
MQTT_PASS = _required("FAKRO_MQTT_PASS")

# --- MQTT topics ---
BASE_TOPIC = os.environ.get("FAKRO_BASE_TOPIC", "fakro/window")
