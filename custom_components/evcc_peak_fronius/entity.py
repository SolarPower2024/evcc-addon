"""Base entity of evcc Peak Fronius."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN
from .controller import PeakController


class PeakEntity(Entity):
    """Common base: device, naming, controller updates.

    Home Assistant builds the entity ids from the English names, whatever its
    language: evcc's placeholders and the docs name these ids.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: PeakController, description: EntityDescription) -> None:
        """Bind the entity to the controller."""
        self.controller = controller
        self.entity_description = description
        self._attr_translation_key = description.key
        entry = controller.entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="evcc fork",
            model="Peak shaving Fronius",
        )

    async def async_added_to_hass(self) -> None:
        """Follow the controller."""
        await super().async_added_to_hass()
        self.async_on_remove(self.controller.async_add_listener(self.async_write_ha_state))
