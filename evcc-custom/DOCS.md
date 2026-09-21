# evcc custom

evcc with three additions on top of upstream. All of them are inert until
configured, so this behaves like the official addon until you switch something on.

## 1. Load management priorities

`lmpriority` per loadpoint decides who gives way when a circuit runs out of
budget. **Lower is shed first.** It is separate from `priority`, which
distributes pv surplus, because the load that should get sun first is usually
not the one that should keep power when the fuse is the constraint.

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

## 2. Battery in load management

The home battery's grid charging power counts against a circuit and is switched
off when the budget runs out.

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
