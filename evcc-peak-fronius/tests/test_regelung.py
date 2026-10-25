"""Tests of the control rules, without Home Assistant running."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.evcc_peak_fronius.const import (
    MODE_AUTO,
    MODE_BLOCK_DISCHARGE,
    MODE_DISCHARGE_LIMIT,
    MODE_GRID_CHARGE,
    REQUEST_GRID_CHARGE,
    REQUEST_HOLD,
    REQUEST_NORMAL,
)
from custom_components.evcc_peak_fronius.regelung import (
    DISCHARGE_MAX,
    STATUS_FREE,
    STATUS_GRID_CHARGE,
    STATUS_HOLD,
    STATUS_METER_OUTAGE,
    STATUS_NO_EVCC,
    STATUS_NO_SOC,
    STATUS_OFF,
    STATUS_SHAVING,
    Inputs,
    decide,
    evcc_alive,
    fit,
    quarter_start,
    should_write,
)

NOW = datetime(2026, 10, 25, 12, 7, 30, tzinfo=UTC)


def inputs(**kw: object) -> Inputs:
    base: dict[str, object] = {
        "now": NOW,
        "enabled": True,
        "limit": 2000.0,
        "limit_written_at": NOW - timedelta(minutes=1),
        "soc": 15.0,
        "threshold": 20.0,
        "request": REQUEST_NORMAL,
        "grid_charge_power": 0.0,
        "grid": 3000.0,
        "grid_updated": NOW,
        "battery": 500.0,
    }
    base.update(kw)
    return Inputs(**base)  # type: ignore[arg-type]


def test_quarter_start() -> None:
    assert quarter_start(NOW) == datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
    assert quarter_start(NOW.replace(minute=45)) == NOW.replace(minute=45, second=0)


@pytest.mark.parametrize(
    ("written", "now", "alive"),
    [
        (None, NOW, False),
        (NOW - timedelta(minutes=7), NOW, True),  # 12:00:30, this quarter
        (NOW - timedelta(minutes=8), NOW, False),  # 11:59:30, last quarter, grace over
        # 12:15:30 is in the grace of the new quarter: a write of 12:14 counts
        (NOW.replace(minute=14), NOW.replace(minute=15, second=30), True),
        (NOW.replace(minute=14), NOW.replace(minute=17, second=0), False),
    ],
)
def test_evcc_alive(written: datetime | None, now: datetime, alive: bool) -> None:
    assert evcc_alive(written, now) is alive


def test_below_threshold_covers_only_the_excess() -> None:
    # grid 3000 + battery 500 - limit 2000 = 1500
    t = decide(inputs(), owned=False, below=False)
    assert (t.mode, t.discharge, t.status, t.owned, t.below) == (
        MODE_DISCHARGE_LIMIT,
        1500,
        STATUS_SHAVING,
        True,
        True,
    )


def test_setpoint_rounds_up_to_10_w() -> None:
    assert decide(inputs(grid=3001.0), owned=True, below=True).discharge == 1510


def test_setpoint_never_negative() -> None:
    assert decide(inputs(grid=500.0, battery=-800.0), owned=True, below=True).discharge == 0


def test_above_threshold_free() -> None:
    t = decide(inputs(soc=50.0), owned=True, below=False)
    assert (t.mode, t.discharge, t.status) == (MODE_DISCHARGE_LIMIT, DISCHARGE_MAX, STATUS_FREE)


def test_hysteresis() -> None:
    # below stays until 2 % above the threshold
    assert decide(inputs(soc=21.0), owned=True, below=True).below
    assert not decide(inputs(soc=22.0), owned=True, below=True).below
    # not below yet: exactly at the threshold is not below
    assert not decide(inputs(soc=20.0), owned=True, below=False).below


@pytest.mark.parametrize(
    "kw",
    [
        {"grid": None},
        {"battery": None},
        {"grid_updated": None},
        {"grid_updated": NOW - timedelta(seconds=31)},
    ],
)
def test_meter_outage_frees_the_battery(kw: dict[str, object]) -> None:
    t = decide(inputs(**kw), owned=True, below=True)
    assert (t.discharge, t.status) == (DISCHARGE_MAX, STATUS_METER_OUTAGE)


def test_no_soc_frees_and_keeps_hysteresis() -> None:
    t = decide(inputs(soc=None), owned=True, below=True)
    assert (t.discharge, t.status, t.below) == (DISCHARGE_MAX, STATUS_NO_SOC, True)


def test_no_evcc_hands_back_when_owned() -> None:
    t = decide(inputs(limit_written_at=None), owned=True, below=True)
    assert (t.mode, t.status, t.owned) == (MODE_AUTO, STATUS_NO_EVCC, False)


def test_no_evcc_touches_nothing_when_not_owned() -> None:
    t = decide(inputs(limit_written_at=None), owned=False, below=False)
    assert (t.mode, t.status) == (None, STATUS_NO_EVCC)


def test_no_evcc_ends_grid_charging() -> None:
    t = decide(inputs(limit_written_at=None, request=REQUEST_GRID_CHARGE), owned=True, below=False)
    assert t.mode == MODE_AUTO


def test_off_hands_back() -> None:
    t = decide(inputs(enabled=False), owned=True, below=True)
    assert (t.mode, t.status, t.owned) == (MODE_AUTO, STATUS_OFF, False)
    assert decide(inputs(enabled=False), owned=False, below=False).mode is None


def test_grid_charge_request() -> None:
    t = decide(
        inputs(request=REQUEST_GRID_CHARGE, grid_charge_power=2345.0, enabled=False),
        owned=False,
        below=False,
    )
    assert (t.mode, t.grid_charge, t.status, t.owned) == (
        MODE_GRID_CHARGE,
        2340,
        STATUS_GRID_CHARGE,
        True,
    )


def test_hold_request_without_peak_shaving_blocks() -> None:
    t = decide(inputs(request=REQUEST_HOLD, enabled=False), owned=False, below=False)
    assert (t.mode, t.status, t.owned) == (MODE_BLOCK_DISCHARGE, STATUS_HOLD, True)


def test_hold_request_with_peak_shaving_covers_peaks() -> None:
    # soc above the threshold: held, only the excess over the limit is covered
    t = decide(inputs(request=REQUEST_HOLD, soc=80.0), owned=False, below=False)
    assert (t.mode, t.discharge, t.status) == (MODE_DISCHARGE_LIMIT, 1500, STATUS_HOLD)
    t = decide(
        inputs(request=REQUEST_HOLD, soc=80.0, grid=1000.0, battery=0.0), owned=True, below=False
    )
    assert t.discharge == 0
    t = decide(inputs(request=REQUEST_HOLD, grid=None), owned=True, below=False)
    assert (t.discharge, t.status) == (DISCHARGE_MAX, STATUS_METER_OUTAGE)


def write(current: float | None, target: float, **kw: object) -> bool:
    args: dict[str, object] = {
        "minimum": 0.0,
        "maximum": 10000.0,
        "raise_immediately": True,
        "last_lowered": None,
        "now": NOW,
    }
    args.update(kw)
    return should_write(current, target, **args)  # type: ignore[arg-type]


def test_should_write_tolerance() -> None:
    # lowering within the tolerance is skipped, raising never
    assert not write(1040, 1000)
    assert write(1050, 1000)
    assert write(1000, 1010)
    assert not write(1000, 1040, raise_immediately=False)
    assert not write(1000, 1000)
    assert write(None, 1000)


def test_should_write_min_and_max_always_land() -> None:
    assert write(20, 0)
    assert write(9990, 10000)


def test_should_write_lower_rate_limited() -> None:
    assert write(2000, 1000, last_lowered=NOW - timedelta(seconds=11))
    assert not write(2000, 1000, last_lowered=NOW - timedelta(seconds=5))
    # raising is never held back
    assert write(1000, 2000, last_lowered=NOW - timedelta(seconds=1))
    # without raise_immediately lowering is not rate limited
    assert write(2000, 1000, raise_immediately=False, last_lowered=NOW)


def test_fit() -> None:
    assert fit(DISCHARGE_MAX, 0, 10000) == 10000
    assert fit(-5, 0, 10000) == 0
    assert fit(500, 0, 10000) == 500


def test_grid_charge_power_never_negative() -> None:
    t = decide(
        inputs(request=REQUEST_GRID_CHARGE, grid_charge_power=-500.0), owned=False, below=False
    )
    assert t.grid_charge == 0


def test_no_evcc_ends_hold() -> None:
    t = decide(inputs(limit_written_at=None, request=REQUEST_HOLD), owned=True, below=True)
    assert (t.mode, t.below) == (MODE_AUTO, False)


def test_hysteresis_just_below_the_band() -> None:
    assert decide(inputs(soc=21.9), owned=True, below=True).below


def test_setpoint_on_the_step_stays() -> None:
    assert decide(inputs(grid=3500.0, battery=0.0), owned=True, below=True).discharge == 1500


def test_threshold_100_holds_the_battery() -> None:
    # the hold of the optimizer: threshold 100 %, only peaks are covered
    t = decide(inputs(threshold=100.0, soc=99.0, grid=1500.0, battery=0.0), owned=True, below=False)
    assert (t.status, t.discharge) == (STATUS_SHAVING, 0)
