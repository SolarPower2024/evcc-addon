# Changelog

## 0.316.1-lm6

- Peak shaving: the setpoint and the grid charge power are fitted to the
  entity's min, max and step (some batteries misbehave on values off the step).
  The entity no longer needs min 0, max 10000 and step 1.
- Peak shaving: a value is only written when the entity holds a different one.
  New **Schreib-Toleranz** under Lastmanagement-Details → Peak Shaving (default
  0 W = every change) skips smaller changes, sparing devices that store each
  write.
- Peak shaving: without meter values for over 2 minutes the battery is released
  (free value) and grid charging pauses until the values are back. Before, the
  last setpoint stayed in the entity.
- Phase switching: if the minimum current on 1 phase ends up above the 1-phase
  maximum (e.g. changed through Home Assistant), it charges at the 1-phase
  maximum with a warning instead of stopping the loadpoint.
- Heater in stages: the mode buttons read Aus / Smart / Ein instead of Schnell.
- Nothing to do for you.

## 0.316.1-lm5

- evcc master up to 3 October 2026 taken in (61 commits after 0.316.1-lm4):
  battery-supported charging ends on grid import, the optimizer re-runs right
  after battery settings change, an unsupported battery mode falls back to the
  closest supported one, local network hosts suggested in device setup, new
  device and tariff templates.
- Phase switching: the 1-phase minimum current now builds on evcc's own
  projection of a pending switch to 1 phase. No change in behaviour.
- The temporary handling of the old `lmpriority` key (0.316.1-lm4) is removed.
  Update from 0.316.1-lm4; coming from an older version, start lm4 once first.

## 0.316.1-lm4

- Fix: 0.316.1-lm3 failed to start with "invalid keys: lmpriority" when a
  loadpoint once moved from `evcc.yaml` to the ui still had the old
  `lmpriority` stored in the database. The key is accepted again and removed
  from the database at the first start; the log shows "old lmpriority removed
  from the stored loadpoint config". Nothing to do for you.

## 0.316.1-lm3

- Load management: switch devices (heaters on a Home Assistant switch) now also
  respect a circuit's current limit (fuse), not only its power limit.
- One-time grid charging ends by itself when the battery is removed.
- The EEG counter stays shown in the ui when Home Assistant cannot be reached
  at startup.
- Nothing of the fork is read from `evcc.yaml` any more, everything is set in
  the ui: `lmpriority` at a loadpoint and `loadmanagement` under `site` are
  gone. An `evcc.yaml` still containing them fails to start; remove them.
- Internal restructuring after a code review (load management and peak shaving
  in packages of their own, fewer changes in evcc's own files). No change in
  behaviour.

## 0.316.1-lm2

- Heater in stages: new heating device template "Home Assistant Heizstab in
  Stufen" for a heater with one switch per stage, e.g. a 3 x 3 kW heating rod
  switched per phase. One loadpoint (3 phases) instead of one switch loadpoint
  per stage: evcc switches on as many whole stages as fit, load management
  steps it down stage by stage instead of switching it off, and all stages are
  set in one cycle. A higher stage waits for a delay (default 1 minute),
  switching down is immediate. With a power sensor (e.g. a Home Assistant sum
  helper of the stages) it shows "bereit" instead of "heizt" while its own
  thermostat has cut out. The existing switch loadpoints keep working.
- Phase switching: loadpoints with 1p/3p switching get optional min/max current
  for 1-phase under Elektrik; the regular range is then the 3-phase one.
  Switching to 3 phases only once 1-phase is at its maximum and the surplus
  reaches the 3-phase minimum, back to 1 phase below it. Plus optional delays
  to 3 phases and to 1 phase; empty = the enable and disable delay. Starting
  and stopping charging keep the enable and disable delay. Without these values
  nothing changes.

## 0.316.1-lm1

- Based on evcc master after 0.316.0 (59 commits, with all fixes of 0.316.1).
  New from evcc among others: circuits can be created in the ui
  (Konfiguration → Lastmanagement), site country setting, confirmation before
  grid discharge, battery limit soc together with the battery mode, loadpoints
  start in their default mode after a restart. Circuits kept in the old yaml
  keep working (shown as "veraltet"). Moving them to the new circuit dialog
  gives them new names: choose the battery circuit and the load management
  (peak) circuit again under Lastmanagement-Details.
- Optimizer: the battery's upper soc bound now comes from evcc (full capacity
  without soc limits) instead of the fork's own fallback. Same plans as before.
- Consumption forecast for the optimizer, under Lastmanagement-Details →
  Erweitert → Verbrauchsprognose: evcc (28 day average), per weekday, or
  manual from an uploaded load profile (csv, W per quarter hour or hour and
  month, working days and weekends apart). The profile is mixed with the last
  8 weeks, recent days counting more, and follows their level; a strong
  deviation of the last 3 hours carries over into the next hours. Without a
  profile evcc's forecast applies.

## 0.316.0-lm9

- Optimizer: grid charging is planned slot by slot as evcc charges, while it
  runs and from where the battery reaches the start soc. The plan charges from
  the first slot with room below the limit, so the suggestion no longer says to
  hold while evcc is charging. During a peak that pauses the charge the battery
  covers the part above the limit (above the reserve it runs freely). Switched
  grid charging without a charge power entity draws its full power, which the
  forecast shows over the limit, as it happens.
