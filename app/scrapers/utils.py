import datetime
import logging
import os
import re
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


def is_facebook_post_from_today(article, logger=None, article_text=None):
    """
    Check if a Facebook post is from today by examining its timestamp.

    Facebook shows relative timestamps:
    - "Just now", "Xm" (minutes), "Xh" (hours) = today
    - "1d", "2d" (days) = not today
    - Specific dates = not today

    Args:
        article: Playwright ElementHandle for the post article
        logger: Optional logger for debug messages
        article_text: Pre-fetched inner text of the article. When provided,
            avoids an extra cross-process Playwright call.

    Returns:
        bool: True if post is from today, False otherwise
    """
    try:
        # Use pre-fetched text if provided to avoid a duplicate cross-process call;
        # fall back to fetching from the article element when not supplied.
        if article_text is None:
            article_text = article.inner_text()

        # Look at the first 200 characters where timestamps typically appear
        header_text = article_text[:200]

        # Patterns that indicate the post is from today:
        # - "Just now"
        # - "Xm" or "X mins" (minutes ago)
        # - "Xh" or "X hrs" or "X hours" (hours ago)
        today_patterns = [
            r"\bjust now\b",
            r"\b\d+\s*m\b",  # "5m", "30 m"
            r"\b\d+\s*min",  # "5 mins", "30 minutes"
            r"\b\d+\s*h\b",  # "1h", "23 h"
            r"\b\d+\s*hr",  # "1 hr", "2 hrs", "3 hours"
        ]

        # Patterns that indicate the post is NOT from today:
        # - "Xd" or "X days" (days ago)
        # - Explicit calendar dates with month names or abbreviations
        not_today_patterns = [
            r"\b\d+\s*d\b",  # "1d", "2 d"
            r"\b\d+\s*day",  # "1 day", "2 days"
            # Full month name followed by a day number, e.g., "May 3"
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b",
            # Abbreviated month (optionally with a period) followed by a day number, e.g., "May 3", "Jan. 12"
            r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s+\d{1,2}\b",
        ]

        header_lower = header_text.lower()

        # Check for "not today" patterns first (more specific)
        for pattern in not_today_patterns:
            if re.search(pattern, header_lower):
                if logger:
                    logger.debug(f"Post timestamp indicates NOT today (matched: {pattern})")
                return False

        # Check for "today" patterns
        for pattern in today_patterns:
            if re.search(pattern, header_lower):
                if logger:
                    logger.debug(f"Post timestamp indicates today (matched: {pattern})")
                return True

        # If we can't find any recognizable timestamp, assume it might be today
        # (better to check the post than skip it)
        if logger:
            logger.debug("Could not parse timestamp, assuming post might be from today")
        return True

    except Exception as e:
        # If something goes wrong, assume the post might be from today
        # (better to check than skip)
        if logger:
            logger.warning(f"Error checking post timestamp: {e}")
        return True
