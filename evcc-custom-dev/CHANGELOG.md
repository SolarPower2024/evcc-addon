# Changelog

## 0.319.1-lm1

- **evcc 0.319.1:** fixes in the device templates for the Open-Meteo tariff
  (empty values) and the Huawei SmartLogger. Nothing to do.

## 0.319.0-lm5

- **Charging plans:** the planner now takes the peak limit, the circuit limits
  and the home consumption into account and starts plans early enough. Before,
  it assumed full charger power and could finish late when the peak limit
  slowed charging down.
- **Battery grid charging by SoC:** a hint appears when the stop SoC lies above
  the peak shaving reserve.
- **Debug → Einspeisung neu berechnen:** quarter hours without stored home
  consumption are now also capped to production plus battery discharge.

## 0.319.0-lm5-dev1

- **Debug → Testversion:** take over the data of evcc custom (devices, settings,
  history) and give back what was recorded here (charging sessions, energy
  statistics, peak values; devices and settings optional). Only while evcc
  custom is stopped; a backup of its database is made first. The add-on now
  reads the add-on folders and may restart itself.

## 0.319.0-lm4

- First version: the same as evcc custom 0.319.0-lm4, with its own database and
  manual start, for testing new functions before they reach evcc custom.
