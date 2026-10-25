"""Tests of the integration against a fake fronius_modbus."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.evcc_peak_fronius.const import DOMAIN

from .conftest import DISCHARGE, GRID_CHARGE, MODE, FakeFronius

PREFIX = "evcc_peak_fronius"
START = "2026-10-25 12:01:00+00:00"


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float = 3) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def setup(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(START)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def evcc(hass: HomeAssistant, **values: Any) -> None:
    """Write the inputs the way evcc does, through the own entities."""
    if "threshold" in values:
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": f"number.{PREFIX}_soc_threshold", "value": values["threshold"]},
            blocking=True,
        )
    if "request" in values:
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": f"select.{PREFIX}_request", "option": values["request"]},
            blocking=True,
        )
    if "grid_charge" in values:
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": f"number.{PREFIX}_grid_charge_power", "value": values["grid_charge"]},
            blocking=True,
        )
    if "on" in values:
        await hass.services.async_call(
            "switch",
            "turn_on" if values["on"] else "turn_off",
            {"entity_id": f"switch.{PREFIX}_peak_shaving"},
            blocking=True,
        )
    if "limit" in values:
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": f"number.{PREFIX}_limit", "value": values["limit"]},
            blocking=True,
        )
    await hass.async_block_till_done()


def status(hass: HomeAssistant) -> str:
    return hass.states.get(f"sensor.{PREFIX}_status").state


async def test_entities_and_idle_start(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Fixed English entity ids; without evcc nothing is written."""
    await setup(hass, mock_config_entry, freezer)
    for entity in (
        f"switch.{PREFIX}_peak_shaving",
        f"number.{PREFIX}_limit",
        f"number.{PREFIX}_soc_threshold",
        f"number.{PREFIX}_grid_charge_power",
        f"select.{PREFIX}_request",
    ):
        assert hass.states.get(entity) is not None, entity
    assert status(hass) == "no_evcc"
    await tick(hass, freezer, 10)
    assert fronius.take() == []


