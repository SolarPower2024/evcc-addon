# evcc custom

evcc with a few additions on top of upstream. All of them are inert until
configured, so this behaves like the official addon until you switch something on.

Everything is configured in the evcc ui under **Konfiguration →
Lastmanagement-Details** (Batterie-Stromkreis, Prioritäten, Abwurfschutz,
Batterie-Netzladen, Peak Shaving, Leistungstarif, Batterie-Vermessung, Profile,
Erweitert) and on the
**Hausbatterie** page (profile, switches, limits, soc values). **Mehr →
Lastmanagement (Peak)** shows what
load management is doing right now, **Mehr → Peak Shaving** the highest quarter
hour of each month.

## 1. Load management priorities

One priority decides who gives way when a circuit runs out of budget:
**lower is shed first.** For a loadpoint it is its regular evcc priority, the
same one that distributes pv surplus, so pv surplus, planned charging and load
management follow one order. The home battery has no evcc priority and keeps a
value of its own on the same 0-10 scale.

Set it under **Lastmanagement-Details → Prioritäten** for every loadpoint on a
circuit and for the home battery once it is assigned to one: drag the loads into
order, the most important on top. A drag numbers all of them from the bottom
(0, 1, 2 …, at most 10). A loadpoint's value is also shown and editable in its
own settings. Changes apply immediately. Loads without a circuit do not take part and are not listed.

Earlier versions had a separate load management priority per loadpoint
(`lmpriority`). On the first start of this version those values are taken over
into the loadpoints' priority once (a log line names each one); the pv surplus
order follows them from then on.

Loads only take part when they sit on a `circuit`. Without differing
priorities nothing changes versus upstream.

Recovery uses the same mechanism in reverse: power that frees up stays withheld
from lower-priority loads for as long as someone above still reports unmet
demand. Each rung costs one update cycle, and evcc updates one loadpoint per
cycle, so a full shed or recovery takes up to `interval x loadpoints`.

**Overload** is shed from the bottom: a load keeps what it draws as long as the
loads below it draw enough to cover the excess.

That only works if they give way. A load that keeps drawing more than it was
allowed while its circuit is overloaded (tolerance 300 W or 10 %) is no longer
counted on after the set cycles, **Erweitert → Vorgabe ignoriert nach** (default
3, 0 = off). The next load up the priority order is then cut instead. Example: the
battery is told to grid-charge at 3 kW but keeps drawing 6.25 kW, so the heater
above it is switched off. As soon as the load follows its limit again it counts
again. The log shows a warning and the overview the event "folgt der Vorgabe
nicht".

**Home Assistant switches** (heaters and the like) can only be on or off, so
load management switches them on only when their whole power fits and off when
it no longer does. Enter the power the device draws when on in the switch's
field **Leistung** (W). evcc checks it before switching on and uses it while
there is no measurement; without a power sensor it is also shown as the
device's power. Without the field evcc uses the last measured power, or 3680 W
(16 A) before the first measurement.

## 2. Battery in load management

The home battery's grid charging power counts against a circuit. Assign the
circuit under **Lastmanagement-Details → Batterie-Stromkreis**; the circuit
needs a power limit in kW (`maxPower`), a current limit alone is not checked.

Under **Batterie-Netzladen** you choose how the battery charges from the grid:

- **On/off** (no charge power entity): charging only starts when the full
  expected charge power fits into the circuit.
- **Dynamic** (with a charge power entity, e.g. `input_number.battery_charge_power`):
  evcc writes the permitted charge power in W every cycle, the smallest of the
  expected charge power, the room below the peak limit (when peak shaving is on)
  and the room in the circuit. Below 500 W it does not charge and writes 0. Your
  Home Assistant automation sets the battery's charge power from it. The entity
  needs min 0, max at least the expected charge power and step 1.

Outside the ui the same settings exist in `evcc.yaml`:

```yaml
site:
  loadmanagement:
    timeout: 10m
    battery:
      circuit: main   # the circuit the battery draws from, empty = not managed
      priority: 0     # shed before everything else
      power: 5000     # expected grid charge power in W
      phases: 3
      holdoff: 5m     # wait before retrying after a shed
```

A battery driven through Home Assistant mode scripts can only be switched on or
off, so the **full** `power` has to fit into the budget. Set it to the power the
battery realistically draws, not its nameplate maximum — otherwise grid charging
blocks itself unnecessarily. If omitted it falls back to the sum of the battery
meters' `maxchargepower`.

`holdoff` prevents flapping: stopping the battery frees exactly the power that
would make it start again.

## 3. Soc-based grid charging

