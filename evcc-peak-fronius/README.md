# evcc Peak Fronius (`evcc_peak_fronius`)

Home-Assistant-Integration für Peak Shaving (Leistungstarif) mit einer
Fronius-GEN24-Batterie (z. B. BYD Battery-Box) über
[fronius_modbus](https://github.com/callifo/fronius_modbus).

Der evcc-Fork gibt die Peak-Werte vor (an/aus, erlaubte Netzleistung, SoC-Schwelle,
Netzladeleistung). Die Anforderung (normal, Netzladen, Entladesperre) setzen die
Home-Assistant-Skripte der evcc-Batteriemodi, wie im evcc-Standard. Diese Integration regelt die Batterie innerhalb
von Sekunden. Fronius regelt den Eigenverbrauch weiter selbst: die Integration
setzt nur Speichermodus, Entladegrenze und Netzladeleistung.

## Was sie tut

| Lage | Speichermodus | Entladegrenze |
|---|---|---|
| SoC über der Schwelle | `Discharge Limit` | Maximum |
| SoC unter der Schwelle | `Discharge Limit` | `Netz + Batterie − Limit`, auf 10 W aufgerundet, nie unter 0 |
| Anforderung Netzladen | `Charge from Grid` | – (Netzladeleistung, auf 10 W abgerundet) |
| Anforderung Entladesperre, Peak Shaving an | `Discharge Limit` | nur `Netz + Batterie − Limit` (Spitzen), egal welcher SoC |
| Anforderung Entladesperre, Peak Shaving aus | `Block Discharging` | – |
| Peak Shaving aus | `Auto` (nur wenn die Integration den Modus hält) | – |

- Unter der Schwelle bleibt sie, bis der SoC 2 % darüber liegt.
- Eine höhere Entladegrenze wird sofort geschrieben, eine niedrigere höchstens
  alle 10 s und erst ab 50 W Unterschied; insgesamt höchstens ein Schreibvorgang
  je 2 s. Nach einem eigenen Moduswechsel wird die Grenze einmal neu geschrieben.
  Ein fehlgeschlagener Schreibvorgang wird nach 4, 8, 16 … s (höchstens 5 min)
  wiederholt.
- **Messausfall** (Netzleistung über 30 s alt oder nicht verfügbar):
  Entladegrenze auf Maximum.
- **Lebenszeichen von evcc:** Das Limit zeigt zu jeder Viertelstunde
  (:00/:15/:30/:45) 0, und evcc schreibt es neu, solange es läuft. Beim Stopp
  schreibt evcc 0, dann gibt die Integration sofort frei. Kommt bis 2 min nach
  Viertelbeginn nichts, gibt die Integration die Batterie frei (Modus `Auto`).
  Ohne evcc gibt es kein Peak Shaving.
- Zeigt der Speichermodus nach dem Schreiben nicht den gewollten Wert, schreibt
  sie ihn alle 10 s neu und drückt nach 3 Versuchen „Reset Modbus API Control“
  (wenn ausgewählt).
- Bei jeder Freigabe steht zuerst die Entladegrenze auf Maximum (Netzladen auf 0),
  dann der Modus auf `Auto`: bleibt der Modus hängen, ist die Batterie trotzdem frei.
  Ein von Hand auf 0 gesetztes Limit gibt sofort frei.
- Beim Deaktivieren, Entfernen oder Stoppen von Home Assistant geht der Modus
  auf `Auto` zurück, wenn die Integration ihn hält. Das gilt auch nach einem
  Neustart.

## Entitäten (evcc schreibt sie)

| Entität | Bedeutung |
|---|---|
| `switch.evcc_peak_fronius_peak_shaving` | Peak Shaving an/aus |
| `number.evcc_peak_fronius_limit` | erlaubte Netzleistung im laufenden 15-min-Fenster (W), zugleich Lebenszeichen |
| `number.evcc_peak_fronius_soc_threshold` | SoC-Schwelle (Reserve, %) |
| `select.evcc_peak_fronius_request` | `normal` / `grid_charge` / `hold`, gesetzt von den Skripten der Batteriemodi |
| `number.evcc_peak_fronius_grid_charge_power` | Netzladeleistung (W) |
| `sensor.evcc_peak_fronius_status` | was gerade passiert, mit Entladeziel und Schreibvorgängen des Tages |

## Einrichtung

1. fronius_modbus einrichten, mit Web-API (lokale Rolle `customer` genügt; nötig
   für „Laden aus dem Netz“ und den Reset-Knopf), Scan-Intervall 5 s. Fronius
   empfiehlt Firmware 1.40.0 oder neuer. In der Fronius-Weboberfläche die zeitbasierte
   Batteriesteuerung ausschalten. Nicht zugleich die offizielle
   Fronius-Integration mit Modbus betreiben (nur ein Modbus-Client).
2. Diese Integration installieren: HACS → ⋮ → *Benutzerdefinierte Repositories* →
   `https://github.com/SolarPower2024/evcc-addon`, Kategorie *Integration*; oder
   `custom_components/evcc_peak_fronius` dieses Repositorys nach
   `/config/custom_components/` kopieren. Danach Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen →
   evcc Peak Fronius*: Netzleistung (Zähler „Power“, Bezug positiv), Batterie-
   Entladeleistung („Storage discharge power“) und Batterie-Ladeleistung („Storage
   charge power“, wird abgezogen; bei einem einzigen Sensor mit Vorzeichen leer
   lassen), SoC, Speichermodus („Storage Control Mode“), Entladegrenze,
   Netzladeleistung und optional den Knopf „Reset Modbus API Control“ wählen.
4. Die Skripte der evcc-Batteriemodi setzen nur die Anforderung, z. B. das Skript
   des Modus Halten: `select.select_option` auf
   `select.evcc_peak_fronius_request` mit `hold` (Normal: `normal`, Netzladen:
   `grid_charge`). Den Speichermodus von fronius_modbus schalten sie nicht mehr.

Hinweise zu fronius_modbus: Entladegrenze und Netzladeleistung sind dort nur im
passenden Speichermodus verfügbar; die Integration schreibt sie erst, wenn der Modus
steht. Nach einem Neustart von Home Assistant zeigt fronius_modbus „Discharge Limit“
mit 0 W als „Block Discharging“; die Integration setzt den Modus dann einmal neu.

Bei jedem Wechsel auf `Charge from Grid` schaltet fronius_modbus über die Web-API
die Ladequellen und baut Modbus neu auf; bis zu 30 s wiederholen seine Sensoren
die letzten Werte. Die Integration behandelt diese 30 s als Messausfall: wird in
dieser Zeit gekappt, ist die Batterie frei. Netzladen erreicht laut fronius_modbus
nur etwa die Hälfte der eingestellten Leistung (Grenze der Hardware).

Grenzen: Fronius kennt keinen Rückfall-Timer für die Batteriewerte. Stirbt Home
Assistant mitten in einer Kappung, bleibt die letzte Entladegrenze stehen, bis
Home Assistant wieder läuft.

## Tests

Im Ordner `evcc-peak-fronius/`:

```bash
pip install -r requirements-test.txt
pytest
```

`tests/test_regelung.py` prüft die Regeln ohne Home Assistant,
`tests/test_controller.py` die Integration gegen ein nachgebautes fronius_modbus.
