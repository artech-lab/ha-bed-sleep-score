"""End-to-end tests: raw acceleration in, sleep score out."""

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
import voluptuous as vol

from custom_components.bed_sleep_score.const import DOMAIN, EMA_ALPHA, SETTLE_S
from custom_components.bed_sleep_score.diagnostics import async_get_config_entry_diagnostics
from custom_components.bed_sleep_score.scoring import ema

ACCEL = "sensor.bed_accel"
QUIET = (9.805, 9.815)
SPIKES = (9.2, 10.5, 9.0)
GLITCH = 0.0  # first reading after a reconnection, far from the resting 9.81 m/s²


async def _at(hass: HomeAssistant, freezer: FrozenDateTimeFactory, when: datetime) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass, when)
    await hass.async_block_till_done()


async def _feed(hass, freezer, start: datetime, values, entity_id: str = ACCEL, step: int = 10) -> None:
    """Publish one raw acceleration value every ``step`` seconds."""
    for index, value in enumerate(values):
        await _at(hass, freezer, start + timedelta(seconds=step * index))
        hass.states.async_set(entity_id, str(value))
        await hass.async_block_till_done()


async def _movement(hass, freezer, at: datetime) -> None:
    """A minute of quiet, a burst at ``at``, then three quiet minutes."""
    await _feed(hass, freezer, at - timedelta(seconds=60), [QUIET[i % 2] for i in range(6)])
    await _feed(hass, freezer, at, SPIKES)
    await _feed(hass, freezer, at + timedelta(seconds=30), [QUIET[i % 2] for i in range(18)])


