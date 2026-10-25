"""Numbers set by evcc: limit, soc threshold, grid charge power."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PeakConfigEntry
from .const import KEY_GRID_CHARGE_POWER, KEY_LIMIT, KEY_SOC_THRESHOLD
from .controller import PeakController
from .entity import PeakEntity


@dataclass(frozen=True, kw_only=True)
class PeakNumberDescription(NumberEntityDescription):
    """A number of the controller."""

    value: Callable[[PeakController], float]
    set_value: Callable[[PeakController, float], None]
    #: How a restored value goes back; ``None`` for the limit: it is evcc's
    #: sign of life and starts at 0 (expired) after a restart.
    restore: Callable[[PeakController, float], None] | None = None


def _restore_threshold(c: PeakController, v: float) -> None:
    c.threshold = v


def _restore_grid_charge(c: PeakController, v: float) -> None:
    c.grid_charge_power = v


NUMBERS: tuple[PeakNumberDescription, ...] = (
    PeakNumberDescription(
        key=KEY_LIMIT,
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=100000,
        native_step=1,
        mode=NumberMode.BOX,
        value=lambda c: c.limit_shown(),
        set_value=lambda c, v: c.set_limit(v),
    ),
    PeakNumberDescription(
        key=KEY_SOC_THRESHOLD,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=5,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.BOX,
        value=lambda c: c.threshold,
        set_value=lambda c, v: c.set_threshold(v),
        restore=_restore_threshold,
    ),
    PeakNumberDescription(
        key=KEY_GRID_CHARGE_POWER,
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=100000,
        native_step=10,
        mode=NumberMode.BOX,
        value=lambda c: c.grid_charge_power,
        set_value=lambda c, v: c.set_grid_charge_power(v),
        restore=_restore_grid_charge,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: PeakConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add the numbers."""
    async_add_entities(PeakNumber(entry.runtime_data, d) for d in NUMBERS)


class PeakNumber(PeakEntity, RestoreNumber):
    """A number evcc writes."""

    entity_description: PeakNumberDescription

    async def async_added_to_hass(self) -> None:
        """Restore the last value where it survives a restart."""
        await super().async_added_to_hass()
        restore = self.entity_description.restore
        last = await self.async_get_last_number_data() if restore is not None else None
        if restore is not None and last is not None and last.native_value is not None:
            restore(self.controller, float(last.native_value))

    @property
    def native_value(self) -> float:
        """Return the value."""
        return self.entity_description.value(self.controller)

    async def async_set_native_value(self, value: float) -> None:
        """Take a value from evcc."""
        self.entity_description.set_value(self.controller, value)
        self.async_write_ha_state()
