"""Centralna konfiguracja mostu Fakro-Tuya-MQTT.

Wszystkie sekrety i parametry sieciowe pochodzą ze zmiennych środowiskowych,
dzięki czemu nic wrażliwego nie trafia do repozytorium.

Przy uruchomieniu lokalnym (bez systemd) wartości można trzymać w pliku `.env`
w katalogu głównym projektu. Jest on wczytywany automatycznie, ale NIE nadpisuje
zmiennych już obecnych w środowisku — dzięki temu `EnvironmentFile` w systemd ma
pierwszeństwo nad plikiem `.env`.

Wzór wszystkich wymaganych zmiennych znajdziesz w `.env.example`.
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv():
    """Wczytuje `.env` z katalogu projektu bez nadpisywania istniejących zmiennych."""
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
    """Zwraca zmienną środowiskową albo rzuca czytelnym błędem, gdy jej brak."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Brak wymaganej zmiennej środowiskowej: {name}. "
            f"Ustaw ją w środowisku lub w pliku .env (patrz .env.example)."
        )
    return value


_load_dotenv()

# --- Urządzenie Tuya (komunikacja lokalna) ---
DEVICE_ID = _required("FAKRO_DEVICE_ID")
LOCAL_KEY = _required("FAKRO_LOCAL_KEY")
DEVICE_IP = _required("FAKRO_DEVICE_IP")
TUYA_VERSION = float(os.environ.get("FAKRO_TUYA_VERSION", "3.3"))

# --- Broker MQTT ---
MQTT_HOST = _required("FAKRO_MQTT_HOST")
MQTT_PORT = int(os.environ.get("FAKRO_MQTT_PORT", "1883"))
MQTT_USER = _required("FAKRO_MQTT_USER")
MQTT_PASS = _required("FAKRO_MQTT_PASS")

# --- Topiki MQTT ---
BASE_TOPIC = os.environ.get("FAKRO_BASE_TOPIC", "fakro/window")
