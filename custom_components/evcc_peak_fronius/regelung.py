"""The control rules, free of Home Assistant.

``decide`` turns one snapshot of the inputs into the target state of the
battery: which storage control mode, which discharge limit or grid charge
power. ``should_write`` decides whether a number is written now. Both are pure
so the rules can be tested without a running Home Assistant; the controller
only gathers the inputs and carries the target out.

Fronius keeps regulating the battery itself (self consumption). The rules only
narrow it: below the soc threshold the battery may discharge only what exceeds
the allowed grid power, everything else stays with Fronius.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from .const import (
    HEARTBEAT_GRACE_S,
    HYSTERESIS_PCT,
    LOWER_INTERVAL_S,
    METER_STALE_S,
    MODE_AUTO,
    MODE_BLOCK_DISCHARGE,
    MODE_DISCHARGE_LIMIT,
    MODE_GRID_CHARGE,
    POWER_STEP_W,
    QUARTER_S,
    REQUEST_GRID_CHARGE,
    REQUEST_HOLD,
    WRITE_TOLERANCE_W,
)

# Status keys, the states of the status sensor.
STATUS_NO_EVCC = "no_evcc"
STATUS_OFF = "off"
STATUS_FREE = "free"
STATUS_SHAVING = "shaving"
STATUS_METER_OUTAGE = "meter_outage"
STATUS_NO_SOC = "no_soc"
STATUS_GRID_CHARGE = "grid_charge"
STATUS_HOLD = "hold"
STATUSES = [
    STATUS_NO_EVCC,
    STATUS_OFF,
    STATUS_FREE,
    STATUS_SHAVING,
    STATUS_METER_OUTAGE,
    STATUS_NO_SOC,
    STATUS_GRID_CHARGE,
    STATUS_HOLD,
]

#: Discharge target meaning "the maximum of the entity".
DISCHARGE_MAX = math.inf


def quarter_start(now: datetime) -> datetime:
    """Return the start of the clock aligned 15 minute window of ``now``."""
    seconds = now.minute * 60 + now.second + now.microsecond / 1e6
    return now - timedelta(seconds=seconds % QUARTER_S)


def evcc_alive(written_at: datetime | None, now: datetime) -> bool:
    """Return whether evcc wrote the limit recently enough.

    evcc has to write the limit once per quarter: the controller resets the
    limit entity at the start of each quarter, so evcc sees a difference and
    writes again. Until ``HEARTBEAT_GRACE_S`` into a quarter a write from the
    previous quarter still counts.
    """
    if written_at is None:
        return False
    start = quarter_start(now)
    if now - start < timedelta(seconds=HEARTBEAT_GRACE_S):
        start -= timedelta(seconds=QUARTER_S)
    return written_at >= start


def ceil_step(value: float) -> float:
    """Round up to the power step (the peak stays covered)."""
    return math.ceil(value / POWER_STEP_W) * POWER_STEP_W


def floor_step(value: float) -> float:
    """Round down to the power step (stays within the limit)."""
    return math.floor(value / POWER_STEP_W) * POWER_STEP_W


@dataclass(frozen=True, kw_only=True)
class Inputs:
    """One snapshot of everything the rules look at.

    Powers in W. ``grid`` is positive for import, ``battery`` positive for
    discharging. ``None`` means unknown (unavailable, unreadable).
    """

    now: datetime
    enabled: bool
    limit: float
    limit_written_at: datetime | None
    soc: float | None
    threshold: float
    request: str
    grid_charge_power: float
    grid: float | None
    grid_updated: datetime | None
    battery: float | None


@dataclass(frozen=True, kw_only=True)
class Target:
    """What the battery should do.

    ``mode`` ``None`` leaves the storage control mode alone. ``discharge``
    is only set with ``MODE_DISCHARGE_LIMIT`` (``DISCHARGE_MAX`` for the
    entity's maximum), ``grid_charge`` only with ``MODE_GRID_CHARGE``.
    ``owned`` tells whether the integration holds the mode afterwards.
    """

    mode: str | None
    status: str
    owned: bool
    below: bool
    discharge: float | None = None
    grid_charge: float | None = None


def _release(owned: bool, status: str, below: bool) -> Target:
    """Hand the battery back to Fronius, if the integration holds it."""
    return Target(mode=MODE_AUTO if owned else None, status=status, owned=False, below=below)


def decide(inputs: Inputs, *, owned: bool, below: bool) -> Target:
    """Return the target state of the battery for ``inputs``.

    ``owned``: the integration set the mode last and has not handed it back.
    ``below``: the soc was below the threshold in the last evaluation
    (hysteresis).
    """
    if not evcc_alive(inputs.limit_written_at, inputs.now):
        return _release(owned, STATUS_NO_EVCC, False)

    if inputs.request == REQUEST_GRID_CHARGE:
        power = floor_step(max(0.0, inputs.grid_charge_power))
        return Target(
            mode=MODE_GRID_CHARGE,
            status=STATUS_GRID_CHARGE,
            owned=True,
            below=below,
            grid_charge=power,
        )
    if inputs.request == REQUEST_HOLD:
        if inputs.enabled:
            # with peak shaving a held battery still covers peaks, whatever the
            # soc: what evcc wants from a hold (it switches to normal for a peak,
            # the integration does it within seconds)
            return _shave(inputs, STATUS_HOLD, below)
        return Target(mode=MODE_BLOCK_DISCHARGE, status=STATUS_HOLD, owned=True, below=below)

    if not inputs.enabled:
        return _release(owned, STATUS_OFF, False)

    if inputs.soc is None:
        return _free(STATUS_NO_SOC, below)

    if below:
        below = inputs.soc < inputs.threshold + HYSTERESIS_PCT
    else:
        below = inputs.soc < inputs.threshold
    if not below:
        return _free(STATUS_FREE, False)

    return _shave(inputs, STATUS_SHAVING, below)


def _shave(inputs: Inputs, status: str, below: bool) -> Target:
    """Discharge only what exceeds the limit."""
    if (
        inputs.grid is None
        or inputs.battery is None
        or inputs.grid_updated is None
        or (inputs.now - inputs.grid_updated > timedelta(seconds=METER_STALE_S))
    ):
        # Without a measurement the battery may cover everything: an outage
        # must not cause a peak.
        return _free(STATUS_METER_OUTAGE, below)

    setpoint = ceil_step(max(0.0, inputs.grid + inputs.battery - inputs.limit))
    return Target(
        mode=MODE_DISCHARGE_LIMIT,
        status=status,
        owned=True,
        below=below,
        discharge=setpoint,
    )


def _free(status: str, below: bool) -> Target:
    """Discharge limit mode with the limit at the maximum."""
    return Target(
        mode=MODE_DISCHARGE_LIMIT,
        status=status,
        owned=True,
        below=below,
        discharge=DISCHARGE_MAX,
    )


def should_write(
    current: float | None,
    target: float,
    *,
    minimum: float,
    maximum: float,
    raise_immediately: bool,
    last_lowered: datetime | None,
    now: datetime,
) -> bool:
    """Return whether ``target`` is written to a number showing ``current``.

    ``target`` is already fitted to ``minimum`` and ``maximum``. Changes
    within the write tolerance are skipped, except to reach the minimum or
    the maximum. With ``raise_immediately`` (the discharge limit) any higher
    value is written at once, so a peak is covered, a lower one at most every
    ``LOWER_INTERVAL_S``.
    """
    if current is None:
        return True
    if target == current:
        return False
    if raise_immediately and target > current:
        # a higher discharge limit covers a peak: always, at once
        return True
    if abs(target - current) < WRITE_TOLERANCE_W and target not in (minimum, maximum):
        return False
    if not raise_immediately:
        return True
    return last_lowered is None or now - last_lowered >= timedelta(seconds=LOWER_INTERVAL_S)


def fit(value: float, minimum: float, maximum: float) -> float:
    """Clamp ``value`` (``DISCHARGE_MAX`` included) into the entity's range."""
    return min(max(value, minimum), maximum)
