"""Further cases of the integration: signs, restore, sign of life, availability,
release paths, status, write rate, several entries.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from custom_components.evcc_peak_fronius import controller as controller_module
from custom_components.evcc_peak_fronius.const import (
    CONF_BATTERY_INVERT,
    CONF_GRID_INVERT,
    CONF_RESET_BUTTON,
    DOMAIN,
)

from .conftest import DISCHARGE, ENTRY_DATA, GRID_CHARGE, MODE, FakeFronius
from .test_controller import PREFIX, START, evcc, setup, status, tick


def entry_with(**data: Any) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="evcc Peak Fronius",
        unique_id=MODE,
        data={**ENTRY_DATA, **data},
    )


async def test_inverted_signs(
    hass: HomeAssistant, fronius: FakeFronius, freezer: FrozenDateTimeFactory
) -> None:
    """Grid export positive and battery charging positive, both inverted."""
    await setup(hass, entry_with(**{CONF_GRID_INVERT: True, CONF_BATTERY_INVERT: True}), freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(-3000, -500, 15)  # import 3000, discharge 500
    await tick(hass, freezer)
    assert fronius.take() == [("mode", "Discharge Limit"), (DISCHARGE, 1500)]


async def test_restore_after_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Switch, threshold, request and grid charge power come back after a
    restart, the limit does not: it is the sign of life of evcc.
    """
    number = {"native_min_value": 0, "native_step": 1, "native_unit_of_measurement": None}
    mock_restore_cache_with_extra_data(
        hass,
        [
            (State(f"switch.{PREFIX}_peak_shaving", "on"), {}),
            (State(f"select.{PREFIX}_request", "hold"), {}),
            (
                State(f"number.{PREFIX}_soc_threshold", "35"),
                {**number, "native_value": 35, "native_max_value": 100},
            ),
            (
                State(f"number.{PREFIX}_grid_charge_power", "1500"),
                {**number, "native_value": 1500, "native_max_value": 100000},
            ),
            (
                State(f"number.{PREFIX}_limit", "2000"),
                {**number, "native_value": 2000, "native_max_value": 100000},
            ),
        ],
    )
    await setup(hass, mock_config_entry, freezer)
    assert hass.states.get(f"switch.{PREFIX}_peak_shaving").state == "on"
    assert hass.states.get(f"select.{PREFIX}_request").state == "hold"
    assert float(hass.states.get(f"number.{PREFIX}_soc_threshold").state) == 35
    assert float(hass.states.get(f"number.{PREFIX}_grid_charge_power").state) == 1500
    assert float(hass.states.get(f"number.{PREFIX}_limit").state) == 0
    assert status(hass) == "no_evcc"
    assert fronius.take() == []


async def test_write_in_the_grace_keeps_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Evcc writes the limit again within the 2 minutes: no release."""
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    await tick(hass, freezer)
    fronius.take()
    freezer.move_to("2026-10-25 12:15:40+00:00")
    await tick(hass, freezer, 1)
    await evcc(hass, limit=2000)
    freezer.move_to("2026-10-25 12:17:30+00:00")
    await tick(hass, freezer, 3)
    assert ("mode", "Auto") not in fronius.take()
    assert status(hass) == "free"


async def test_unavailable_number_waits(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """fronius_modbus shows the discharge limit unavailable until the mode is
    there: nothing is written to it before.
    """
    fronius.numbers_follow_mode = False
    hass.states.async_set(DISCHARGE, STATE_UNAVAILABLE)
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(3000, 500, 15)
    await tick(hass, freezer)
    await tick(hass, freezer)
    assert fronius.take() == [("mode", "Discharge Limit")]
    fronius.set_number(DISCHARGE, 10000, 10000)
    await tick(hass, freezer)
    assert fronius.take() == [(DISCHARGE, 1500)]


async def test_no_evcc_while_grid_charging(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Evcc gone while grid charging: charge power 0 first, then Auto."""
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, grid_charge=3000, request="grid_charge", limit=2000)
    await tick(hass, freezer, 5)
    assert fronius.take() == [("mode", "Charge from Grid"), (GRID_CHARGE, 3000)]
    freezer.move_to("2026-10-25 12:17:01+00:00")
    await tick(hass, freezer, 3)
    assert fronius.take() == [(GRID_CHARGE, 0)]
    await tick(hass, freezer, 3)
    assert fronius.take() == [("mode", "Auto")]


