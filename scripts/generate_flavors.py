#!/usr/bin/env python3
"""
Generate static flavors.json file from all scrapers.

This script is designed to be run by GitHub Actions on a schedule,
generating a static JSON file that can be served directly without
a running backend.
"""

import json
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

# Add the project root to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scrapers.bubbas import scrape_bubbas  # noqa: E402
from app.scrapers.culvers import scrape_culvers  # noqa: E402
from app.scrapers.kopps import scrape_kopps  # noqa: E402
from app.scrapers.murfs import scrape_murfs  # noqa: E402
from app.scrapers.oscars import scrape_oscars  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def load_locations():
    """Load location data from locations.yaml"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    locations_path = os.path.join(project_root, "app", "locations.yaml")

    try:
        with open(locations_path, "r") as f:
            locations_data = yaml.safe_load(f)

        # Create a lookup dict by location name and URL
        location_lookup = {}
        for brand_locations in locations_data.values():
            for loc in brand_locations:
                # Index by name and URL for easy lookup
                location_lookup[loc["name"]] = loc
                location_lookup[loc["url"]] = loc

        logger.info(f"Loaded {len(location_lookup)} location entries from {locations_path}")
        return location_lookup
    except Exception as e:
        logger.warning(f"Could not load locations.yaml: {e}. Continuing without location data.")
        return {}


def enrich_flavor_with_location(flavor, location_lookup):
    """Add location metadata (coordinates, address, etc.) to a flavor entry"""
    # Try to find location by name first, then by URL
    location_data = location_lookup.get(flavor.get("location")) or location_lookup.get(
        flavor.get("url")
    )

    if location_data:
        flavor["location_id"] = location_data["id"]
        flavor["lat"] = location_data["lat"]
        flavor["lng"] = location_data["lng"]
        flavor["address"] = location_data["address"]
        flavor["brand"] = location_data["brand"]

    return flavor


def scrape_all():
    """Run all scrapers and collect flavors."""
    flavors = []
    scrapers = [scrape_culvers, scrape_kopps, scrape_murfs, scrape_oscars, scrape_bubbas]

    # Load location data
    location_lookup = load_locations()

    for scraper in scrapers:
        try:
            logger.info(f"Running {scraper.__name__}...")
            results = scraper()
            # Enrich each flavor with location metadata
            enriched_results = [
                enrich_flavor_with_location(flavor, location_lookup) for flavor in results
            ]
            flavors.extend(enriched_results)
            logger.info(f"  → Got {len(results)} flavor(s)")
        except Exception as err:
            logger.error(f"Scraping error in {scraper.__name__}: {err}", exc_info=True)

    return flavors


def group_flavors_by_location(flavors):
    """
    Group flat list of flavors into location objects.

    Args:
        flavors: List of flavor dictionaries (flat)

    Returns:
        List of location dictionaries with nested flavors
    """
    locations_map = {}

    for entry in flavors:
        # Use location_id as key if available, otherwise sanitize location name
        loc_id = entry.get("location_id")
        if not loc_id:
            loc_name = entry.get("location", "unknown")
            loc_id = loc_name.lower().replace(" ", "-")  # Fallback ID generation

        if loc_id not in locations_map:
            locations_map[loc_id] = {
                "id": loc_id,
                "name": entry.get("location"),
                "address": entry.get("address"),
                "lat": entry.get("lat"),
                "lng": entry.get("lng"),
                "brand": entry.get("brand"),
                "url": entry.get("url"),
                "flavors": [],
            }

        # Add flavor to this location
        # Check for duplicates (same name and date)
        flavor_data = {
            "name": entry.get("flavor"),
            "description": entry.get("description"),
            "date": entry.get("date"),
        }

        # Avoid exact duplicates in the list
        if flavor_data not in locations_map[loc_id]["flavors"]:
            locations_map[loc_id]["flavors"].append(flavor_data)

    return list(locations_map.values())


def generate_static_json():
    """Generate the static flavors.json file."""
    # Get current time in Central timezone
    central_tz = ZoneInfo("America/Chicago")
    now = datetime.now(central_tz)

    logger.info(f"Starting flavor generation at {now.isoformat()}")

    # Scrape all flavors
    flavors = scrape_all()

    # Group flavors by location
    locations = group_flavors_by_location(flavors)

    # Create output data with metadata
    output = {
        "generated_at": now.isoformat(),
        "generated_date": now.strftime("%Y-%m-%d"),
        "flavor_count": len(flavors),
        "location_count": len(locations),
        "locations": locations,
    }

    # Determine output path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_dir = os.path.join(project_root, "static", "data")
    output_path = os.path.join(output_dir, "flavors.json")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Write JSON file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Generated {output_path} with {len(flavors)} flavors")

    return output_path, len(flavors)


if __name__ == "__main__":
    try:
        output_path, count = generate_static_json()
        print(f"✅ Successfully generated {output_path} with {count} flavors")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to generate flavors: {e}", exc_info=True)
        print(f"❌ Failed to generate flavors: {e}")
        sys.exit(1)
