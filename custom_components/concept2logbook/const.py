"""Constants for the Concept2 Logbook integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "concept2logbook"
NAME = "Concept2 Logbook"
VERSION = "0.1.0"

CONF_ACCESS_TOKEN = "access_token"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_PROFILE_ID = "profile_id"
CONF_PROFILE_NAME = "profile_name"
CONF_SUMMARY_PERIODS = "summary_periods"
CONF_WORKOUT_TYPES = "workout_types"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)
MIN_SCAN_INTERVAL_SECONDS = 300

DEFAULT_SUMMARY_PERIODS = ["all_time"]
DEFAULT_WORKOUT_TYPES = ["all"]

SUMMARY_PERIODS = {
    "all_time": "All time",
    "current_year": "Current year",
    "current_month": "Current month",
    "last_30_days": "Last 30 days",
    "last_7_days": "Last 7 days",
    "concept2_season": "Concept2 season",
}

WORKOUT_TYPES = {
    "all": "All workout types",
    "rower": "RowErg",
    "skierg": "SkiErg",
    "bikeerg": "BikeErg",
}

PLATFORMS = ["sensor"]
