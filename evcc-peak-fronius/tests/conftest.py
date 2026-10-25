"""Fixtures: a fake fronius_modbus made of states and recording services.

The targets live in the ``input_select`` and ``input_number`` domains, which
the tests do not load, so their services can be faked here; the integration
calls the service of the entity's own domain.
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

import pytest

try:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
except ImportError:
    collect_ignore = ["test_controller.py", "test_config_flow.py"]
else:
    from homeassistant.core import HomeAssistant, ServiceCall

    from custom_components.evcc_peak_fronius import controller as controller_module
    from custom_components.evcc_peak_fronius.const import (
        CONF_BATTERY_POWER,
        CONF_DISCHARGE_LIMIT,
        CONF_GRID_CHARGE,
        CONF_GRID_POWER,
        CONF_MODE,
        CONF_RESET_BUTTON,
        CONF_SOC,
        DEFAULT_NAME,
        DOMAIN,
    )

    pytest_plugins = "pytest_homeassistant_custom_component"

    MODE_OPTIONS = [
        "Auto",
        "PV Charge Limit",
        "Discharge Limit",
        "PV Charge and Discharge Limit",
        "Charge from Grid",
        "Discharge to Grid",
        "Block Discharging",
        "Block Charging",
    ]
    GRID = "sensor.meter_power"
    BATTERY = "sensor.battery_power"
    SOC = "sensor.battery_soc"
    MODE = "input_select.storage_control_mode"
    DISCHARGE = "input_number.discharge_limit"
    GRID_CHARGE = "input_number.grid_charge_power"
    RESET = "input_button.reset_modbus_control"

    ENTRY_DATA = {
        CONF_GRID_POWER: GRID,
        CONF_BATTERY_POWER: BATTERY,
        CONF_SOC: SOC,
        CONF_MODE: MODE,
        CONF_DISCHARGE_LIMIT: DISCHARGE,
        CONF_GRID_CHARGE: GRID_CHARGE,
        CONF_RESET_BUTTON: RESET,
    }

    @dataclass
    class FakeFronius:
        """The fronius_modbus entities and the calls the integration made."""

        hass: HomeAssistant
        calls: list[tuple[str, Any]] = field(default_factory=list)
        #: When False the mode select ignores writes (a stale mode).
        mode_follows: bool = True
        #: When False the numbers keep showing their value after a mode change,
        #: as fronius_modbus until its next scan.
        numbers_follow_mode: bool = True

        def set_mode(self, mode: str) -> None:
            self.hass.states.async_set(MODE, mode, {"options": MODE_OPTIONS})

        def set_number(self, entity: str, value: float, maximum: float) -> None:
            self.hass.states.async_set(entity, str(value), {"min": 0, "max": maximum, "step": 1})

        def measure(self, grid: float, battery: float, soc: float) -> None:
            self.hass.states.async_set(GRID, str(grid), force_update=True)
            self.hass.states.async_set(BATTERY, str(battery))
            self.hass.states.async_set(SOC, str(soc))

        def take(self) -> list[tuple[str, Any]]:
            calls, self.calls = self.calls, []
            return calls

        def register(self) -> None:
            async def select_option(call: ServiceCall) -> None:
                option = call.data["option"]
                self.calls.append(("mode", option))
                if self.mode_follows:
                    self.set_mode(option)
                    if self.numbers_follow_mode:
                        # fronius_modbus puts the limits back after a mode change
                        self.set_number(DISCHARGE, 10000, 10000)
                        self.set_number(GRID_CHARGE, 0, 5000)

            async def set_value(call: ServiceCall) -> None:
                entity = call.data["entity_id"]
                entity = entity[0] if isinstance(entity, list) else entity
                value = float(call.data["value"])
                self.calls.append((entity, value))
                self.set_number(entity, value, 10000 if entity == DISCHARGE else 5000)

            async def press(call: ServiceCall) -> None:
                self.calls.append(("reset", None))
                self.mode_follows = True

            self.hass.services.async_register("input_select", "select_option", select_option)
            self.hass.services.async_register("input_number", "set_value", set_value)
            self.hass.services.async_register("input_button", "press", press)

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(enable_custom_integrations: None) -> Generator[None]:
        """Load the custom integration in every test."""
        yield

    @pytest.fixture(autouse=True)
    def no_eval_gap(monkeypatch: pytest.MonkeyPatch) -> None:
        """Evaluate right away: the tests move the frozen clock themselves."""
        monkeypatch.setattr(controller_module, "MIN_EVAL_GAP_S", 0)

    @pytest.fixture
    def fronius(hass: HomeAssistant) -> FakeFronius:
        """Return the fake fronius_modbus in its starting state (Auto)."""
        fake = FakeFronius(hass)
        fake.register()
        fake.set_mode("Auto")
        fake.set_number(DISCHARGE, 10000, 10000)
        fake.set_number(GRID_CHARGE, 0, 5000)
        hass.states.async_set(RESET, "unknown")
        fake.measure(1000, 0, 50)
        return fake

    @pytest.fixture
    def mock_config_entry() -> MockConfigEntry:
        """Return the config entry of one inverter."""
        return MockConfigEntry(
            domain=DOMAIN,
            title=DEFAULT_NAME,
            unique_id=MODE,
            entry_id="01J0000000000000000000PEAK",
            data=dict(ENTRY_DATA),
        )
