"""The controller: gathers the inputs, applies the rules, writes the battery.

It only talks to Home Assistant entities (the select and numbers of
fronius_modbus); it never opens a Modbus connection of its own, as the
inverter takes one client only.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

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
    DOMAIN,
    EVAL_INTERVAL_S,
    MIN_EVAL_GAP_S,
    MIN_WRITE_GAP_S,
    MODE_ATTEMPTS_BEFORE_RESET,
    MODE_AUTO,
    MODE_DISCHARGE_LIMIT,
    MODE_GRID_CHARGE,
    MODE_RETRY_S,
    RECONNECT_S,
    REQUEST_NORMAL,
    STORAGE_VERSION,
)
from .regelung import (
    DISCHARGE_MAX,
    STATUS_METER_OUTAGE,
    STATUS_NO_EVCC,
    Inputs,
    Target,
    decide,
    fit,
    quarter_start,
    should_write,
)

_LOGGER = logging.getLogger(__name__)

RELEASE_TIMEOUT_S = 8
MAX_RETRY_S = 300  # a failing write is tried again at most this far apart


def _float(state: State | None) -> float | None:
    """Return the numeric state, ``None`` if it has none."""
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        return float(state.state)
    except ValueError:
        return None


def _usable(state: State | None) -> bool:
    """Return whether an entity can be written.

    Home Assistant answers a call to an unavailable entity with success and
    does nothing.
    """
    return state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


class PeakController:
    """Peak shaving for one Fronius inverter."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Read the configured entities and prepare the state."""
        self.hass = hass
        self.entry = entry
        conf = {**entry.data, **entry.options}
        self.grid_entity: str = conf[CONF_GRID_POWER]
        self.grid_invert: bool = conf.get(CONF_GRID_INVERT, False)
        self.battery_entity: str = conf[CONF_BATTERY_POWER]
        self.battery_invert: bool = conf.get(CONF_BATTERY_INVERT, False)
        self.battery_charge_entity: str | None = conf.get(CONF_BATTERY_CHARGE_POWER) or None
        self.soc_entity: str = conf[CONF_SOC]
        self.mode_entity: str = conf[CONF_MODE]
        self.discharge_entity: str = conf[CONF_DISCHARGE_LIMIT]
        self.grid_charge_entity: str = conf[CONF_GRID_CHARGE]
        self.reset_entity: str | None = conf.get(CONF_RESET_BUTTON) or None

        # Values set by evcc through the own entities.
        self.enabled = False
        self.limit = 0.0
        self.limit_written_at: datetime | None = None
        self.threshold = 20.0
        self.request = REQUEST_NORMAL
        self.grid_charge_power = 0.0

        # Control state.
        self.owned = False
        self.below = False
        self.status = STATUS_NO_EVCC
        self.discharge_target: float | None = None
        self.writes_today = 0
        self._writes_day: date | None = None
        self._last_write: datetime | None = None
        self._last_lowered: datetime | None = None
        self._mode_written: datetime | None = None
        self._mode_written_value: str | None = None
        self._reconnect_until: datetime | None = None  # measurements frozen until then
        self._mode_attempts = 0
        self._failing: dict[str, tuple[int, datetime]] = {}  # failures, last try
        self._force_write = False  # write the numbers once after an own mode change
        self._unsub_stop: CALLBACK_TYPE | None = None
        self._retry: CALLBACK_TYPE | None = None  # evaluation after the write gap
        self._quarter: datetime | None = None

        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._task: asyncio.Task[None] | None = None
        self._pending = False
        self._last_eval: datetime | None = None
        self._stopped = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_load(self) -> None:
        """Load whether the integration held the mode before the restart."""
        data = await self._store.async_load() or {}
        self.owned = bool(data.get("owned", False))

    @callback
    def async_start(self) -> None:
        """Follow the inputs and evaluate periodically."""
        self._quarter = quarter_start(dt_util.utcnow())
        self._unsubs.append(
            async_track_state_change_event(
                self.hass,
                [
                    self.grid_entity,
                    self.battery_entity,
                    *([self.battery_charge_entity] if self.battery_charge_entity else []),
                    self.soc_entity,
                    self.mode_entity,
                    self.discharge_entity,
                    self.grid_charge_entity,
                ],
                self._on_input,
            )
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._on_tick, timedelta(seconds=EVAL_INTERVAL_S))
        )
        self._unsub_stop = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._on_stop)
        self.schedule()

    async def async_stop(self) -> None:
        """Stop controlling and hand the battery back."""
        self._stopped = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._unsub_stop is not None:
            self._unsub_stop()
            self._unsub_stop = None
        if self._retry is not None:
            self._retry()
            self._retry = None
        if self._task is not None and not self._task.done():
            # a write in flight finishes before the hand back starts
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self.async_release()

    async def async_release(self) -> None:
        """Set the mode back to Auto if the integration holds it (best effort)."""
        if not self.owned:
            return
        mode_state = self.hass.states.get(self.mode_entity)
        if not _usable(mode_state):
            _LOGGER.warning("Mode not handed back: %s not available", self.mode_entity)
            return
        try:
            async with asyncio.timeout(RELEASE_TIMEOUT_S):
                # free the limit first: should Auto not land, the battery is free
                await self._free_limits(mode_state.state)
                await self._call_select(self.mode_entity, MODE_AUTO)
        except Exception:
            _LOGGER.warning("Mode not handed back to Auto", exc_info=True)
            return
        await self._set_owned(False)

    async def _on_stop(self, _event: Event) -> None:
        """Home Assistant stops: nobody controls the battery any more."""
        self._unsub_stop = None  # a listener of async_listen_once is gone once called
        await self.async_stop()

    async def _free_limits(self, mode: str) -> None:
        """Set the limit of the running mode free: discharge maximum, grid charge 0."""
        if mode == MODE_DISCHARGE_LIMIT:
            state = self.hass.states.get(self.discharge_entity)
            if _usable(state):
                maximum = float(state.attributes.get("max", 100000))
                if _float(state) != maximum:
                    await self._call_number(self.discharge_entity, maximum)
        elif mode == MODE_GRID_CHARGE:
            state = self.hass.states.get(self.grid_charge_entity)
            if _usable(state) and _float(state) != 0:
                await self._call_number(self.grid_charge_entity, 0)

    # ------------------------------------------------------------------
    # Values from the own entities
    # ------------------------------------------------------------------

    @callback
    def async_add_listener(self, update: CALLBACK_TYPE) -> Callable[[], None]:
        """Register an entity that shows controller values."""
        self._listeners.append(update)
        return lambda: self._listeners.remove(update)

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()

    @callback
    def set_enabled(self, enabled: bool) -> None:
        """Peak shaving on or off (written by evcc)."""
        self.enabled = enabled
        self.schedule()

    @callback
    def set_limit(self, limit: float) -> None:
        """Take the allowed grid power of the window, also evcc's sign of life."""
        self.limit = limit
        # 0 means expired: written by hand it hands the battery back right away
        self.limit_written_at = dt_util.utcnow() if limit > 0 else None
        self._notify()
        self.schedule()

    def limit_shown(self) -> float:
        """Return the limit entity's state: 0 once evcc has not written in this quarter."""
        now = dt_util.utcnow()
        written = self.limit_written_at
        if written is None or written < quarter_start(now):
            return 0.0
        return self.limit

    @callback
    def set_threshold(self, threshold: float) -> None:
        """Soc threshold of the reserve (written by evcc)."""
        self.threshold = threshold
        self.schedule()

    @callback
    def set_request(self, request: str) -> None:
        """Take the request normal, grid charging or hold (written by evcc)."""
        self.request = request
        self.schedule()

    @callback
    def set_grid_charge_power(self, power: float) -> None:
        """Grid charge power for the request grid charging (written by evcc)."""
        self.grid_charge_power = power
        self.schedule()

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    @callback
    def _on_input(self, _event: Event) -> None:
        self.schedule()

    @callback
    def _on_tick(self, now: datetime) -> None:
        quarter = quarter_start(dt_util.utcnow())
        if quarter != self._quarter:
            # Show the limit as expired, so evcc writes it again.
            self._quarter = quarter
            self._notify()
        self.schedule()

    @callback
    def schedule(self) -> None:
        """Evaluate soon; one evaluation at a time, at most one per second."""
        if self._stopped:
            return
        if self._task is not None and not self._task.done():
            self._pending = True
            return
        self._task = self.entry.async_create_background_task(
            self.hass, self._run(), f"{DOMAIN} evaluation"
        )

    async def _run(self) -> None:
        while True:
            self._pending = False
            if self._last_eval is not None:
                wait = MIN_EVAL_GAP_S - (dt_util.utcnow() - self._last_eval).total_seconds()
                if wait > 0:
                    await asyncio.sleep(wait)
            self._last_eval = dt_util.utcnow()
            try:
                await self.async_evaluate()
            except Exception:
                _LOGGER.exception("Evaluation failed")
            if not self._pending or self._stopped:
                return

    def _inputs(self, now: datetime) -> Inputs:
        grid_state = self.hass.states.get(self.grid_entity)
        grid = _float(grid_state)
        if grid is not None and self.grid_invert:
            grid = -grid
        battery = _float(self.hass.states.get(self.battery_entity))
        if battery is not None and self.battery_invert:
            battery = -battery
        if battery is not None and self.battery_charge_entity is not None:
            # two sensors, both positive: discharging minus charging
            charge = _float(self.hass.states.get(self.battery_charge_entity))
            battery = None if charge is None else battery - charge
        updated = None
        if grid is not None and grid_state is not None:
            updated = getattr(grid_state, "last_reported", None) or grid_state.last_updated
        if self._reconnect_until is not None and now < self._reconnect_until:
            # the values look fresh but repeat the last read: a meter outage
            updated = None
        return Inputs(
            now=now,
            enabled=self.enabled,
            limit=self.limit,
            limit_written_at=self.limit_written_at,
            soc=_float(self.hass.states.get(self.soc_entity)),
            threshold=self.threshold,
            request=self.request,
            grid_charge_power=self.grid_charge_power,
            grid=grid,
            grid_updated=updated,
            battery=battery,
        )

    async def async_evaluate(self) -> None:
        """Apply the rules once and write what has to change."""
        now = dt_util.utcnow()
        target = decide(self._inputs(now), owned=self.owned, below=self.below)
        self.below = target.below
        if target.status != self.status:
            if target.status == STATUS_NO_EVCC:
                _LOGGER.warning("No limit from evcc in time: peak shaving stops")
            elif target.status == STATUS_METER_OUTAGE:
                _LOGGER.warning("Grid power %s missing or stale: discharge free", self.grid_entity)
        self.status = target.status
        self.discharge_target = target.discharge
        try:
            await self._apply(target, now)
        finally:
            self._notify()

    async def _apply(self, target: Target, now: datetime) -> None:
        if target.mode is None:
            await self._set_owned(target.owned)
            return
        mode_state = self.hass.states.get(self.mode_entity)
        if not _usable(mode_state):
            return
        if mode_state.state != target.mode:
            if target.mode == MODE_AUTO and await self._free_before_release(mode_state.state, now):
                return
            await self._change_mode(target.mode, now)
            return
        if self._mode_written_value == target.mode:
            # fronius_modbus reset the limits with the mode change; the number
            # entities may still show the old value until its next scan
            self._force_write = True
        self._mode_attempts = 0
        self._mode_written = None
        self._mode_written_value = None
        await self._set_owned(target.owned)
        force = self._force_write
        if target.discharge is not None:
            entity, value, raise_immediately = self.discharge_entity, target.discharge, True
        elif target.grid_charge is not None:
            entity, value, raise_immediately = self.grid_charge_entity, target.grid_charge, False
        else:
            self._force_write = False
            return
        if await self._write_number(
            entity, value, now, raise_immediately=raise_immediately, force=force
        ):
            self._force_write = False

    async def _free_before_release(self, mode: str, now: datetime) -> bool:
        """Free the running limit before writing Auto; report whether it wrote.

        Should Auto not land (a stale mode, no reset button), the battery is
        then at least not left throttled.
        """
        if mode == MODE_DISCHARGE_LIMIT:
            return await self._write_number(
                self.discharge_entity, DISCHARGE_MAX, now, raise_immediately=True
            )
        if mode == MODE_GRID_CHARGE:
            return await self._write_number(
                self.grid_charge_entity, 0, now, raise_immediately=False
            )
        return False

    async def _change_mode(self, mode: str, now: datetime) -> None:
        """Write the mode and wait for it to show.

        fronius_modbus can keep a stale mode: after three attempts the Modbus
        control is reset.
        """
        if (
            mode == self._mode_written_value
            and self._mode_written is not None
            and now - self._mode_written < timedelta(seconds=MODE_RETRY_S)
        ):
            return
        if mode != self._mode_written_value:
            self._mode_attempts = 0
        if not self._write_allowed(now):
            return
        if self._backing_off("mode", now):
            return
        if self._mode_attempts >= MODE_ATTEMPTS_BEFORE_RESET and self.reset_entity:
            _LOGGER.warning(
                "Mode %s did not show after %d attempts, resetting the Modbus control",
                mode,
                self._mode_attempts,
            )
            self._mode_attempts = 0
            self._mode_written = now
            await self._guarded("reset", self._call_button(self.reset_entity), now)
            return
        self._mode_attempts += 1
        self._mode_written = now
        self._mode_written_value = mode
        if mode == MODE_GRID_CHARGE:
            self._reconnect_until = now + timedelta(seconds=RECONNECT_S)
        if mode != MODE_AUTO:
            # From here on the integration may have changed the mode.
            await self._set_owned(True)
        await self._guarded("mode", self._call_select(self.mode_entity, mode), now)

    async def _write_number(
        self,
        entity: str,
        target: float,
        now: datetime,
        *,
        raise_immediately: bool,
        force: bool = False,
    ) -> bool:
        """Write a number if needed; report whether a write was sent.

        ``force`` also writes what the entity already shows, without the
        tolerance and the rate limit of lowering.
        """
        state = self.hass.states.get(entity)
        if not _usable(state):
            return False
        minimum = float(state.attributes.get("min", 0))
        maximum = float(state.attributes.get("max", 100000))
        value = fit(target, minimum, maximum)
        current = _float(state)
        if not force and not should_write(
            current,
            value,
            minimum=minimum,
            maximum=maximum,
            raise_immediately=raise_immediately,
            last_lowered=self._last_lowered,
            now=now,
        ):
            return False
        if not self._write_allowed(now) or self._backing_off(entity, now):
            return False
        lowering = raise_immediately and current is not None and value < current
        if await self._guarded(entity, self._call_number(entity, value), now) and lowering:
            # a lowering that failed did not lower: the next try is not held back
            self._last_lowered = now
        return True

    def _write_allowed(self, now: datetime) -> bool:
        """Report whether the write gap has passed; if not, evaluate again after it."""
        if self._last_write is None or now - self._last_write >= timedelta(seconds=MIN_WRITE_GAP_S):
            return True
        if self._retry is None and not self._stopped:
            self._retry = async_call_later(self.hass, MIN_WRITE_GAP_S, self._on_retry)
        return False

    @callback
    def _on_retry(self, _now: datetime) -> None:
        self._retry = None
        self.schedule()

    def _backing_off(self, what: str, now: datetime) -> bool:
        """After a failure wait 4, 8, 16 … s, at most MAX_RETRY_S, before the next try."""
        if what not in self._failing:
            return False
        count, last = self._failing[what]
        wait = min(MIN_WRITE_GAP_S * 2**count, MAX_RETRY_S)
        return now - last < timedelta(seconds=wait)

    async def _guarded(self, what: str, call: Any, now: datetime) -> bool:
        """Run one write, count it, log a failure once until it works again.

        Report whether it landed.
        """
        self._last_write = now
        today = dt_util.as_local(now).date()
        if today != self._writes_day:
            self._writes_day = today
            self.writes_today = 0
        self.writes_today += 1
        try:
            await call
        except Exception as err:
            if what in self._failing:
                count = self._failing[what][0] + 1
                _LOGGER.debug("Write %s failed again (%d): %s", what, count, err)
            else:
                count = 1
                _LOGGER.error("Write %s failed: %s", what, err)
            self._failing[what] = (count, now)
            return False
        if self._failing.pop(what, None) is not None:
            _LOGGER.info("Write %s works again", what)
        return True

    async def _set_owned(self, owned: bool) -> None:
        if owned == self.owned:
            return
        self.owned = owned
        await self._store.async_save({"owned": owned})

    async def _call_select(self, entity: str, option: str) -> None:
        await self.hass.services.async_call(
            entity.split(".", maxsplit=1)[0],
            "select_option",
            {ATTR_ENTITY_ID: entity, "option": option},
            blocking=True,
        )

    async def _call_number(self, entity: str, value: float) -> None:
        await self.hass.services.async_call(
            entity.split(".", maxsplit=1)[0],
            "set_value",
            {ATTR_ENTITY_ID: entity, "value": value},
            blocking=True,
        )

    async def _call_button(self, entity: str) -> None:
        await self.hass.services.async_call(
            entity.split(".", maxsplit=1)[0], "press", {ATTR_ENTITY_ID: entity}, blocking=True
        )
