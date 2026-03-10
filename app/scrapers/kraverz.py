"""Scraper for Kraverz Frozen Custard."""

import re
from datetime import date
from urllib.parse import urljoin

from app.scrapers.scraper_base import BaseScraper
from app.scrapers.utils import get_central_time

# Regex used by `_extract_today_flavor` to pull just today's flavor text from
# flattened page content.
#
# The Kraverz page text often looks like this once HTML is normalized:
# "Today's Flavor of the Day: CLOSED DON’T MISS OUT ON YOUR FAVORITE ..."
#
# Pattern behavior:
# - Match the exact label: "Today's Flavor of the Day:"
# - Skip optional whitespace after the label (`\s*`)
# - Capture flavor text in group(1), allowing common flavor characters,
#   with a safety length bound of 3..80 characters
# - Stop capture at known following section markers (via lookahead),
#   or at end-of-string
#
# This prevents over-capturing into adjacent headings like
# "DON'T MISS OUT" or menu links.
TODAYS_SECTION_PATTERN = re.compile(
    r"Today's Flavor of the Day:\s*([A-Za-z0-9&'’ .\-]{3,80}?)(?=\s+(?:DON[’']?T MISS OUT|View our Flavor Schedule|View Our Menu|Shake of the Month|Menu|Flavor Schedule)\b|$)",
    re.IGNORECASE,
)


class KraverzScraper(BaseScraper):
    """Scraper for Kraverz Frozen Custard."""

    def __init__(self):
        super().__init__("kraverz", "Kraverz")

    def scrape(self):
        """Scrape Kraverz Frozen Custard flavor of the day."""
        self.log_start()

        if not self.locations:
            self.log_error("No locations found")
            return []

        location = self.locations[0]
        location_name = location.get("name", "Kraverz Frozen Custard")
        base_url = location.get("url")

        if not base_url:
            self.log_error("No URL found")
            return []

        schedule_url = urljoin(base_url.rstrip("/") + "/", "FlavorSchedule")
        self.log_location(location_name, schedule_url)

        try:
            html = self.get_html(schedule_url)
            if not html:
                self.log_error("Failed to get HTML")
                return []

            page_text = html.get_text(" ", strip=True)

            flavor_name = self._extract_today_flavor(page_text)
            if not flavor_name:
                today = get_central_time().date()
                flavor_name = self._extract_scheduled_flavor(page_text, today)

            if not flavor_name:
                self.log_error("No flavor of the day found")
                return []

            flavor_name = self._normalize_flavor(flavor_name)
            self.log_flavor(location_name, flavor_name)

            flavor_entry = self.create_flavor(
                location_name,
                flavor_name,
                "",
                None,
                url=base_url,
                location_id=location.get("id"),
                lat=location.get("lat"),
                lng=location.get("lng"),
                address=location.get("address"),
            )
            self.log_complete(1)
            return [flavor_entry]

        except Exception as e:
            self.log_error(f"Failed to scrape: {e}", exc_info=True)
            return []

    def _extract_today_flavor(self, page_text: str) -> str | None:
        """Extract flavor from the explicit "Today's Flavor of the Day" section."""
        match = TODAYS_SECTION_PATTERN.search(page_text)
        if not match:
            return None
        return match.group(1).strip()

    def _extract_scheduled_flavor(self, page_text: str, target_date: date) -> str | None:
        """Extract flavor from the monthly date/flavor schedule line."""
        mmdd = target_date.strftime("%m/%d")
        pattern = re.compile(
            rf"\b{re.escape(mmdd)}\s+([A-Z0-9&'’ .\-]+?)(?=\s+\d{{2}}/\d{{2}}\b|$)",
            re.IGNORECASE,
        )
        match = pattern.search(page_text)
        if not match:
            return None
        return match.group(1).strip()

    def _normalize_flavor(self, flavor_name: str) -> str:
        """Normalize whitespace/casing and keep CLOSED as-is."""
        flavor_name = re.sub(r"\s+", " ", flavor_name).strip(" -–—:;,.\t\n")
        if flavor_name.upper() == "CLOSED":
            return "CLOSED"
        if flavor_name.isupper():
            return flavor_name.title()
        return flavor_name


def scrape_kraverz():
    """Scrape Kraverz - called by generate_flavors.py."""
    scraper = KraverzScraper()
    return scraper.scrape()
