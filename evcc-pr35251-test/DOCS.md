# PR35251 Test

Runs the official evcc test image of evcc PR 35251 (circuit limits grid import
to the month's 15-min peak). Only for testing, not for daily use.

## Separate from evcc custom

- Own addon, own database (`/data/evcc.db` of this addon). evcc custom and its
  data stay untouched.
- Both use port 7070 on the host network. **Stop evcc custom before starting
  this addon** and start evcc custom again afterwards. The addon does not start
  at boot.
- To test with the real devices: copy the `evcc.db` of evcc custom into this
  addon's data folder while both are stopped. Fork-only settings are unknown to
  this image; if it does not start, use an empty database and set up the test
  devices in the ui.

## Update

The image tag follows new builds of the PR. To get the latest build: addon →
⋮ → Rebuild.

## Remove

Uninstall the addon; its database is removed with it.
