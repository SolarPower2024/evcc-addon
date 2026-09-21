# Changelog

## 0.315.0-lm5

- The grid charge power the peak check assumes is now a setting under
  Lastspitzenmanagement, and the section shows which value is actually in use
  and where it came from.
- Fix: an undeterminable charge power blocked grid charging with nothing but a
  debug line. Note that a battery meter only reports its limits when both
  maxchargepower and maxdischargepower are set.
- Load management now also refuses grid charging when the charge power is
  unknown, instead of waving it through.

## 0.315.0-lm4

- The peak shaving target entity now has its own "Lastspitzenmanagement" section
  in the configuration; no yaml needed when running as this add-on.
- Fix: the card could report "unrestricted" while shaving at full power, when
  the setpoint happened to equal the free-discharge value.
- Fix: grid charging was blocked for as long as the reserve was armed, so the
  reserve could only be refilled from pv and stayed empty overnight. It is now
  blocked only when charging would actually exceed the peak limit.
- Fix: a missing target entity left the "reserve armed" state behind.

## 0.315.0-lm3

- Peak shaving: the battery's lower soc range can be reserved for grid demand
  peaks. Configure the switch, the peak limit (2–20 kW) and the reserve soc
  under Hausbatterie; the output entity goes into `evcc.yaml`, see the docs.
- While the reserve is held, the battery stays in normal mode and grid charging
  is blocked, as charging from the grid would create the peak itself.
- The Home Assistant plugin can now write `number` and `input_number` entities.

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
