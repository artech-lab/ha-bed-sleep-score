# SPDX-License-Identifier: GPL-3.0-or-later
"""Constants for the Bed Sleep Score integration."""

from __future__ import annotations

from datetime import time
from typing import Final

DOMAIN: Final = "bed_sleep_score"
DEFAULT_NAME: Final = "Sleep tracker"
FORMULA_VERSION: Final = 3

# Bundled dashboard card
CARD_FILENAME: Final = "bed-sleep-score-card.js"
CARD_URL: Final = f"/{DOMAIN}/{CARD_FILENAME}"

# Config entry keys
CONF_SENSORS: Final = "accelerometer_sensors"
CONF_PRESENCE_ENTITY: Final = "presence_entity"
CONF_THRESHOLD: Final = "movement_threshold"
CONF_WINDOW_START: Final = "window_start"
CONF_WINDOW_END: Final = "window_end"

DEFAULT_WINDOW_START: Final = time(0, 0)
DEFAULT_WINDOW_END: Final = time(8, 0)

# ---------------------------------------------------------------- analysis
# The signal is the rolling standard deviation of the acceleration magnitude
# (m/s²). Every anchor below is calibrated on a bed-mounted MPU6050 and scales
# with the movement threshold, which is the only user-facing tuning knob.
STD_DEV_WINDOW_S: Final = 120
MIN_WINDOW_SAMPLES: Final = 5
# After the tracker starts, or an axis becomes numeric again after being
# unavailable/unknown, the readings are discarded for this long: the first
# values after a reconnection are often off and would hold the agitation above
# the threshold for a whole standard-deviation window. One full window plus a
# minute of margin lets the sensor stabilise; the analysis then restarts from
# an empty window, so nothing collected while settling can trigger a movement.
SETTLE_S: Final = STD_DEV_WINDOW_S + 60
DEFAULT_THRESHOLD: Final = 0.102  # a movement starts above this agitation
THRESHOLD_OFF_RATIO: Final = 0.765  # ... and ends below threshold * ratio
CALM_FULL: Final = 0.008  # net agitation (mean - min) for full calm points
CALM_ZERO: Final = 0.020
PEAK_FULL: Final = 0.3  # peak agitation for full intensity points
PEAK_ZERO: Final = 3.0

# ----------------------------------------------------------------- scoring
CLUSTER_MINUTES: Final = 15  # a movement this close to the previous one is "clustered"
CONTINUITY_FULL_MIN: Final = 120.0  # ≈ one complete sleep cycle (90-110 min)
CONTINUITY_ZERO_MIN: Final = 30.0
CONTINUITY_CAP_MIN: Final = 720
FREE_MOVEMENTS: Final = 8
MOVEMENTS_ZERO_AT: Final = 20
FREE_CLUSTERS: Final = 2
CLUSTERS_ZERO_AT: Final = 8
MIN_NIGHT_SAMPLES: Final = 10  # below this, calm/intensity fall back to neutral
EMA_ALPHA: Final = 0.25  # "7-day" exponential moving average
GRACE_HOURS: Final = 3  # catch-up after a restart

MAX_POINTS: Final = {"continuity": 30, "movements": 25, "wakeups": 20, "calm": 15, "intensity": 10}

# ----------------------------------------------------------------- actions
SERVICE_SET_SCORE: Final = "set_score"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_SCORE: Final = "score"
ATTR_AVERAGE: Final = "average"
ATTR_NIGHT_OF: Final = "night_of"

PRESENCE_HOME_STATES: Final = frozenset({"home", "on"})
STORAGE_VERSION: Final = 1
