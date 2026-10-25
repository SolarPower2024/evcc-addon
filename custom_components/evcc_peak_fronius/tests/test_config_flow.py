"""Tests of the config and options flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.evcc_peak_fronius.const import (
    CONF_GRID_INVERT,
    CONF_MODE,
    CONF_RESET_BUTTON,
    DOMAIN,
)

from .conftest import ENTRY_DATA, MODE, FakeFronius


async def test_user_flow_creates_entry(hass: HomeAssistant, fronius: FakeFronius) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.evcc_peak_fronius.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], dict(ENTRY_DATA))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "evcc Peak Fronius"
    assert result["data"][CONF_MODE] == MODE


async def test_user_flow_rejects_select_without_modes(
    hass: HomeAssistant, fronius: FakeFronius
) -> None:
    hass.states.async_set(MODE, "Auto", {"options": ["Auto", "Charge", "Discharge"]})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], dict(ENTRY_DATA))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MODE: "mode_options"}


async def test_options_flow(
    hass: HomeAssistant, fronius: FakeFronius, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    with patch("custom_components.evcc_peak_fronius.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {**ENTRY_DATA, CONF_GRID_INVERT: True}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_GRID_INVERT] is True


async def test_options_flow_clears_reset_button(
    hass: HomeAssistant, fronius: FakeFronius, mock_config_entry: MockConfigEntry
) -> None:
    """A cleared optional field stays cleared, it does not come back from the setup."""
    mock_config_entry.add_to_hass(hass)
    data = {k: v for k, v in ENTRY_DATA.items() if k != CONF_RESET_BUTTON}
    with patch("custom_components.evcc_peak_fronius.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(result["flow_id"], data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    conf = {**mock_config_entry.data, **mock_config_entry.options}
    assert conf[CONF_RESET_BUTTON] is None


async def test_user_flow_aborts_for_a_configured_inverter(
    hass: HomeAssistant, fronius: FakeFronius, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], dict(ENTRY_DATA))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_rejects_select_without_modes(
    hass: HomeAssistant, fronius: FakeFronius, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    hass.states.async_set(MODE, "Auto", {"options": ["Auto"]})
    with patch("custom_components.evcc_peak_fronius.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], dict(ENTRY_DATA)
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MODE: "mode_options"}