async def test_shaving_below_threshold(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Free above the threshold, only the excess below it, raise at once,
    lower at most every 10 s.
    """
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    assert fronius.take() == [("mode", "Discharge Limit")]
    assert status(hass) == "free"

    fronius.measure(3000, 500, 15)
    await tick(hass, freezer)
    assert fronius.take() == [(DISCHARGE, 1500)]
    assert status(hass) == "shaving"

    fronius.measure(4000, 1500, 15)  # 4000 + 1500 - 2000
    await tick(hass, freezer)
    assert fronius.take() == [(DISCHARGE, 3500)]

    fronius.measure(2500, 3500, 15)  # 2500 + 3500 - 2000 = 4000: within tolerance? no, raise
    await tick(hass, freezer)
    assert fronius.take() == [(DISCHARGE, 4000)]

    fronius.measure(1500, 1000, 15)  # 500: lower, 6 s after the last lowering
    await tick(hass, freezer)
    assert fronius.take() == []
    await tick(hass, freezer, 5)
    assert fronius.take() == [(DISCHARGE, 500)]

    fronius.measure(1500, 500, 25)  # back above threshold + hysteresis
    await tick(hass, freezer)
    assert fronius.take() == [(DISCHARGE, 10000)]
    assert status(hass) == "free"


async def test_meter_outage_frees(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(3000, 500, 15)
    await tick(hass, freezer)
    fronius.take()
    hass.states.async_set("sensor.meter_power", STATE_UNAVAILABLE)
    await tick(hass, freezer, 11)
    assert fronius.take() == [(DISCHARGE, 10000)]
    assert status(hass) == "meter_outage"


async def test_heartbeat_releases_without_evcc(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The limit shows 0 from the next quarter; without a new write the
    battery goes back to Auto 2 min later, a new write takes over again.
    """
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    await tick(hass, freezer)
    fronius.take()
    assert float(hass.states.get(f"number.{PREFIX}_limit").state) == 2000

    freezer.move_to("2026-10-25 12:15:02+00:00")
    await tick(hass, freezer, 3)
    assert float(hass.states.get(f"number.{PREFIX}_limit").state) == 0
    assert fronius.take() == []  # still in the grace

    freezer.move_to("2026-10-25 12:17:01+00:00")
    await tick(hass, freezer, 3)
    assert fronius.take() == [("mode", "Auto")]
    assert status(hass) == "no_evcc"

    await tick(hass, freezer)
    await evcc(hass, limit=2000)
    assert fronius.take() == [("mode", "Discharge Limit")]


async def test_grid_charge_and_hold(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, grid_charge=2345, request="grid_charge", limit=2000)
    assert fronius.take() == [("mode", "Charge from Grid")]
    await tick(hass, freezer, 5)
    assert fronius.take() == [(GRID_CHARGE, 2340)]
    assert status(hass) == "grid_charge"

    await tick(hass, freezer)
    await evcc(hass, request="hold")
    assert fronius.take() == [("mode", "Block Discharging")]  # peak shaving off

    await tick(hass, freezer)
    await evcc(hass, request="normal")
    assert fronius.take() == [("mode", "Auto")]
    assert status(hass) == "off"


async def test_unload_hands_back(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.take()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert fronius.take() == [("mode", "Auto")]


async def test_unload_leaves_mode_it_does_not_hold(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    fronius.set_mode("PV Charge Limit")
    await setup(hass, mock_config_entry, freezer)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert fronius.take() == []
    assert hass.states.get(MODE).state == "PV Charge Limit"


async def test_restart_hands_back_held_mode(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Held before the restart and no evcc yet: back to Auto."""
    hass_storage[f"{DOMAIN}.{mock_config_entry.entry_id}"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}.{mock_config_entry.entry_id}",
        "data": {"owned": True},
    }
    fronius.set_mode("Discharge Limit")
    await setup(hass, mock_config_entry, freezer)
    assert fronius.take() == [("mode", "Auto")]


async def test_unavailable_mode_is_not_written(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    hass.states.async_set(MODE, STATE_UNAVAILABLE)
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    await tick(hass, freezer, 15)
    assert fronius.take() == []


async def test_stale_mode_resets_modbus_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A mode that does not show is written again every 10 s; after three
    attempts the Modbus control is reset.
    """
    fronius.mode_follows = False
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    assert fronius.take() == [("mode", "Discharge Limit")]
    await tick(hass, freezer, 5)
    assert fronius.take() == []
    await tick(hass, freezer, 6)
    assert fronius.take() == [("mode", "Discharge Limit")]
    await tick(hass, freezer, 11)
    assert fronius.take() == [("mode", "Discharge Limit")]
    await tick(hass, freezer, 11)
    assert fronius.take() == [("reset", None)]
    await tick(hass, freezer, 11)
    assert fronius.take() == [("mode", "Discharge Limit")]
    assert hass.states.get(MODE).state == "Discharge Limit"


async def test_write_failure_does_not_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
    caplog: Any,
) -> None:
    """A failing write is logged once and tried again."""

    async def broken(call: Any) -> None:
        raise ValueError("Discharge limit cannot be changed in the current storage mode")

    hass.services.async_register("input_number", "set_value", broken)
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(3000, 500, 15)
    await tick(hass, freezer)
    await tick(hass, freezer)
    assert caplog.text.count("Write input_number.discharge_limit failed") == 1
    assert status(hass) == "shaving"


async def test_release_frees_the_limit_before_auto(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Peak shaving off: first the discharge limit to the maximum, then Auto, so
    a mode that does not change still leaves the battery free.
    """
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(3000, 500, 15)
    await tick(hass, freezer)
    assert fronius.take() == [("mode", "Discharge Limit"), (DISCHARGE, 1500)]
    await tick(hass, freezer)
    await evcc(hass, on=False)
    assert fronius.take() == [(DISCHARGE, 10000)]
    await tick(hass, freezer)
    assert fronius.take() == [("mode", "Auto")]


async def test_numbers_written_after_own_mode_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The number entity can still show the value of before the mode change:
    the integration writes it once anyway.
    """
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(1000, 0, 15)  # nothing to cover: discharge 0
    await tick(hass, freezer)
    assert fronius.take() == [("mode", "Discharge Limit"), (DISCHARGE, 0)]
    fronius.numbers_follow_mode = False
    await tick(hass, freezer)
    await evcc(hass, on=False, request="hold")  # hold without peak shaving: block
    assert fronius.take() == [("mode", "Block Discharging")]
    await tick(hass, freezer)
    await evcc(hass, on=True)  # still held: no change of the mode
    await evcc(hass, request="normal")
    assert fronius.take() == [("mode", "Discharge Limit")]
    await tick(hass, freezer)
    # the entity still shows 0 as before the change, the target is 0 as well
    assert fronius.take() == [(DISCHARGE, 0)]
    await tick(hass, freezer, 5)
    assert fronius.take() == []


async def test_raise_below_tolerance_is_written(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(3000, 500, 15)
    await tick(hass, freezer)
    fronius.take()
    fronius.measure(3040, 1500, 15)  # 2540 -> raise of 1040, then 20 more
    await tick(hass, freezer)
    fronius.take()
    fronius.measure(3020, 2540, 15)  # 3560: +1020
    await tick(hass, freezer)
    fronius.take()
    fronius.measure(1040, 3560, 15)  # 2600: lower by 960, rate limited
    await tick(hass, freezer)
    fronius.take()
    fronius.measure(2020, 3560, 15)  # 3580: +20 above 3560 shown
    await tick(hass, freezer)
    assert fronius.take() == [(DISCHARGE, 3580)]


async def test_limit_zero_by_hand_releases(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    await tick(hass, freezer)
    fronius.take()
    await tick(hass, freezer)
    await evcc(hass, limit=0)
    assert fronius.take() == [("mode", "Auto")]
    assert status(hass) == "no_evcc"


async def test_limit_starts_expired_after_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    await setup(hass, mock_config_entry, freezer)
    assert float(hass.states.get(f"number.{PREFIX}_limit").state) == 0


async def test_home_assistant_stop_hands_back(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
    caplog: Any,
) -> None:
    """Home Assistant stops: back to Auto, without a listener error."""
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(3000, 500, 15)
    await tick(hass, freezer)
    fronius.take()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert fronius.take() == [(DISCHARGE, 10000), ("mode", "Auto")]
    assert "Unable to remove unknown job listener" not in caplog.text


async def test_failing_write_backs_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A write that keeps failing is tried again 4, 8, 16 … s apart."""
    tries: list[float] = []

    async def broken(call: Any) -> None:
        tries.append(call.data["value"])
        raise ValueError("Discharge limit cannot be changed in the current storage mode")

    hass.services.async_register("input_number", "set_value", broken)
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(3000, 500, 15)
    for _ in range(20):  # 60 s
        await tick(hass, freezer)
        fronius.measure(3000, 500, 15)
    # 1st at once, then after 4, 8, 16, 32 s at the earliest
    assert 3 <= len(tries) <= 5


async def test_hold_with_peak_shaving_covers_peaks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Hold from the battery mode script with peak shaving on: no block, only the
    excess over the limit, also above the threshold.
    """
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000)
    await tick(hass, freezer)
    fronius.take()
    await evcc(hass, request="hold")
    fronius.measure(1000, 0, 80)
    await tick(hass, freezer, 11)
    assert fronius.take() == [(DISCHARGE, 0)]
    assert status(hass) == "hold"
    fronius.measure(3500, 0, 80)
    await tick(hass, freezer)
    assert fronius.take() == [(DISCHARGE, 1500)]


async def test_two_battery_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """fronius_modbus: storage discharge and charge power, both positive; the
    charge power is subtracted, an unknown one counts as a meter outage.
    """
    hass.states.async_set("sensor.battery_charge_power", "800")
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, "battery_charge_power": "sensor.battery_charge_power"},
    )
    freezer.move_to(START)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await evcc(hass, threshold=20, on=True, limit=2000)
    fronius.measure(3000, 0, 15)  # 3000 + 0 - 800 - 2000 = 200
    await tick(hass, freezer)
    assert fronius.take() == [("mode", "Discharge Limit"), (DISCHARGE, 200)]
    hass.states.async_set("sensor.battery_charge_power", STATE_UNAVAILABLE)
    await tick(hass, freezer, 11)
    assert status(hass) == "meter_outage"


async def test_measurements_frozen_after_grid_charge(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    fronius: FakeFronius,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After a switch to Charge from Grid fronius_modbus reconnects and repeats
    the last values for up to 30 s: a peak in that time gets the battery free.
    """
    await setup(hass, mock_config_entry, freezer)
    await evcc(hass, threshold=20, on=True, limit=2000, grid_charge=2000, request="grid_charge")
    assert fronius.take() == [("mode", "Charge from Grid")]
    await tick(hass, freezer, 5)
    fronius.take()
    await evcc(hass, request="normal")  # a peak: evcc pauses grid charging
    fronius.measure(3000, 0, 15)
    await tick(hass, freezer, 3)
    await tick(hass, freezer, 3)
    assert status(hass) == "meter_outage"
    assert (DISCHARGE, 1000) not in fronius.take()
    await tick(hass, freezer, 25)  # 30 s after the switch the values count again
    fronius.measure(3000, 0, 15)
    await tick(hass, freezer, 11)
    assert status(hass) == "shaving"
