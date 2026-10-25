"""Select: the request of evcc (normal, grid charging, hold)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import PeakConfigEntry
from .const import KEY_REQUEST, REQUESTS
from .entity import PeakEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: PeakConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the select."""
    async_add_entities(
        [
            PeakRequest(
                entry.runtime_data, SelectEntityDescription(key=KEY_REQUEST, options=REQUESTS)
            )
        ]
    )


class PeakRequest(PeakEntity, SelectEntity, RestoreEntity):
    """What evcc wants from the battery besides peak shaving."""

    async def async_added_to_hass(self) -> None:
        """Restore the last request."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None and last.state in REQUESTS:
            self.controller.request = last.state

    @property
    def current_option(self) -> str:
        """Return the request."""
        return self.controller.request

    async def async_select_option(self, option: str) -> None:
        """Take a request from evcc."""
        self.controller.set_request(option)
        self.async_write_ha_state()
