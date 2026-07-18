# Mapa punktów danych Tuya (DPS) — okno dachowe Fakro

Odtworzona metodą reverse-engineeringu z komunikacji lokalnej urządzenia
(protokół Tuya 3.3). Kolumna „Topic MQTT" odnosi się do bazy `fakro/window`
(zmienna `FAKRO_BASE_TOPIC`).

## Sterowanie (zapisywalne)

| DP  | Topic MQTT           | Zapis (komenda)           | Wartości                          | Opis |
|-----|----------------------|---------------------------|-----------------------------------|------|
| 2   | `control`            | `fakro/window/set`        | `open` / `close` / `stop`         | Podstawowa komenda okna |
| 7   | `position`           | `fakro/window/position/set` | `0`–`100` (%)                   | Pozycja docelowa / bieżąca |
| 19  | `speed`              | `fakro/window/speed/set`  | `soft` / `normal` / `quick`       | Prędkość ruchu |
| 141 | `rain_use`           | `fakro/window/rain_use/set` | `ON` / `OFF`                    | Włączenie ochrony przed deszczem |

## Odczyt — stan i czujniki

| DP  | Topic MQTT     | Opis |
|-----|----------------|------|
| 140 | `rain_state`   | Wykryto deszcz (bool) |
| 106 | `motor`        | Stan silnika |
| 111 | `noposition`   | Brak pozycji / kalibracja |
| 120 | `errors`       | Kod błędu |
| 181 | `current`      | Pobór prądu (surowa wartość) |
| 182 | `voltage`      | Napięcie (surowa wartość) |
| 179 | `load_close`   | Próg obciążenia przy zamykaniu |
| 180 | `load_open`    | Próg obciążenia przy otwieraniu |

## Odczyt — diagnostyka i liczniki

| DP  | Topic MQTT   | Opis |
|-----|--------------|------|
| 101 | `flagserwis` | Flaga serwisowa |
| 102 | `type`       | Typ urządzenia |
| 121 | `pozikon`    | Pozikon (licznik) |
| 122 | `spare`      | Rezerwa / nieznane |
| 123 | `spare2`     | Rezerwa / nieznane |
| 124 | `spare3`     | Rezerwa / nieznane |
| 184 | `cnt_up`     | Licznik otwarć |
| 185 | `cnt_down`   | Licznik zamknięć |
| 186 | `cnt_work`   | Licznik pracy silnika |

## Topiki pomocnicze (publikowane przez most)

| Topic MQTT      | Opis |
|-----------------|------|
| `raw`           | Pełny surowy słownik `dps` (JSON) |
| `availability`  | `online` / `offline` |
| `heartbeat`     | Znacznik czasu (unix) ostatniego odświeżenia — używany przez healthcheck |
| `heartbeat_iso` | Znacznik czasu ostatniego odświeżenia (czytelny) |
