# evcc custom

evcc with a few additions on top of upstream. All of them are inert until
configured, so this behaves like the official addon until you switch something on.

Everything is configured in the evcc ui under **Konfiguration →
Lastmanagement-Details** (Batterie-Stromkreis, Prioritäten, Netzladen, Peak
Shaving) and on the **Hausbatterie** page (switches, limits, soc values).

## 1. Load management priorities

The shed priority per loadpoint decides who gives way when a circuit runs out of
budget. **Lower is shed first.** It is separate from `priority`, which
distributes pv surplus, because the load that should get sun first is usually
not the one that should keep power when the fuse is the constraint.

Set it under **Lastmanagement-Details → Prioritäten**, 0 to 10 for every
loadpoint on a circuit and for the home battery once it is assigned to one.
Changes apply immediately. Loads without a circuit do not take part and are not
listed.

The `lmpriority` key of a loadpoint in `evcc.yaml` is only the fallback for a
load that has no value set in the ui:

```yaml
loadpoints:
  - title: Wallbox
    charger: wallbox
    circuit: main
    priority: 5      # pv surplus goes here first
    lmpriority: 1    # ... but this is reduced first

  - title: Heizstab
    charger: ha-switch-heater
    circuit: main
    lmpriority: 2

  - title: Wärmepumpe
    charger: ha-switch-heatpump
    circuit: main
    lmpriority: 5    # keeps its power the longest
```

Loads only take part when they sit on a `circuit`. Without differing
priorities nothing changes versus upstream.

Recovery uses the same mechanism in reverse: power that frees up stays withheld
from lower-priority loads for as long as someone above still reports unmet
demand. Each rung costs one update cycle, and evcc updates one loadpoint per
cycle, so a full shed or recovery takes up to `interval x loadpoints`.

**Overload** is shed from the bottom: a load keeps what it draws as long as the
loads below it draw enough to cover the excess.

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

Under **Netzladen** you choose how the battery charges from the grid:

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

## 4. Peak shaving

Caps the grid demand peak a demand charge (Leistungspreis) is billed on, by
holding the battery's lower soc range back as a reserve.

Configure it on the **Hausbatterie** page: a switch, the peak limit (2–20 kW in
0.5 kW steps) and the reserve soc.

| Battery soc | Behaviour | Value written to the entity |
| --- | --- | --- |
| above the reserve | ordinary self-consumption | `10000` (discharge freely) |
| below the reserve | peaks only | `max(0, demand − limit)` in W |
| charging from the grid | no discharging | `0` |

evcc only computes the setpoint. The Home Assistant automation reading the
entity does the actual discharging.

The target entity is set under **Lastmanagement-Details → Peak Shaving**, just
the entity id, for example `input_number.battery_peak_power`. Running as this
add-on, evcc reaches Home Assistant through the supervisor, so no url and no
token are needed. The entity needs **min 0, max at least 10000 and step 1**,
otherwise Home Assistant rejects the values.

Everything is written in watts; only the limit is shown in kW.

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

### What this does not do

The setpoint is derived from instantaneous power, not from the energy already
consumed in the running 15 minute window. That is safe — the instantaneous value
never exceeds the limit, so neither does the average — but it spends battery on
short spikes that barely move the 15 minute average. The card shows that average
so the effect can be judged before deciding whether window-aware rationing is
worth the added complexity.

## 5. OeMAG feed-in tariff

Add it under **Tarife & Vorhersagen → Einspeisevergütung hinzufügen**, provider
**OeMAG Marktpreis (Einspeisung)**. A restart applies it, like any tariff.

OeMAG publishes a month's market price only in the following month. Until then
the latest published value is the running feed-in price, for display and for
all calculations. On the **Stichtag Neuberechnung** (default 15th) that value
becomes the final price of the previous month, and evcc recalculates once:

- the stored 15 minute feed-in rates of the previous month
- the price of the previous month's charging sessions: their solar share is
  valued at the feed-in price, so it is revalued from the provisional to the
  final price

Each month is recalculated exactly once. If evcc is not running on that day it
catches up on the next start within the month. Sessions from a time evcc did not
store feed-in rates for are left unchanged. The log shows a line like
`feed-in 2026-08 finalized at 0.08997/kWh: … recalculated`.

The price comes from an unofficial scraper
(github.com/chrsbrmr/oemag-marktpreis). Values that are missing, not in EUR/kWh
or outside 0 to 1 EUR/kWh are ignored and the last good value is kept.

## Requirements

The battery needs `modeNormal` and `modeCharge` scripts configured on the Home
Assistant battery meter, otherwise evcc cannot control it at all and the grid
charging features stay hidden.

## Running alongside the official addon

Both can be installed at the same time, but not started at the same time: they
bind the same ports and would fight over the same devices. Keep `sqlite_file`
and `config_file` pointing at separate paths so they do not share state.

## Source

Built from https://github.com/SolarPower2024/evcc, branch `loadmanagement`.
See `core/lm/README.md` there for the implementation details and the list of
upstream files that were touched.
