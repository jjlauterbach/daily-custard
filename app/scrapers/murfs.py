import datetime
import re
from zoneinfo import ZoneInfo

from app.scrapers.scraper_base import BaseScraper


class MurfsScraper(BaseScraper):
    """Scraper for Murf's Frozen Custard."""

    def __init__(self):
        super().__init__("murfs")

    def scrape(self):
        """Scrape Murf's Frozen Custard."""
        self.log_start()
        try:
            location = self.locations[0]
            location_name = location.get("name", "Murfs")
            location_url = location.get("url")

            self.log_location(location_name)

            html = self.get_html(location_url)

            # Find the date string in the subDateSpan (e.g., 'Sunday, Jul. 06')
            date_span = html.find("span", {"class": "subDateSpan"})
            flavor_date = None
            if date_span and date_span.text:
                # Parse e.g. 'Sunday, Jul. 06' to '2025-07-06'
                date_text = date_span.text.strip()
                m = re.search(r"([A-Za-z]+\.?)[,]?\s*(\d{2})", date_text)
                if m:
                    month_str, day_str = m.groups()
                    month_map = {
                        "Jan.": 1,
                        "Feb.": 2,
                        "Mar.": 3,
                        "Apr.": 4,
                        "May.": 5,
                        "Jun.": 6,
                        "Jul.": 7,
                        "Aug.": 8,
                        "Sep.": 9,
                        "Oct.": 10,
                        "Nov.": 11,
                        "Dec.": 12,
                    }
                    month = month_map.get(month_str)
                    if month:
                        # Use US Central time for the year
                        central_now = datetime.datetime.now(ZoneInfo("America/Chicago"))
                        year = central_now.year
                        flavor_date = f"{year:04d}-{month:02d}-{int(day_str):02d}"

            flavor_name_tag = html.find("span", {"class": "flavorOfDayWhiteSpan"})
            flavor_name = flavor_name_tag.string.strip() if flavor_name_tag else None

            # Grab the description from the .flavorDescriptionSpan
            desc_tag = html.find("span", {"class": "flavorDescriptionSpan"})
            description = desc_tag.get_text(strip=True) if desc_tag else ""

            if flavor_name and len(flavor_name) > 2:
                self.logger.info(f"🍨 MURFS: Found flavor: {flavor_name} for date: {flavor_date}")
                flavor_entry = self.create_flavor(
                    location_name,
                    flavor_name,
                    description or "",
                    flavor_date,
                    url=location_url,
                )
                self.log_complete(1)
                return [flavor_entry]
            else:
                self.log_error("No flavor name found")
                return []

        except Exception as e:
            self.log_error(f"Failed to scrape: {e}", exc_info=True)
            return []


def scrape_murfs():
    """Scrape Murf's - called by generate_flavors.py."""
    scraper = MurfsScraper()
    return scraper.scrape()