- Optimizer: the forecast is planned again right away when grid charging starts
  or stops, and a changed setting arriving during a planning run is planned
  right after it instead of waiting for the next slot.

## 0.316.0-lm8

- Optimizer: the peak shaving reserve covers peaks in the forecast. Where the
  grid would go over the limit while the battery holds the reserve, the battery
  covers the part above the limit below the reserve, down to its own minimum
  soc, as peak shaving does; without peaks it still stops at the reserve. What
  charges below the reserve (pv, grid charging) stays there for peaks.
- Optimizer: grid charging with peak shaving is planned only with the room below
  the limit and pauses while the demand exceeds it (before, the forecast could
  show charging over the limit). A peak running right now no longer hides grid
  charging from the whole forecast.
- Only the forecast changes, nothing is switched. A further planning pass that
  fails keeps the plan before it.

## 0.316.0-lm7

- Optimizer: soc-based grid charging as a second planning pass. The battery
  forecast now discharges to the start soc and then shows the grid charge to
  the stop soc within the charging time at the grid charge power, instead of
  holding at the stop soc. Whether it charges again later is up to the
  optimizer. Only the forecast changes, nothing is switched.

## 0.316.0-lm6

- **OeMAG removed**: the OeMAG market price feed-in tariff with its monthly
  recalculation is gone (kept aside for later). If your feed-in tariff uses
  "OeMAG Marktpreis", switch it to another tariff (e.g. a fixed price) before
  updating. The EEG split stays.
- Optimizer: soc-based grid charging is planned ahead. The battery forecast
  now shows the charge from the start to the stop soc where the battery is
  expected to reach the start soc, instead of staying at the start soc. The
  peak shaving reserve stays a hard minimum; with it above the start soc no
  charging is planned. A floor set this way is no longer shown as "leer".
- Consumption forecast by weekday and a consumption safety margin
  (Lastmanagement-Details → Erweitert).
- Battery identification (Lastmanagement-Details → Batterie-Vermessung):
  usable capacity and efficiency learned from the stored slots, optionally
  used by the optimizer and one-time grid charging.
- Texts: battery page without the peak details (now only in Mehr →
  Lastmanagement (Peak)) and the one-time charging hint; overview with the
  state beside the switch, the shed guard lock only while it holds a load off,
  "dimmen/abschalten von unten nach oben"; shorter peak statistics and
  priority dialogs.

## 0.316.0-lm5

- Load management (peak) circuit (Lastmanagement-Details → Erweitert): the
  circuit holding your peak limit, beside a circuit for the fuse. Only it is
  shown under Mehr → Lastmanagement (Peak), only it is lifted by the switch
  there, and follow the peak raises it. Replaces "Stromkreis-Grenze
  mitziehen", a circuit chosen there is taken over. None = all circuits as
  before.
- An exceeded power limit no longer pops up as a notification, it stays in the
  log. An exceeded current limit (fuse) is still shown.
- Priorities (Lastmanagement-Details → Prioritäten) are sorted by drag, the
  most important on top; a drag numbers all loads from the bottom (0, 1, 2 …).
- Overview: shed guard lock beside the name, no priority column, loads listed
  by priority ("unten wird zuerst abgeworfen").
- Optimizer: solves again right away when its inputs change (peak switch,
  limit, reserve, soc grid charging, follow the peak, circuit limits), instead
  of keeping an old plan for up to 15 minutes.
- Texts: "Batterie-Netzladen" instead of "Netzladen"; Erweitert without the
  default values, the hysteresis and the budget named as peak shaving's;
  shorter peak shaving and capacity tariff descriptions.

## 0.316.0-lm4

- Load management switch (Mehr → Lastmanagement): off lifts the power limits
  of all circuits, so wallboxes, heaters and grid charging are no longer
  throttled for them. Fuses (current limits), §14a and battery peak shaving
  stay active; the configuration is unchanged and on restores it. Survives a
  restart.
- Follow the peak can raise a chosen circuit's power limit along ("Stromkreis-
  Grenze mitziehen"), never below its configured value, back with the next
  month. Only for a circuit that is the peak limit, not the agreed connection
  power.

## 0.316.0-lm3

- Follow the peak (Lastmanagement-Details → Peak Shaving): once the month's
  highest quarter hour is above the peak limit, the limit rises to that peak
  minus a buffer (default 0.5 kW), so the battery no longer shaves below a
  peak that is paid anyway. A new month starts with your own limit again.
- Capacity tariff (new tile Lastmanagement-Details → Leistungstarif): price
  per kW and year, threshold with a higher price above it, agreed power and
  minimum; prefilled with the Austrian draft for 2027. Mehr → Peak Shaving
  shows each month's capacity cost and what the battery saved.
- Optimizer: a price tariff set as planner tariff (Tarife → Vorhersage
  hinzufügen → Planer-Vorhersage) is the grid price the optimizer plans with;
  statistics and costs keep the grid tariff. With a real price close to the
  feed-in price (e.g. 10 ct vs 9 ct) the optimizer never discharges; a
  planning price of at least 1.25 × feed-in (12 ct) lets it.
- Charge once: the duration now includes the charging losses, so the target
  is reached in time and "bis Uhrzeit" picks enough cheap slots; with an
  unknown grid charge power the optimizer plans with the battery's maximum
  charge power.

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