async def _setup(hass: HomeAssistant, **data) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Sleep tracker",
        data={"accelerometer_sensors": [ACCEL], "window_start": "00:00:00", "window_end": "08:00:00", **data},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_full_night(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    evening = dt_util.now().replace(hour=22, minute=0, second=0, microsecond=0)
    freezer.move_to(evening)
    hass.states.async_set(ACCEL, "9.81")
    entry = await _setup(hass)

    # English entity IDs, whatever the UI language.
    for entity_id in (
        "sensor.sleep_tracker_score",
        "sensor.sleep_tracker_score_7_day_average",
        "sensor.sleep_tracker_movements",
        "sensor.sleep_tracker_clustered_movements",
        "sensor.sleep_tracker_longest_undisturbed_sleep",
        "binary_sensor.sleep_tracker_window_active",
        "binary_sensor.sleep_tracker_movement",
        "time.sleep_tracker_window_start",
        "time.sleep_tracker_window_end",
    ):
        assert hass.states.get(entity_id) is not None, entity_id
    assert hass.states.get("binary_sensor.sleep_tracker_window_active").state == "off"

    midnight = evening + timedelta(hours=2)
    await _at(hass, freezer, midnight)
    await _at(hass, freezer, midnight + timedelta(seconds=30))
    assert hass.states.get("binary_sensor.sleep_tracker_window_active").state == "on"
    assert hass.states.get("sensor.sleep_tracker_movements").state == "0"

    await _movement(hass, freezer, midnight + timedelta(hours=1))
    assert hass.states.get("binary_sensor.sleep_tracker_movement").state == "off"
    await _movement(hass, freezer, midnight + timedelta(hours=1, minutes=5))  # clustered
    await _movement(hass, freezer, midnight + timedelta(hours=4))

    assert hass.states.get("sensor.sleep_tracker_movements").state == "3"
    assert hass.states.get("sensor.sleep_tracker_clustered_movements").state == "1"
    assert hass.states.get("sensor.sleep_tracker_longest_undisturbed_sleep").state == "175"

    await _at(hass, freezer, midnight + timedelta(hours=8))
    score = hass.states.get("sensor.sleep_tracker_score")
    attrs = score.attributes
    assert attrs["continuity_minutes"] == 240
    assert attrs["components"]["continuity"] == 30.0
    assert attrs["components"]["movements"] == 25.0
    assert attrs["components"]["wakeups"] == 20.0
    assert attrs["night_of"] == midnight.date().isoformat()
    assert not attrs["neutral_signal"]
    assert float(hass.states.get("sensor.sleep_tracker_score_7_day_average").state) == float(score.state)

    # Once per day: a reload during the grace period does not score again.
    calculated = entry.runtime_data.last_calculation
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.last_calculation == calculated
    assert hass.states.get("sensor.sleep_tracker_score").state == score.state


async def test_three_axes_presence_and_persistence(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    start = dt_util.now().replace(hour=1, minute=0, second=0, microsecond=0)
    freezer.move_to(start)
    axes = ["sensor.bed_x", "sensor.bed_y", "sensor.bed_z"]
    hass.states.async_set("person.sleeper", "not_home")
    hass.states.async_set(axes[0], "0.2")
    hass.states.async_set(axes[1], "unavailable")
    entry = await _setup(hass, accelerometer_sensors=axes, presence_entity="person.sleeper")
    tracker = entry.runtime_data

    # Set up inside the window: the night starts immediately (catch-up).
    assert hass.states.get("sensor.sleep_tracker_movements").state == "0"

    # No signal until every axis reports.
    await _feed(hass, freezer, start + timedelta(seconds=10), [9.80, 9.81], axes[2])
    assert tracker.agitation is None
    hass.states.async_set(axes[1], "-0.1")
    await hass.async_block_till_done()
    # The axis that came back opens a settling period: still no signal.
    assert tracker.is_settling()
    await _feed(hass, freezer, start + timedelta(seconds=30), [9.80, 9.81, 9.80, 9.81, 9.80], axes[2])
    assert tracker.agitation is None
    await _feed(hass, freezer, start + timedelta(minutes=4), [9.80, 9.81, 9.80, 9.81, 9.80], axes[2])
    assert not tracker.is_settling()
    assert tracker.agitation is not None and tracker.agitation < 0.01

    await _feed(hass, freezer, start + timedelta(minutes=6), [3.0, -2.5, 4.0], axes[0])
    assert hass.states.get("binary_sensor.sleep_tracker_movement").state == "on"
    assert hass.states.get("sensor.sleep_tracker_movements").state == "1"

    # Sensors going silent end the movement instead of leaving it stuck.
    await _at(hass, freezer, start + timedelta(minutes=10))
    assert hass.states.get("binary_sensor.sleep_tracker_movement").state == "off"

    # Counters survive a reload.
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.sleep_tracker_movements").state == "1"

    # Nobody home at the end of the window: no score.
    await _at(hass, freezer, start.replace(hour=8))
    assert hass.states.get("sensor.sleep_tracker_score").state == "unknown"


async def test_window_change(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    start = dt_util.now().replace(hour=1, minute=0, second=0, microsecond=0)
    freezer.move_to(start)
    await _setup(hass)
    await hass.services.async_call(
        "time", "set_value", {"entity_id": "time.sleep_tracker_window_end", "time": "06:30:00"}, blocking=True
    )
    assert hass.states.get("time.sleep_tracker_window_end").state == "06:30:00"
    await _at(hass, freezer, start.replace(hour=6, minute=30))
    assert hass.states.get("sensor.sleep_tracker_score").state != "unknown"


def _quiet(count: int) -> list[float]:
    return [QUIET[i % 2] for i in range(count)]


async def _quiet_night(hass, freezer) -> tuple[MockConfigEntry, datetime, float]:
    """Set up inside the window and collect a few quiet minutes once the start-up settling is over."""
    start = dt_util.now().replace(hour=1, minute=0, second=0, microsecond=0)
    freezer.move_to(start)
    hass.states.async_set(ACCEL, "9.81")
    entry = await _setup(hass)
    assert entry.runtime_data.is_settling()
    await _feed(hass, freezer, start + timedelta(seconds=SETTLE_S + 10), _quiet(12))
    night = entry.runtime_data.night
    assert night.samples > 0 and night.maximum < entry.runtime_data.threshold_off
    return entry, start, night.maximum


async def _reconnect(hass, freezer, entry: MockConfigEntry, at: datetime) -> None:
    """A glitch as first value, quiet readings, a second glitch just before the settling ends, then quiet."""
    tracker = entry.runtime_data
    await _feed(hass, freezer, at, [GLITCH, *_quiet(SETTLE_S // 10 - 2)])
    assert tracker.is_settling()
    assert tracker.agitation is None
    assert hass.states.get("binary_sensor.sleep_tracker_movement").state == "off"
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["tracker"]["settling"] is True
    await _feed(hass, freezer, at + timedelta(seconds=SETTLE_S - 10), [GLITCH])
    samples = tracker.night.samples
    await _feed(hass, freezer, at + timedelta(seconds=SETTLE_S + 10), _quiet(18))
    assert not tracker.is_settling()
    assert tracker.night.samples > samples  # the statistics resume after the settling


async def test_settling_after_restart(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    entry, start, maximum = await _quiet_night(hass, freezer)

    # Home Assistant restarts inside the window; the sensor is unavailable until it reconnects.
    restart = start + timedelta(minutes=10)
    await _at(hass, freezer, restart)
    hass.states.async_set(ACCEL, "unavailable")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.is_settling()

    await _reconnect(hass, freezer, entry, restart + timedelta(seconds=10))
    tracker = entry.runtime_data
    assert hass.states.get("sensor.sleep_tracker_movements").state == "0"
    assert tracker.night.maximum == pytest.approx(maximum, rel=0.05)

    await _movement(hass, freezer, restart + timedelta(minutes=15))
    assert hass.states.get("sensor.sleep_tracker_movements").state == "1"


async def test_settling_after_unavailable(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    entry, start, maximum = await _quiet_night(hass, freezer)
    tracker = entry.runtime_data
    assert not tracker.is_settling()

    await _at(hass, freezer, start + timedelta(minutes=7))
    hass.states.async_set(ACCEL, "unavailable")
    await _at(hass, freezer, start + timedelta(minutes=8))

    await _reconnect(hass, freezer, entry, start + timedelta(minutes=9))
    assert hass.states.get("sensor.sleep_tracker_movements").state == "0"
    assert tracker.night.maximum == pytest.approx(maximum, rel=0.05)

    # A real movement after the settling is detected as before.
    await _movement(hass, freezer, start + timedelta(minutes=20))
    assert hass.states.get("sensor.sleep_tracker_movements").state == "1"
    assert tracker.night.maximum > tracker.threshold_on


async def test_set_score(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    start = dt_util.now().replace(hour=1, minute=0, second=0, microsecond=0)
    freezer.move_to(start)
    entry = await _setup(hass)
    tracker = entry.runtime_data
    assert hass.states.get("sensor.sleep_tracker_score").state == "unknown"

    # Defaults: night of today, average untouched.
    await hass.services.async_call(DOMAIN, "set_score", {"config_entry_id": entry.entry_id, "score": 70}, blocking=True)
    score = hass.states.get("sensor.sleep_tracker_score")
    assert score.state == "70"
    assert score.attributes["night_of"] == start.date().isoformat()
    assert hass.states.get("sensor.sleep_tracker_score_7_day_average").state == "unknown"

    await hass.services.async_call(
        DOMAIN,
        "set_score",
        {"config_entry_id": entry.entry_id, "score": 82, "average": 78.5, "night_of": "2026-01-01"},
        blocking=True,
    )
    score = hass.states.get("sensor.sleep_tracker_score")
    assert score.state == "82"
    assert score.attributes["night_of"] == "2026-01-01"
    assert score.attributes["imported"] is True
    assert "components" not in score.attributes  # the card hides the breakdown line
    assert score.attributes["max_points"]
    assert hass.states.get("sensor.sleep_tracker_score_7_day_average").state == "78.5"
    # The night in progress and the once-per-day guard are untouched.
    assert tracker.last_calculation is None
    assert tracker.night.started == start

    # Persisted across a reload.
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.sleep_tracker_score").state == "82"
    assert hass.states.get("sensor.sleep_tracker_score_7_day_average").state == "78.5"

    # The window of the same day still ends with a regular score, averaged from the imported value.
    await _at(hass, freezer, start.replace(hour=8))
    score = hass.states.get("sensor.sleep_tracker_score")
    assert score.attributes["night_of"] == start.date().isoformat()
    assert "imported" not in score.attributes
    assert set(score.attributes["components"]) == {"continuity", "movements", "wakeups", "calm", "intensity"}
    average = float(hass.states.get("sensor.sleep_tracker_score_7_day_average").state)
    assert average == ema(78.5, int(score.state), EMA_ALPHA)


async def test_set_score_errors(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(DOMAIN, "set_score", {"config_entry_id": "missing", "score": 50}, blocking=True)
    assert error.value.translation_key == "entry_not_found"

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "set_score", {"config_entry_id": entry.entry_id, "score": 120}, blocking=True
        )

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN, "set_score", {"config_entry_id": entry.entry_id, "score": 50}, blocking=True
        )
    assert error.value.translation_key == "entry_not_loaded"
