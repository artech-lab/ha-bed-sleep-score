# SPDX-License-Identifier: GPL-3.0-or-later
"""Night tracking engine for Bed Sleep Score.

One ``SleepTracker`` per config entry does the whole analysis:

    accelerometer axes -> magnitude -> rolling standard deviation ("agitation")
    -> hysteresis -> movement episodes -> night accumulators -> score

It resets at the start of the sleep window and scores the night at its end,
recovers both after a Home Assistant restart, scores at most once per day and
persists its state with ``Store``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CLUSTER_MINUTES,
    CONF_PRESENCE_ENTITY,
    CONF_SENSORS,
    CONF_THRESHOLD,
    CONF_WINDOW_END,
    CONF_WINDOW_START,
    CONTINUITY_CAP_MIN,
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    DOMAIN,
    EMA_ALPHA,
    FORMULA_VERSION,
    GRACE_HOURS,
    MAX_POINTS,
    MIN_WINDOW_SAMPLES,
    PRESENCE_HOME_STATES,
    STD_DEV_WINDOW_S,
    STORAGE_VERSION,
    THRESHOLD_OFF_RATIO,
)
from .scoring import NightInputs, compute_score, ema, magnitude, std_dev

_LOGGER = logging.getLogger(__name__)

SAVE_DELAY_S = 30
TICK = timedelta(seconds=30)


def _parse_time(value: Any, default: time) -> time:
    return (dt_util.parse_time(value) if isinstance(value, str) else None) or default


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _from_iso(value: Any) -> datetime | None:
    parsed = dt_util.parse_datetime(str(value)) if value else None
    return dt_util.as_local(parsed) if parsed else None


@dataclass(slots=True)
class Night:
    """Accumulators for the night in progress."""

    started: datetime | None = None
    movements: int = 0
    clusters: int = 0
    longest_min: float = 0.0
    last_movement: datetime | None = None
    samples: int = 0
    total: float = 0.0
    minimum: float | None = None
    maximum: float | None = None

    def add_sample(self, value: float) -> None:
        """Add one agitation sample."""
        self.samples += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    def to_dict(self) -> dict[str, Any]:
        """Serialise for storage."""
        return {**asdict(self), "started": _iso(self.started), "last_movement": _iso(self.last_movement)}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Night:
        """Restore from storage."""
        if not data:
            return cls()
        data = {key: value for key, value in data.items() if key in cls.__slots__}
        data["started"] = _from_iso(data.get("started"))
        data["last_movement"] = _from_iso(data.get("last_movement"))
        return cls(**data)


class SleepTracker:
    """Tracks one bed and scores each night."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, version: str) -> None:
        """Initialise the tracker."""
        self.hass = hass
        self.entry = entry
        self.version = version
        conf = {**entry.data, **entry.options}

        self.sensors: list[str] = list(conf[CONF_SENSORS])
        self.presence_entity: str | None = conf.get(CONF_PRESENCE_ENTITY) or None
        self.threshold_on = float(conf.get(CONF_THRESHOLD, DEFAULT_THRESHOLD))
        self.threshold_off = self.threshold_on * THRESHOLD_OFF_RATIO
        self.scale = self.threshold_on / DEFAULT_THRESHOLD

        self.window_start = _parse_time(entry.data.get(CONF_WINDOW_START), DEFAULT_WINDOW_START)
        self.window_end = _parse_time(entry.data.get(CONF_WINDOW_END), DEFAULT_WINDOW_END)

        self.night = Night()
        self.last_reset: datetime | None = None
        self.last_calculation: datetime | None = None
        self.last_result: dict[str, Any] | None = None
        self.average: float | None = None

        self.agitation: float | None = None
        self.moving = False

        self._axes: dict[str, float] = {}
        self._window: deque[tuple[datetime, float]] = deque()
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._unsubs: list[CALLBACK_TYPE] = []
        self._window_unsubs: list[CALLBACK_TYPE] = []

    # ------------------------------------------------------------------ setup

    @property
    def signal(self) -> str:
        """Dispatcher signal for this entry."""
        return f"{DOMAIN}_update_{self.entry.entry_id}"

    async def async_load(self) -> None:
        """Restore persisted state."""
        data = await self._store.async_load() or {}
        self.night = Night.from_dict(data.get("night"))
        self.last_reset = _from_iso(data.get("last_reset"))
        self.last_calculation = _from_iso(data.get("last_calculation"))
        self.last_result = data.get("last_result")
        self.average = data.get("average")
        self.window_start = _parse_time(data.get("window_start"), self.window_start)
        self.window_end = _parse_time(data.get("window_end"), self.window_end)

    @callback
    def async_start(self) -> None:
        """Subscribe to the sensors and schedule the window."""
        self._unsubs = [
            async_track_state_change_event(self.hass, self.sensors, self._on_sensor),
            async_track_time_interval(self.hass, self._on_tick, TICK),
        ]
        self._schedule_window()
        for entity_id in self.sensors:
            if (state := self.hass.states.get(entity_id)) is not None:
                self._read_axis(entity_id, state.state)

        if self.hass.is_running:
            self._catch_up()
        else:
            self._unsubs.append(
                self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, lambda _event: self._catch_up())
            )

    async def async_stop(self) -> None:
        """Unsubscribe and flush storage."""
        for unsub in (*self._unsubs, *self._window_unsubs):
            unsub()
        self._unsubs.clear()
        self._window_unsubs.clear()
        await self._store.async_save(self._as_storage())

    @callback
    def _schedule_window(self) -> None:
        for unsub in self._window_unsubs:
            unsub()
        self._window_unsubs = [
            async_track_time_change(self.hass, action, hour=at.hour, minute=at.minute, second=at.second)
            for action, at in ((self._on_window_start, self.window_start), (self._on_window_end, self.window_end))
        ]

    # ------------------------------------------------------------- window math

    def in_window(self, now: datetime | None = None) -> bool:
        """Whether ``now`` falls inside the sleep window (midnight-safe)."""
        current = (now or dt_util.now()).time()
        start, end = self.window_start, self.window_end
        if start < end:
            return start <= current < end
        return start != end and (current >= start or current < end)

    @staticmethod
    def _today_at(value: time, now: datetime) -> datetime:
        return now.replace(hour=value.hour, minute=value.minute, second=value.second, microsecond=0)

    # --------------------------------------------------------------- analysis

    def _read_axis(self, entity_id: str, raw_state: str) -> bool:
        try:
            self._axes[entity_id] = float(raw_state)
        except (TypeError, ValueError):
            self._axes.pop(entity_id, None)
            return False
        return len(self._axes) == len(self.sensors)

    @callback
    def _on_sensor(self, event: Event[EventStateChangedData]) -> None:
        """New accelerometer value: update the agitation and detect movements."""
        new_state = event.data["new_state"]
        if new_state is None or not self._read_axis(event.data["entity_id"], new_state.state):
            return
        now = dt_util.now()
        self._window.append((now, magnitude([self._axes[entity_id] for entity_id in self.sensors])))
        self._analyse(now)

    @callback
    def _on_tick(self, now: datetime) -> None:
        """Keep the signal fresh when the sensors go quiet, and refresh entities."""
        self._analyse(dt_util.now(), sample=False)

    @callback
    def _analyse(self, now: datetime, *, sample: bool = True) -> None:
        horizon = now - timedelta(seconds=STD_DEV_WINDOW_S)
        while self._window and self._window[0][0] < horizon:
            self._window.popleft()

        if len(self._window) < MIN_WINDOW_SAMPLES:
            # Not enough data (startup, or sensors unavailable): no signal.
            self.agitation = None
            self.moving = False
        else:
            self.agitation = std_dev([value for _, value in self._window])
            if sample and self.in_window(now):
                self.night.add_sample(self.agitation)
                self._store.async_delay_save(self._as_storage, SAVE_DELAY_S)
            # Hysteresis: a movement starts above threshold_on and ends below threshold_off.
            if not self.moving and self.agitation > self.threshold_on:
                self.moving = True
                self._register_movement(now)
            elif self.moving and self.agitation < self.threshold_off:
                self.moving = False
        self._notify()

    @callback
    def _register_movement(self, now: datetime) -> None:
        """One movement episode inside the window."""
        if not self.in_window(now):
            return
        night = self.night
        gap_min = max((now - (night.last_movement or now)).total_seconds() / 60, 0.0)
        if night.movements > 0 and gap_min < CLUSTER_MINUTES:
            night.clusters += 1
        if gap_min > night.longest_min:
            night.longest_min = float(min(round(gap_min), CONTINUITY_CAP_MIN))
        night.movements += 1
        night.last_movement = now
        self._store.async_delay_save(self._as_storage, 1)

    # ------------------------------------------------------- reset & scoring

    @callback
    def _on_window_start(self, now: datetime) -> None:
        self.async_reset(now)

    @callback
    def _on_window_end(self, now: datetime) -> None:
        self.async_calculate(now, end=self._today_at(self.window_end, now))

    @callback
    def _catch_up(self) -> None:
        """Recover a reset or a calculation missed while Home Assistant was down."""
        now = dt_util.now()
        if self.in_window(now):
            start = self._today_at(self.window_start, now)
            if now < start:
                start -= timedelta(days=1)
            if self.last_reset is None or self.last_reset < start:
                _LOGGER.debug("Catch-up: starting the night of %s", start)
                self.async_reset(now)
            return
        end = self._today_at(self.window_end, now)
        if end <= now <= end + timedelta(hours=GRACE_HOURS):
            _LOGGER.debug("Catch-up: scoring the night that ended at %s", end)
            self.async_calculate(now, end=end)

    @callback
    def async_reset(self, now: datetime | None = None) -> None:
        """Start a new night."""
        now = now or dt_util.now()
        self.night = Night(started=now, last_movement=now)
        self.last_reset = now
        self._save()

    def _is_present(self) -> bool:
        if not self.presence_entity:
            return True
        state = self.hass.states.get(self.presence_entity)
        return state is not None and state.state.lower() in PRESENCE_HOME_STATES

    @callback
    def async_calculate(self, now: datetime | None = None, *, end: datetime | None = None) -> bool:
        """Score the night that ended at ``end``. Returns True if a score was written."""
        now = now or dt_util.now()
        end = end or now
        if self.last_calculation is not None and self.last_calculation.date() == now.date():
            _LOGGER.debug("Score already calculated today, skipping")
            return False
        if not self._is_present():
            _LOGGER.debug("%s is not home, skipping the score", self.presence_entity)
            return False

        night = self.night
        # Close the last stretch: from the last movement to the END of the window.
        final_gap = max((end - night.last_movement).total_seconds() / 60, 0.0) if night.last_movement else 0.0
        continuity = min(round(max(night.longest_min, final_gap)), CONTINUITY_CAP_MIN)
        night.longest_min = float(continuity)

        result = compute_score(
            NightInputs(
                continuity_min=continuity,
                movements=night.movements,
                clusters=night.clusters,
                samples=night.samples,
                mean=night.total / night.samples if night.samples else None,
                minimum=night.minimum,
                maximum=night.maximum,
            ),
            self.scale,
        )
        self.average = ema(self.average, result["score"], EMA_ALPHA)
        self.last_calculation = now
        self.last_result = {
            **result,
            "night_of": end.date().isoformat(),
            "continuity_minutes": continuity,
            "movements": night.movements,
            "clustered_movements": night.clusters,
            "samples": night.samples,
        }
        self._save()
        return True

    async def async_set_window(self, *, start: time | None = None, end: time | None = None) -> None:
        """Change the sleep window (from the time entities)."""
        self.window_start = start or self.window_start
        self.window_end = end or self.window_end
        self._schedule_window()
        self._save()

    # --------------------------------------------------------------- helpers

    @property
    def score(self) -> int | None:
        """Last nightly score."""
        return self.last_result["score"] if self.last_result else None

    @property
    def score_attributes(self) -> dict[str, Any]:
        """Attributes of the score sensor (the card reads the breakdown from here)."""
        result = {key: value for key, value in (self.last_result or {}).items() if key != "score"}
        return {**result, "max_points": MAX_POINTS, "formula_version": FORMULA_VERSION}

    def _as_storage(self) -> dict[str, Any]:
        return {
            "night": self.night.to_dict(),
            "last_reset": _iso(self.last_reset),
            "last_calculation": _iso(self.last_calculation),
            "last_result": self.last_result,
            "average": self.average,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
        }

    def diagnostics(self) -> dict[str, Any]:
        """Snapshot for diagnostics."""
        return {
            **self._as_storage(),
            "version": self.version,
            "in_window": self.in_window(),
            "agitation": self.agitation,
            "moving": self.moving,
            "axes_available": len(self._axes),
            "window_samples": len(self._window),
            "threshold_on": self.threshold_on,
            "threshold_off": self.threshold_off,
        }

    @callback
    def _save(self) -> None:
        self.hass.async_create_task(self._store.async_save(self._as_storage()))
        self._notify()

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(self.hass, self.signal)
