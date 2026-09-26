# Changelog

## 0.316.0-lm2

- One priority: a loadpoint's regular evcc priority now also decides load
  management shedding, so pv surplus, planned charging and load management
  follow one order. The home battery keeps its own value (0-10). The former
  load management priorities of the loadpoints are taken over once on the
  first start (log line per loadpoint) - this also changes the pv surplus
  order accordingly.
- Optimizer: peak limit, peak reserve, soc-based grid charging (start soc
  planned ahead, stop soc as goal within "Netzlade-Ziel erreichen in",
  default 3 h), one-time grid charging, circuit limits and priorities are
  given to the optimizer as inputs, so its plan, the battery forecast and its
  suggestions match what evcc does. Works with a local optimizer (addon
  "evcc optimizer").
- Charge once: battery page, "Einmalig bis … aus dem Netz laden", right away
  or by a time at the cheapest time, with cancel, continues across restarts.
- Second feed-in tariff (EEG): add "Einspeisevergütung EEG" below the
  feed-in tariff (fixed price, 0 allowed) and set the Home Assistant counter
  of the EEG export. The export is recorded split into EEG and standard
  feed-in (GET /api/feedinsplit); the display on the new energy page follows
  with a later evcc version.

## 0.316.0-lm1

- Based on evcc 0.316.0.
- Below the peak reserve a battery mode set from outside through the evcc api
  (e.g. by a Home Assistant automation) is no longer overridden.
- Maintenance: the load management check of a loadpoint now runs inside
  evcc's own calculation instead of a copy of it, so later evcc updates merge
  more easily. No change in behaviour.
- Peak shaving targets can no longer be written through a yaml
  `source: homeassistant` setter; set them in the ui as before.

## 0.315.0-lm12

- Load management no longer counts on a load that ignores its limit. When a
  circuit stays overloaded and a reduced load keeps drawing more than allowed
  (e.g. a battery told to grid-charge at 3 kW that keeps drawing 6.25 kW), the
  next load up the priority order is cut after the set cycles (Erweitert →
  "Vorgabe ignoriert nach", default 3, 0 = off). The overview shows an event,
  the log a warning.
- Lastmanagement-Details are shown as tiles, like the services.

## 0.315.0-lm11

- Peak shaving now limits the **15 minute average** instead of the momentary
  grid power. Energy not drawn earlier in a quarter hour allows more later, so
  short spikes no longer use the battery reserve. The battery page shows the
  grid draw allowed until the end of the quarter hour.
- The quarter hour is metered with an energy counter: the grid meter's import
  counter, else a Home Assistant energy sensor (new field under
  Lastmanagement-Details → Peak Shaving), else the grid power as before.
- New under Erweitert: from which minute the allowed grid draw stops growing
  (default 12) and its cap (default 2 × peak limit).
- New under Mehr → **Peak Shaving**: the highest quarter hour of each month
  with and without the battery, and how often the battery stepped in.
- The profile selection moved to the bottom of the battery page.
- Shorter help texts in the load management settings.

## 0.315.0-lm10

- New under Mehr → **Lastmanagement**: an overview of what load management is
  doing right now. Circuit load, peak shaving (15 minute average, setpoint),
  battery grid charging, every load with its state (running, throttled, shed
  and held off until, waiting with what it needs and what is free, paused) and
  the recent events.
- New **Abwurfschutz** under Lastmanagement-Details: a protected loadpoint
  that load management had to switch off stays off for the set minutes, so a
  heater does not flap with a fluctuating load.
- New **Profile** under Lastmanagement-Details, picked on the battery page:
  named sets of settings (e.g. summer and winter) for soc grid charging,
  battery usage, the discharge lock, peak shaving (incl. limit) and the
  wallboxes' solar share. Values not ticked stay as they are.
- New **Erweitert** under Lastmanagement-Details: reserve hysteresis, free
  value, grid charge hold-off, reservation expiry and battery phases, which
  were yaml only before.
- OeMAG: the feed-in tariff card shows the last finalized month and the next
  recalculation. "Monate anzeigen" lists every finalized month and can
  recalculate one by hand with a corrected price.

## 0.315.0-lm9

- The peak shaving setpoint and the grid charge power are now written to Home
  Assistant in every cycle, not only when they change. A value changed in Home
  Assistant (by hand, an automation or a restart) no longer sticks.
- While peak shaving is off, the free value (10000 W) is written once and then
  nothing more.

## 0.315.0-lm8

- New feed-in tariff "OeMAG Marktpreis (Einspeisung)" under Tarife &
  Vorhersagen → Einspeisevergütung. The latest published market price is used
  as the running feed-in price.
- From the finalize day (default 15th, adjustable 1 to 28) that value becomes
  the final price of the previous month: the stored feed-in rates of that
  month and the prices of its charging sessions (solar share) are recalculated
  once. Each month only once, so a later change at the source does not rewrite
  it again.

## 0.315.0-lm7

- Home Assistant switches (heaters etc.) are now switched on or off as a whole
  by load management. Before, a 3 kW heater could be switched on with only
  1.6 kW to spare and the circuit stayed overloaded.
- New optional field "Leistung" (W) on the Home Assistant switch: the power the
  device draws when on. Load management checks it before switching on and uses
  it while there is no measurement. Without a power sensor it is also shown as
  the device's power.
- An overload is now shed by priority, lowest first, instead of hitting
  whichever loadpoint evcc happens to update first.
- Power that no higher-priority load can use (e.g. 1.6 kW free while every
  waiting heater needs 3 kW) is no longer held back from lower-priority loads.

## 0.315.0-lm6

- The configuration section is now called "Lastmanagement-Details" with four
  entries: Batterie-Stromkreis, Prioritäten, Netzladen and Peak Shaving.
- Shed priorities for all loads, the battery included, are set under
  Prioritäten and apply immediately. The field in the loadpoint dialog is gone;
  a value set there stays in use until you change it on the new page.
- New optional charge power entity under Netzladen: evcc writes the permitted
  grid charge power in W, sized to stay below the peak limit and within the
  circuit, and 0 when not charging. Without it grid charging stays on/off.
- Fix: grid charging was blocked while the battery was below the reserve.
- A demand peak (consumption without the battery above the peak limit) pauses
  grid charging for 5 minutes so the battery can shave it.
- The discharge entity gets 0 instead of 10000 while the battery charges from
  the grid.
- Fix: a higher-priority load that can only switch on in full (battery, heater)
  never got its power from a lower-priority wallbox.
- Fix: charge powers that are not a multiple of 100 W (e.g. 6250) could not be
  saved; the browser blocked it without a message.
- Soc grid charging carries on after a restart, a lost hand-back of the free
  value to Home Assistant is retried, and setpoints are whole watts.

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
