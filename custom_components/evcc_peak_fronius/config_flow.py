"""Config and options flow: pick the entities of fronius_modbus."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_CHARGE_POWER,
    CONF_BATTERY_INVERT,
    CONF_BATTERY_POWER,
    CONF_DISCHARGE_LIMIT,
    CONF_GRID_CHARGE,
    CONF_GRID_INVERT,
    CONF_GRID_POWER,
    CONF_MODE,
    CONF_RESET_BUTTON,
    CONF_SOC,
    DEFAULT_NAME,
    DOMAIN,
    REQUIRED_MODES,
)

ENTITY_KEYS = (
    CONF_GRID_POWER,
    CONF_BATTERY_POWER,
    CONF_SOC,
    CONF_MODE,
    CONF_DISCHARGE_LIMIT,
    CONF_GRID_CHARGE,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the form, prefilled with ``defaults``."""

    def entity(key: str, domains: list[str], **kw: Any) -> tuple[Any, Any]:
        marker = vol.Required(key, default=defaults[key]) if key in defaults else vol.Required(key)
        return marker, selector.EntitySelector(selector.EntitySelectorConfig(domain=domains, **kw))

    def optional(key: str, domains: list[str], **kw: Any) -> tuple[Any, Any]:
        marker = vol.Optional(key, description={"suggested_value": defaults.get(key)})
        return marker, selector.EntitySelector(selector.EntitySelectorConfig(domain=domains, **kw))

    fields = dict(
        [
            entity(CONF_GRID_POWER, ["sensor"], device_class="power"),
            (
                vol.Optional(CONF_GRID_INVERT, default=defaults.get(CONF_GRID_INVERT, False)),
                selector.BooleanSelector(),
            ),
            entity(CONF_BATTERY_POWER, ["sensor"], device_class="power"),
            (
                vol.Optional(CONF_BATTERY_INVERT, default=defaults.get(CONF_BATTERY_INVERT, False)),
                selector.BooleanSelector(),
            ),
            optional(CONF_BATTERY_CHARGE_POWER, ["sensor"], device_class="power"),
            entity(CONF_SOC, ["sensor"]),
            entity(CONF_MODE, ["select", "input_select"]),
            entity(CONF_DISCHARGE_LIMIT, ["number", "input_number"]),
            entity(CONF_GRID_CHARGE, ["number", "input_number"]),
            optional(CONF_RESET_BUTTON, ["button", "input_button"]),
        ]
    )
    return vol.Schema(fields)


def _validate(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Check that the mode select offers the modes the integration uses."""
    errors: dict[str, str] = {}
    state = hass.states.get(data[CONF_MODE])
    options = state.attributes.get("options", []) if state else []
    if not all(mode in options for mode in REQUIRED_MODES):
        errors[CONF_MODE] = "mode_options"
    return errors


class PeakConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up peak shaving for one inverter."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick the entities."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(self.hass, user_input)
            if not errors:
                await self.async_set_unique_id(user_input[CONF_MODE])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Change the entities later."""
        return PeakOptionsFlow()


class PeakOptionsFlow(OptionsFlow):
    """Change the picked entities."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the same form, prefilled."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(self.hass, user_input)
            if not errors:
                # an optional field cleared is missing in the input; store it
                # empty, the value of the first setup would come back otherwise
                return self.async_create_entry(
                    data={CONF_RESET_BUTTON: None, CONF_BATTERY_CHARGE_POWER: None, **user_input}
                )
        defaults = {**self.config_entry.data, **self.config_entry.options, **(user_input or {})}
        defaults.pop(CONF_NAME, None)
        return self.async_show_form(step_id="init", data_schema=_schema(defaults), errors=errors)
