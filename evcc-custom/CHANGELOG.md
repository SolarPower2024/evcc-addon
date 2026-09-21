# Changelog

## 0.315.0-lm2

- The load shedding priority is now a field in the loadpoint configuration ui,
  shown once a circuit is assigned. It was yaml-only before, which made it
  unusable for loadpoints managed through the ui. Changing it needs a restart.

## 0.315.0-lm1

Based on evcc upstream master `0bd94d01`.

- Load management: `lmpriority` per loadpoint, lower is shed first, separate
  from the pv surplus `priority`
- Load management: the home battery's grid charging counts against a circuit
  and is shed when the budget runs out
- Battery: soc-based grid charging with a switch and a start/stop soc,
  configurable in the ui under Hausbatterie
