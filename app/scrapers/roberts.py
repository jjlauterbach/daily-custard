"""Scraper for Robert's Frozen Custard (Germantown, WI)."""

import datetime

from app.scrapers.scraper_base import BaseScraper
from app.scrapers.utils import get_central_time

ROBERTS_FLAVOR_CALENDAR_URL = "https://robertsfrozencustard.com/flavor.html"


class RobertsScraper(BaseScraper):
    """Scraper for Robert's Frozen Custard flavor calendar."""

    def __init__(self):
        super().__init__("roberts", "Robert's")

    def scrape(self):
        """Scrape Robert's flavor of the day from their flavor calendar."""
        self.log_start()

        if not self.locations:
            self.log_error("No locations found")
            return []

        location = self.locations[0]
        location_name = location.get("name", self.brand)
        location_url = location.get("url", "https://robertsfrozencustard.com/")

        self.log_location(location_name, ROBERTS_FLAVOR_CALENDAR_URL)

        try:
            html = self.get_html(ROBERTS_FLAVOR_CALENDAR_URL)
            if not html:
                self.log_error("Failed to get HTML")
                return []

            flavor_name, flavor_date = self._extract_todays_flavor(html)
            if not flavor_name:
                self.log_error("No flavor found for today")
                return []

            self.log_flavor(location_name, flavor_name, flavor_date)
            flavor_entry = self.create_flavor(
                location_name,
                flavor_name,
                "",
                flavor_date,
                url=location_url,
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

    def _extract_todays_flavor(self, html):
        """Extract today's flavor from the Flavor Calendar list.

        Returns:
            tuple[str | None, str | None]: (flavor, yyyy-mm-dd) or (None, None)
        """
        today = get_central_time().date()

        calendar_heading = html.find("h1", string=lambda s: s and "flavor calendar" in s.lower())
        if not calendar_heading:
            return None, None

        calendar_list = calendar_heading.find_next("ul")
        if not calendar_list:
            return None, None

        for item in calendar_list.find_all("li"):
            flavor, entry_date = self._parse_calendar_item(item)
            if not flavor or not entry_date:
                continue
            if entry_date == today:
                return flavor, entry_date.strftime("%Y-%m-%d")

        return None, None

    def _parse_calendar_item(self, item):
        """Parse a single calendar <li> into (flavor, date)."""
        lines = [line.strip() for line in item.stripped_strings if line and line.strip()]
        if len(lines) < 2:
            return None, None

        flavor = lines[0]
        date_text = lines[1]

        for fmt in ("%a, %B %d, %Y", "%A, %B %d, %Y"):
            try:
                parsed_date = datetime.datetime.strptime(date_text, fmt).date()
                return flavor, parsed_date
            except ValueError:
                continue

        return None, None


def scrape_roberts():
    """Scrape Robert's Frozen Custard - called by generate_flavors.py."""
    scraper = RobertsScraper()
    return scraper.scrape()
