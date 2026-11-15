"""End-to-end tests: raw acceleration in, sleep score out."""

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.bed_sleep_score.const import DOMAIN

ACCEL = "sensor.bed_accel"
QUIET = (9.805, 9.815)
SPIKES = (9.2, 10.5, 9.0)


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
    await _feed(hass, freezer, start + timedelta(seconds=30), [9.80, 9.81, 9.80, 9.81, 9.80], axes[2])
    assert tracker.agitation is not None and tracker.agitation < 0.01

    await _feed(hass, freezer, start + timedelta(minutes=2), [3.0, -2.5, 4.0], axes[0])
    assert hass.states.get("binary_sensor.sleep_tracker_movement").state == "on"
    assert hass.states.get("sensor.sleep_tracker_movements").state == "1"

    # Sensors going silent end the movement instead of leaving it stuck.
    await _at(hass, freezer, start + timedelta(minutes=6))
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