A switch plus a start and a stop soc, independent of the price-based grid charge
limit. Configure it in the evcc ui under **Hausbatterie**. Charging starts once
the soc is at or below the start value and runs until the stop value is reached.

It goes through the same battery mode path as price-based grid charging, so a
Home Assistant battery triggers its `modeCharge` script as usual. The battery's
own `maxsoc` still applies on top as a hard ceiling.

Also available via the api:

```
POST /api/batterysocgridcharge/{true|false}
POST /api/batterysocgridchargestart/{soc}
POST /api/batterysocgridchargestop/{soc}
```

### Charge once

Below it on the battery page: **Einmalig bis … aus dem Netz laden**, right
away or **bis Uhrzeit** at the cheapest time before it (from the planner
tariff; right away when the time has passed or the duration is unknown). It
switches itself off at the target soc, continues across restarts and has a
cancel button. The same checks as soc-based grid charging apply (peak,
circuit, charge power).

```
POST   /api/batterygridchargeonce/{soc}[/{HH:MM}]
DELETE /api/batterygridchargeonce
```

## 4. Peak shaving

Caps the grid demand peak a demand charge (Leistungspreis) is billed on, by
holding the battery's lower soc range back as a reserve.

Configure it on the **Hausbatterie** page: a switch, the peak limit (2–20 kW in
0.5 kW steps) and the reserve soc.

| Battery soc | Behaviour | Value written to the entity |
| --- | --- | --- |
| above the reserve | ordinary self-consumption | `10000` (discharge freely) |
| below the reserve | peaks only | `max(0, demand − allowed)` in W, see below |
| charging from the grid | no discharging | `0` |

evcc only computes the setpoint. The Home Assistant automation reading the
entity does the actual discharging.

While peak shaving is on, the setpoint is written in **every cycle**, even when
it has not changed, so a value changed in Home Assistant (by hand, an
automation or a restart) is corrected in the next cycle. While it is off, the
free value is written once and then nothing more. The grid charge power entity
is written every cycle either way.

The target entity is set under **Lastmanagement-Details → Peak Shaving**, just
the entity id, for example `input_number.battery_peak_power`. Running as this
add-on, evcc reaches Home Assistant through the supervisor, so no url and no
token are needed. The entity needs **min 0, max at least 10000 and step 1**,
otherwise Home Assistant rejects the values.

Everything is written in watts; only the limit is shown in kW.

### The 15 minute window

A demand charge is billed on the average of each quarter hour (:00, :15, :30,
:45), so the limit applies to that average, not to the momentary grid power.
`allowed` is the grid power that keeps the running quarter hour's average at
the limit: `(limit × 15 min − energy drawn so far) / time left`. Drawing less
early on allows more later, so a short spike is only covered when the quarter
hour as a whole would end above the limit. Example: 5 kW limit, nothing drawn
for 5 minutes, then 7.5 kW are allowed for the remaining 10.

- `allowed` is at most **2 × the limit** (Erweitert → cap).
- From **minute 12** on it no longer grows, only falls (Erweitert → freeze
  minute). A meter clock off by a few seconds could otherwise move a large late
  draw into the next quarter hour.
- Once a quarter hour's budget is spent, `allowed` is 0 and the setpoint is
  the whole demand. This only happens when the battery could not deliver
  earlier.
- The part of a quarter hour evcc did not see (after a start) counts at the
  limit.

The energy drawn comes from, in this order:

1. the grid meter's import counter in evcc, when it has one
2. a Home Assistant energy sensor, **Energiezähler Netzbezug** under
   Lastmanagement-Details → Peak Shaving: a total counter in kWh or Wh, not a
   daily value
3. the grid power, which evcc only sees every 10 to 30 seconds

The dialog shows which one is in use. A counter that fails or stops updating is
replaced by the grid power until the quarter hour ends, with a warning in the
log. Grid charging still pauses on the momentary demand above the limit.

Outside the add-on there is no supervisor, so the endpoint has to be given once
in `evcc.yaml`:

```yaml
site:
  loadmanagement:
    peakshaving:
      uri: http://homeassistant.local:8123
      freevalue: 10000 # optional, the "discharge freely" signal
      hysteresis: 2 # optional, soc band around the reserve in %
```

### Why the demand is not simply the grid meter reading

Once the battery starts shaving, the grid meter no longer shows the load — it
shows the result of the controller's own work. Deriving the setpoint from it
would oscillate: shave, see a compliant grid value, stop, see the peak return.
evcc therefore adds the battery power back to recover the underlying demand,
which is independent of what the battery is doing. `TestPeakSetpointIsStable`
in the fork pins this down.

### Interaction with the other features

