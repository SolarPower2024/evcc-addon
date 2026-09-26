# evcc optimizer

Runs the evcc optimizer locally in Home Assistant, so the **evcc custom** addon
does not need the cloud optimizer. The optimizer plans battery and vehicle
charging from prices, the pv forecast and the household demand.

This addon contains no code of its own: it runs the official optimizer image
(`evcc/optimizer`) in a fixed version.

## Setup

1. Install and start **evcc optimizer**.
2. In the **evcc custom** addon configuration set **Optimizer API Endpoint
   (OPTIMIZER_URI)** to `http://localhost:7050` and restart evcc custom.
3. In evcc the optimizer still needs a sponsor token and, under
   Konfiguration, **Experimentell** and the **Optimizer** switched on, exactly
   as with the cloud service.

Both addons use the host network, so nothing else needs to be connected. Port
7050 must be free: do not run a second optimizer addon at the same time.

## Version

`version` in `config.yaml` is the build date of the pinned optimizer image, the
image tag in `Dockerfile` its build. Both are bumped together when evcc custom
moves to an evcc version that expects a newer optimizer.

Current pin: build of 2026-09-14. evcc 0.316 was built against the optimizer
interface of 2026-09-17, which only adds `c_active` (a vehicle already charging
at the start of the plan). This build ignores the field, so a running charge
is not treated as already started; everything else works.

## Resources

The optimizer solves each request within 10 seconds (the image default) with
four worker processes. On a Raspberry Pi the first requests may take a few
seconds.
