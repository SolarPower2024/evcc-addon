# Changelog

## 0.319.0-lm5-dev1

- **Debug → Testversion:** take over the data of evcc custom (devices, settings,
  history) and give back what was recorded here (charging sessions, energy
  statistics, peak values; devices and settings optional). Only while evcc
  custom is stopped; a backup of its database is made first. The add-on now
  reads the add-on folders and may restart itself.

## 0.319.0-lm4

- First version: the same as evcc custom 0.319.0-lm4, with its own database and
  manual start, for testing new functions before they reach evcc custom.
