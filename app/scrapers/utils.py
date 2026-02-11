import datetime
import logging
import os
from zoneinfo import ZoneInfo

import yaml

_LOCATION_REGISTRY_CACHE = None


def load_location_registry():
    """Load locations.yaml and cache the parsed data."""
    global _LOCATION_REGISTRY_CACHE
    if _LOCATION_REGISTRY_CACHE is not None:
        return _LOCATION_REGISTRY_CACHE

    locations_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locations.yaml")
    try:
        with open(locations_path, "r", encoding="utf-8") as file:
            _LOCATION_REGISTRY_CACHE = yaml.safe_load(file) or {}
            return _LOCATION_REGISTRY_CACHE
    except Exception as exc:
        logging.warning(f"Failed to load locations registry from {locations_path}: {exc}")
        _LOCATION_REGISTRY_CACHE = {}
        return _LOCATION_REGISTRY_CACHE


def get_locations_for_brand(brand_key):
    """Return enabled locations for a brand key (e.g., 'culvers')."""
    registry = load_location_registry()
    locations = registry.get(brand_key, []) if isinstance(registry, dict) else []
    return [loc for loc in locations if loc.get("enabled", True)]


def get_central_time():
    return datetime.datetime.now(ZoneInfo("America/Chicago"))


def get_central_date_string():
    return get_central_time().strftime("%Y-%m-%d")
