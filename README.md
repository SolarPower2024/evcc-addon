# evcc custom Home Assistant addon

A private addon repository for a customised evcc build.

## Install

Home Assistant → Settings → Add-ons → Add-on Store → ⋮ → Repositories → add:

```
https://github.com/SolarPower2024/evcc-addon
```

Then install **evcc custom** from the store, and optionally **evcc optimizer** to
run the optimizer locally instead of the cloud service (see
[evcc-optimizer/DOCS.md](evcc-optimizer/DOCS.md)).

## What is different from the official addon

Additions for load management (priorities, battery, switch devices, heater in
stages, shed guard, overview), battery grid charging by soc and one-time, peak
shaving for a capacity tariff, battery profiles, consumption forecast, battery
identification, a second feed-in tariff (EEG) and 1p/3p current limits. All
inert until configured, all set up in the ui. See
[evcc-custom/DOCS.md](evcc-custom/DOCS.md).

The image is built from [SolarPower2024/evcc](https://github.com/SolarPower2024/evcc)
and published to `ghcr.io/solarpower2024/evcc-custom`.

## Releasing a new version

1. In the evcc fork, tag the commit: `git tag v<evcc version>-lmN && git push origin v<evcc version>-lmN`
2. Wait for the *Custom image* workflow to push `ghcr.io/solarpower2024/evcc-custom:<evcc version>-lmN`
3. Here, bump `version:` in `evcc-custom/config.yaml` to `<evcc version>-lmN`, add its changelog entry and push

Home Assistant then offers the update.