async def test_status_attributes_and_daily_count(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(3000, 500, 15)
    await tick(hass, freezer)
    attrs = hass.states.get(f"sensor.{PREFIX}_status").attributes
    assert attrs["discharge_target"] == 1500
    assert attrs["owned"] is True
    assert attrs["writes_today"] == 2  # mode and discharge limit

    freezer.tick(timedelta(days=1))
    await evcc(hass, limit=2000)
    fronius.measure(4000, 1500, 15)
    await tick(hass, freezer)
    attrs = hass.states.get(f"sensor.{PREFIX}_status").attributes
    # only the writes of the new day: the hand back after a day without evcc and
    # the mode once evcc writes again
    assert attrs["writes_today"] == 2


async def test_free_status_has_no_target(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    await tick(hass, freezer)
    attrs = hass.states.get(f"sensor.{PREFIX}_status").attributes
    assert attrs["discharge_target"] is None  # the maximum is not a number to show


async def test_one_write_per_two_seconds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The mode and the limit are not written in the same second."""
    await setup(hass, mock_config_entry, freezer)
    fronius.measure(3000, 500, 15)
    await evcc(hass, threshold=20, on=True, limit=2000)
    assert fronius.take() == [("mode", "Discharge Limit")]
    await tick(hass, freezer, 1)
    assert fronius.take() == []
    await tick(hass, freezer, 1.5)
    assert fronius.take() == [(DISCHARGE, 1500)]


async def test_stale_mode_without_reset_button(
    hass: HomeAssistant, fronius: FakeFronius, freezer: FrozenDateTimeFactory
) -> None:
    """Without a reset button the mode is written again every 10 s, nothing pressed."""
    fronius.mode_follows = False
    await setup(hass, entry_with(**{CONF_RESET_BUTTON: None}), freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    calls: list[tuple[str, Any]] = fronius.take()
    for _ in range(5):
        await tick(hass, freezer, 11)
        calls += fronius.take()
    assert ("reset", None) not in calls
    assert calls.count(("mode", "Discharge Limit")) == 6


async def test_foreign_mode_left_alone_at_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A Discharge Limit set by someone else is not handed back without evcc."""
    fronius.set_mode("Discharge Limit")
    await setup(hass, mock_config_entry, freezer)
    await tick(hass, freezer, 10)
    assert fronius.take() == []


async def test_owned_mark_is_stored(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    await tick(hass, freezer, 1)
    assert hass_storage[f"{DOMAIN}.{mock_config_entry.entry_id}"]["data"] == {"owned": True}


async def test_two_entries_get_their_own_ids(
    hass: HomeAssistant, fronius: FakeFronius, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(START)
    hass.states.async_set("input_select.second_mode", "Auto", {"options": ["Auto"]})
    for unique, mode in (("a", MODE), ("b", "input_select.second_mode")):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="evcc Peak Fronius",
            unique_id=unique,
            data={**ENTRY_DATA, "mode": mode},
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get(f"switch.{PREFIX}_peak_shaving") is not None
    assert hass.states.get(f"switch.{PREFIX}_peak_shaving_2") is not None


async def test_unload_during_grid_charge(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading while grid charging: charge power 0, then Auto."""
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, grid_charge=3000, request="grid_charge", limit=2000)
    await tick(hass, freezer, 5)
    fronius.take()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert fronius.take() == [(GRID_CHARGE, 0), ("mode", "Auto")]


async def test_unload_keeps_mark_when_mode_unavailable(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
    caplog: Any,
) -> None:
    """The mode cannot be written at the unload: the mark stays, the next start
    hands back.
    """
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    await tick(hass, freezer)
    fronius.take()
    hass.states.async_set(MODE, STATE_UNAVAILABLE)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert fronius.take() == []
    assert "Mode not handed back" in caplog.text
    assert hass_storage[f"{DOMAIN}.{mock_config_entry.entry_id}"]["data"] == {"owned": True}


async def test_unload_keeps_mark_when_the_write_fails(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
    caplog: Any,
) -> None:
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    await tick(hass, freezer)

    async def broken(call: Any) -> None:
        raise ValueError("Modbus closed")

    hass.services.async_register("input_select", "select_option", broken)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert "Mode not handed back to Auto" in caplog.text
    assert hass_storage[f"{DOMAIN}.{mock_config_entry.entry_id}"]["data"] == {"owned": True}


async def test_write_works_again_is_logged(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
    caplog: Any,
) -> None:
    fail = {"on": True}

    async def flaky(call: Any) -> None:
        if fail["on"]:
            raise ValueError("busy")
        fronius.calls.append((call.data["entity_id"], float(call.data["value"])))

    hass.services.async_register("input_number", "set_value", flaky)
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(3000, 500, 15)
    await tick(hass, freezer)
    fail["on"] = False
    await tick(hass, freezer, 5)
    assert "works again" in caplog.text
    assert fronius.take()[-1] == (DISCHARGE, 1500)


async def test_failing_mode_write_backs_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    tries: list[str] = []

    async def broken(call: Any) -> None:
        tries.append(call.data["option"])
        raise ValueError("busy")

    hass.services.async_register("input_select", "select_option", broken)
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    for _ in range(10):  # 30 s
        await tick(hass, freezer)
    # every 10 s at most, and with the growing gap after a failure
    assert 2 <= len(tries) <= 4


async def test_options_change_reloads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup(hass, mock_config_entry, freezer)
    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_GRID_INVERT: True})
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.grid_invert is True


async def test_evaluations_are_coalesced(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
    monkeypatch: Any,
) -> None:
    """Many state events at once: one evaluation with the latest values."""
    await setup(hass, mock_config_entry, freezer)
    controller = mock_config_entry.runtime_data
    count = {"n": 0}
    evaluate = controller.async_evaluate

    async def counted() -> None:
        count["n"] += 1
        await evaluate()

    monkeypatch.setattr(controller, "async_evaluate", counted)
    monkeypatch.setattr(controller_module, "MIN_EVAL_GAP_S", 0.2)
    freezer.tick(timedelta(seconds=5))  # long after the last evaluation
    for grid in range(10):
        hass.states.async_set("sensor.meter_power", str(1000 + grid))
    await asyncio.sleep(0)
    freezer.tick(timedelta(seconds=1))  # the gap has passed for the follow-up
    await hass.async_block_till_done()
    assert count["n"] == 1