While the reserve is being held, evcc keeps the battery in **normal** mode so
your automation can discharge it. Grid charging (soc or price based) still works
below the reserve, with two rules:

- A demand peak, meaning consumption **without** the battery above the peak
  limit, pauses grid charging for 5 minutes and the battery shaves instead.
- The charge power itself is not counted against the peak limit. In on/off mode
  charging can therefore push the grid above the limit (e.g. 1 kW house + 6.25 kW
  charging). Use the dynamic charge power entity to keep charging below it.

Peak shaving alone is the expensive lever. Reducing a wallbox from 11 to 4 kW
costs charging time; emptying the battery costs a cycle and leaves nothing for
the next peak. Giving the wallbox the lowest priority lets load management take
the first bite when the circuit limit is reached.

### Follow the peak

Lastmanagement-Details → Peak Shaving → **Follow the Peak**. A capacity tariff
bills the month's highest quarter hour. Once the month already has a peak above
your limit, the limit rises to that peak minus the **buffer** (0–5 kW, default
0.5 kW; peak 10 kW → limit 9.5 kW), never below your own limit. The battery page
keeps showing your own limit; Mehr → Lastmanagement (Peak) notes the raised
one in the peak tile. A new month, or
switching it off, returns to your own limit.

The **load management (peak) circuit** (see Erweitert), when chosen, rises
along with the raised limit, never below its configured value, and is back at it
with the next month. This replaces the former "Stromkreis-Grenze mitziehen"; a
circuit chosen there is taken over.

### Capacity tariff (Leistungstarif)

Lastmanagement-Details → **Leistungstarif**: price per kW and year up to a
threshold, a higher price above it, the agreed power with the share billed at
least, and a minimum power. Prefilled with the Austrian draft for 2027
(33.82 €/kW/year up to 10 kW, double above, at least 20 % of the agreed power and
2 kW; final amounts from December 2026). Mehr → Peak Shaving then shows each
month's capacity cost, the saving against the peak without the battery (extra
cost when grid charging raised the peak) and the total.

## 5. Second feed-in tariff (EEG)

If part of the export goes to an energy community (EEG), add **Einspeisevergütung
EEG hinzufügen** below the feed-in tariff: a fixed price, 0 is allowed. In its
card, **Zähler festlegen** sets the Home Assistant energy counter of the EEG
export (kWh or Wh). evcc then records the EEG export per quarter hour; the
standard feed-in is the total export of the grid meter minus EEG. Only
counters are used, the grid power that drives pv control, load management and
peak shaving is not touched, and self-consumption keeps being valued at the
standard tariff. The split is available via `GET /api/feedinsplit`; its display
on the new energy page follows with a later evcc version.

## 6. Shed guard (Abwurfschutz)

A protected loadpoint that load management had to switch off stays off for the
set minutes (0 to 120, 0 = off), even if the power is back earlier. Only
switching off a running load counts: a switch that loses its budget, or a
wallbox pushed below its minimum current. A load that could not start for lack
of power is not held off. Set it under **Lastmanagement-Details →
Abwurfschutz**, the minutes and a tick per loadpoint.

## 7. Overview (Mehr → Lastmanagement (Peak))

Shown once a circuit is configured. Tiles for the load management (peak)
circuit, or every circuit when none is chosen (load and limit),
peak shaving (15 minute average, allowed grid draw until the quarter hour ends,
reserve and setpoint, a limit raised by follow the peak) and battery grid
charging, the overall state beside the switch; below every load on a circuit by
priority (throttled and switched off from the bottom up), with its state and a
lock while the shed guard holds it off, and the
last 20 events (shed, throttled, peak covered, grid charging paused or
blocked). The events are kept in memory and start empty after a restart.

The switch **Lastmanagement** at the top turns load management off: the power
limit of the load management (peak) circuit (without one chosen: of all
circuits) no longer throttles wallboxes, heaters or grid charging; other
circuits, e.g. the fuse, keep theirs. Fuses (current limits), §14a and battery
peak shaving stay active. Your configuration is not changed; switching on
restores the limits. The setting survives a restart.

An exceeded power limit no longer pops up as a notification (top right), load
management handles it by shedding; it stays in the log. An exceeded current
limit (fuse) is still shown.

**Mehr → Peak Shaving** shows, per month, the highest quarter hour with the
battery (the actual grid draw) and without it (grid draw plus battery power,
charging counts negative), each with its time, and how often the battery
started covering a peak. Only quarter hours evcc saw from their start count. The
last 24 months are kept.

## 8. Battery profiles

Set up under **Lastmanagement-Details → Profile**, picked on the **Hausbatterie**
page. A profile has a name, an icon and any of these values, each with a tick:

