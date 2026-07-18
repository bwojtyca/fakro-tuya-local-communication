# Fakro Tuya Local Communication

Most (bridge) do **lokalnej** komunikacji z elektrycznym oknem dachowym Fakro
sterowanym przez Tuya — bez chmury. Odpytuje urządzenie protokołem lokalnym
Tuya (`tinytuya`, wersja 3.3), publikuje jego stan na MQTT i przyjmuje komendy,
dzięki czemu okno pojawia się w Home Assistancie jako natywne urządzenie
(przez MQTT Discovery).

```
Okno Fakro (Tuya, lokalnie) ──tinytuya──► fakro_bridge ──MQTT──► Home Assistant
                                              ▲                        │
                                              └──── komendy ◄──────────┘
```

## Funkcje

- **Sterowanie:** otwórz / zamknij / stop, pozycja `0–100%`, prędkość (`soft`/`normal`/`quick`), ochrona przed deszczem.
- **Telemetria:** ~25 wartości (pozycja, deszcz, prąd, napięcie, liczniki, błędy, flagi serwisowe...).
- **Odporność:** każda operacja Tuya w osobnym procesie z twardym timeoutem; automatyczny restart usługi, gdy zniknie heartbeat (healthcheck co minutę).
- **Integracja z HA:** automatyczne tworzenie encji przez MQTT Discovery.

Pełna mapa punktów danych urządzenia: [`docs/dps-map.md`](docs/dps-map.md).

## Struktura repozytorium

```
fakro_config.py              # wspólna konfiguracja (czyta zmienne środowiskowe / .env)
.env.example                 # wzór konfiguracji — skopiuj do .env i uzupełnij
requirements.txt             # zależności (tinytuya, paho-mqtt)
src/
  fakro_bridge.py            # główny serwis: Tuya <-> MQTT (+ komendy)
  fakro_healthcheck.py       # restart usługi przy braku heartbeatu
discovery/
  ha_discovery.py            # publikacja MQTT Discovery do Home Assistanta
tools/                       # skrypty deweloperskie/diagnostyczne
  test_connection.py         # szybki test połączenia z urządzeniem
  read_status.py             # odczyt surowego statusu + odświeżenie DPS
  bridge_readonly.py         # uproszczony most tylko do odczytu (starszy)
  ha_discovery_extra.py      # wcześniejsza wersja discovery (referencja)
deploy/
  deploy.sh                  # deploy z Maca do kontenera LXC po SSH
  systemd/                   # jednostki systemd (usługa + healthcheck + timer)
docs/
  dps-map.md                 # mapa punktów danych Tuya (DPS)
```

## Konfiguracja

Wszystkie sekrety (klucz lokalny Tuya, hasło MQTT itd.) pochodzą ze zmiennych
środowiskowych — **nic wrażliwego nie jest zapisane w kodzie ani w repo**.

```bash
cp .env.example .env
# uzupełnij .env prawdziwymi wartościami (patrz komentarze w pliku)
```

Plik `.env` jest ignorowany przez git. Przy uruchomieniu przez systemd jest
wczytywany jako `EnvironmentFile`; przy uruchomieniu ręcznym `fakro_config.py`
sam go wczytuje z katalogu projektu.

## Uruchomienie lokalne (do testów)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python tools/test_connection.py     # sprawdź połączenie z oknem
python src/fakro_bridge.py          # uruchom most (Ctrl+C, aby zatrzymać)
```

## Deploy na kontener LXC (Proxmox)

Deploy odbywa się z Maca po SSH — kopiuje kod i `.env`, instaluje zależności,
konfiguruje systemd i restartuje usługę. Docelowa lokalizacja na kontenerze:
`/opt/fakro-bridge`, środowisko Python: `/opt/tuya-env`.

```bash
./deploy/deploy.sh              # deploy + restart usługi
./deploy/deploy.sh --discovery  # dodatkowo opublikuj encje do Home Assistanta
```

Parametry deployu (host kontenera, katalogi) czytane są z pliku `.env`
(klucze `FAKRO_DEPLOY_HOST`, `FAKRO_DEPLOY_DIR`, `FAKRO_VENV_DIR`) i można je
doraźnie nadpisać zmienną środowiskową:

```bash
FAKRO_DEPLOY_HOST=root@192.168.x.x ./deploy/deploy.sh
```

### Przydatne komendy na kontenerze

```bash
systemctl status fakro-bridge          # stan usługi
journalctl -u fakro-bridge -f          # logi na żywo
systemctl list-timers fakro-healthcheck # następny healthcheck
```

## Zależności

- Python 3.13
- [`tinytuya`](https://github.com/jasonacox/tinytuya) — lokalny protokół Tuya
- [`paho-mqtt`](https://github.com/eclipse/paho.mqtt.python) — klient MQTT
