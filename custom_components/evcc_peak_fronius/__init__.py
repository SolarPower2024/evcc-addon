"""evcc Peak Fronius.

Peak shaving for a Fronius GEN24 battery (e.g. BYD) through fronius_modbus.
evcc sets the inputs (on/off, allowed grid power, soc threshold, request);
the integration narrows the discharge limit within seconds. Fronius keeps
regulating self consumption itself.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .controller import PeakController

type PeakConfigEntry = ConfigEntry[PeakController]


async def async_setup_entry(hass: HomeAssistant, entry: PeakConfigEntry) -> bool:
    """Set up peak shaving for one inverter."""
    controller = PeakController(hass, entry)
    await controller.async_load()
    entry.runtime_data = controller

    # The platforms first: the restorable entities hand their last value to
    # the controller before it evaluates for the first time.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    controller.async_start()

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PeakConfigEntry) -> bool:
    """Stop controlling and hand the battery back to Fronius."""
    await entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: PeakConfigEntry) -> None:
    """Reload the entry after its options changed."""
    await hass.config_entries.async_reload(entry.entry_id)