- Netzladen: soc grid charging on/off, start soc, stop soc
- Batterienutzung: surplus to the battery first up to, battery as charging
  buffer from, start charging from, discharge lock in fast and planned charging
- Lastspitzenkappung: on/off, reserve soc, peak limit
- Wallbox: solar share per wallbox (heating devices are not offered)

Values not ticked stay as they are when switching. "Aktuelle Werte übernehmen"
fills the profile with what is set right now. Switching runs the same checks as
setting a value by hand; if one value cannot be applied, the others still are
and the battery page shows which one failed.

## 9. Advanced settings (Erweitert)

Under **Lastmanagement-Details → Erweitert**: the **Stromkreis Lastmanagement
(Peak)**, i.e. the circuit holding your peak limit beside a circuit for the fuse
(only it is shown in the overview, lifted by the switch and raised by follow the
peak; none = all circuits), the peak shaving reserve hysteresis (default 2 %),
free value written while the battery may discharge freely (10000 W), grid
charge hold-off after a peak or the circuit stopped it (5 min), reservation
expiry for waiting higher priority loads (10 min), the battery's phases for
current limits (3), the minute from which the peak shaving budget stops
growing (12) and its cap (2 × limit), and the cycles after which a
load ignoring its limit is no longer counted on (3, 0 = off), and the longest the
optimizer plans soc-based battery grid charging from the start to the stop soc
(3 h): it plans the charging time at the grid charge power, at most this;
with peak shaving as long as the room below the limit takes.

### Consumption forecast and battery identification

Under **Erweitert**, **Verbrauchsprognose → Nach Wochentag** forecasts each day
of the home consumption from the same weekday of the last 8 weeks instead of
the 28 day average (weekends differ from working days); **Sicherheitszuschlag
Verbrauch** takes a higher percentile (60-90 %) instead of the mean, so the
optimizer keeps more battery back.

**Lastmanagement-Details → Batterie-Vermessung** learns the battery's usable
capacity and round trip efficiency from the charging and discharging runs of
the last 60 days (each over 20 % soc, at least 3 each way). With **Gemessene
Werte verwenden** the optimizer plans with the measured capacity and one-time
grid charging with capacity and efficiency; implausible values are not used.

## 10. Optimizer

The optimizer (Konfiguration → Experimentell and Optimizer, needs a sponsor
token) gets the settings above as inputs, so its plan, the battery soc forecast
and its suggestions match what evcc does: the peak limit as grid import limit,
the peak reserve and the start soc of soc-based grid charging as minimum soc,
the charge to the stop soc once charged, from now while it runs and else from
where the battery is expected to fall to the start soc: from there the
optimizer plans the rest again, starting with that charge, so the forecast
shows the discharge to the start soc and the grid charge to the stop soc (only
while it is switched on), a one-time grid charge as goal, a loadpoint's
circuit power as its limit and the priorities.

With peak shaving the forecast follows the reserve as evcc runs it: where the
plan would go over the limit while the battery holds the reserve, it is planned
again and the battery covers the part above the limit below the reserve, down
to its own minimum soc; what charges below the reserve (pv surplus, running or
one-time grid charging) stays there for peaks. Without peaks it stops at the
reserve. Grid charging is planned slot by slot as evcc charges, only with the room below
the limit, and pauses while the demand exceeds it (switched grid charging
without a charge power entity draws its full power, also in the forecast). A
start or stop of grid charging plans again right away. It can run locally: install the
addon **evcc optimizer** and set **OPTIMIZER_URI** to its address, e.g.
`http://localhost:7050` on the same host.

**Planning price.** With a real grid price close to the feed-in price (e.g.
10 ct vs 9 ct) the optimizer never discharges the battery: its losses
make stored energy worth more than the saving. Add a planner tariff (Tarife →
Vorhersage hinzufügen → Planer-Vorhersage → fixed price) of at least 1.25 ×
the feed-in price, e.g. 12 ct: the optimizer plans with it, statistics and
costs keep the grid tariff. Note that the planner tariff also drives vehicle
charge plans, so do not use a fixed one together with a dynamic grid tariff.

## Requirements

The battery needs `modeNormal` and `modeCharge` scripts configured on the Home
Assistant battery meter, otherwise evcc cannot control it at all and the grid
charging features stay hidden.

## Running alongside the official addon

Both can be installed at the same time, but not started at the same time: they
bind the same ports and would fight over the same devices. Keep `sqlite_file`
and `config_file` pointing at separate paths so they do not share state.

## Source

Built from https://github.com/SolarPower2024/evcc, branch `load-peak-features`.
See `core/lm/README.md` there for the implementation details and the list of
upstream files that were touched.
