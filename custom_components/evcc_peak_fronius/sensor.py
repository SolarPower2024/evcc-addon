"""Sensor: what the controller does right now."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PeakConfigEntry
from .const import KEY_STATUS
from .entity import PeakEntity
from .regelung import STATUSES


async def async_setup_entry(
    hass: HomeAssistant, entry: PeakConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the status sensor."""
    async_add_entities(
        [
            PeakStatus(
                entry.runtime_data,
                SensorEntityDescription(
                    key=KEY_STATUS,
                    device_class=SensorDeviceClass.ENUM,
                    options=STATUSES,
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
            )
        ]
    )


class PeakStatus(PeakEntity, SensorEntity):
    """Status with the discharge target and the writes of the day."""

    @property
    def native_value(self) -> str:
        """Return the status."""
        return self.controller.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the details."""
        target = self.controller.discharge_target
        return {
            "discharge_target": None if target is None or math.isinf(target) else target,
            "owned": self.controller.owned,
            "writes_today": self.controller.writes_today,
        }
