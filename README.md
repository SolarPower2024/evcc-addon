# evcc custom Home Assistant addon

A private addon repository for a customised evcc build.

## Install

Home Assistant → Settings → Add-ons → Add-on Store → ⋮ → Repositories → add:

```
https://github.com/SolarPower2024/evcc-addon
```

Then install **evcc custom** from the store.

## What is different from the official addon

Three additions, all inert until configured: priority-based load shedding
(`lmpriority`), the home battery as a load management participant, and
soc-based grid charging. See [evcc-custom/DOCS.md](evcc-custom/DOCS.md).

The image is built from [SolarPower2024/evcc](https://github.com/SolarPower2024/evcc)
and published to `ghcr.io/solarpower2024/evcc-custom`.

## Releasing a new version

1. In the evcc fork, tag the commit: `git tag v0.315.0-lm2 && git push origin v0.315.0-lm2`
2. Wait for the *Custom image* workflow to push `ghcr.io/solarpower2024/evcc-custom:0.315.0-lm2`
3. Here, bump `version:` in `evcc-custom/config.yaml` to `0.315.0-lm2` and push

Home Assistant then offers the update.
