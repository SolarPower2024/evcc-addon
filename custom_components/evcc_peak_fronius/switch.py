"""Switch: peak shaving on or off (set by evcc)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import PeakConfigEntry
from .const import KEY_PEAK_SHAVING
from .entity import PeakEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: PeakConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the switch."""
    async_add_entities(
        [PeakSwitch(entry.runtime_data, SwitchEntityDescription(key=KEY_PEAK_SHAVING))]
    )


class PeakSwitch(PeakEntity, SwitchEntity, RestoreEntity):
    """Peak shaving on/off."""

    async def async_added_to_hass(self) -> None:
        """Restore the last state."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.controller.enabled = last.state == STATE_ON

    @property
    def is_on(self) -> bool:
        """Return whether peak shaving is on."""
        return self.controller.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn peak shaving on."""
        self.controller.set_enabled(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn peak shaving off."""
        self.controller.set_enabled(False)
        self.async_write_ha_state()
