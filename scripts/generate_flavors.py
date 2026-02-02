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


def scrape_all():
    """Run all scrapers and collect flavors."""
    flavors = []
    scrapers = [scrape_culvers, scrape_kopps, scrape_murfs, scrape_oscars, scrape_bubbas]

    for scraper in scrapers:
        try:
            logger.info(f"Running {scraper.__name__}...")
            results = scraper()
            flavors.extend(results)
            logger.info(f"  → Got {len(results)} flavor(s)")
        except Exception as err:
            logger.error(f"Scraping error in {scraper.__name__}: {err}", exc_info=True)

    return flavors


def generate_static_json():
    """Generate the static flavors.json file."""
    # Get current time in Central timezone
    central_tz = ZoneInfo("America/Chicago")
    now = datetime.now(central_tz)

    logger.info(f"Starting flavor generation at {now.isoformat()}")

    # Scrape all flavors
    flavors = scrape_all()

    # Create output data with metadata
    output = {
        "generated_at": now.isoformat(),
        "generated_date": now.strftime("%Y-%m-%d"),
        "flavor_count": len(flavors),
        "flavors": flavors,
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
