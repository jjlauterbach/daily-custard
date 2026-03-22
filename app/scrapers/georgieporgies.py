"""Scraper for Georgie Porgie's flavor forecast."""

import re

from app.scrapers.scraper_base import BaseScraper

GEORGIE_PORGIES_FORECAST_URL = "https://georgieporgies.com/georgies-flavor-forecast/"


class GeorgiePorgiesScraper(BaseScraper):
    """Scraper for Georgie Porgie's Treefort."""

    def __init__(self):
        super().__init__("georgieporgies", "Georgie Porgie's")

    def scrape(self):
        """Scrape today's flavor from Georgie Porgie's forecast page."""
        self.log_start()

        if not self.locations:
            self.log_error("No locations found")
            return []

        try:
            html = self.get_html(GEORGIE_PORGIES_FORECAST_URL)
            if not html:
                self.log_error("Failed to get HTML")
                return []

            flavor_name, description = self._extract_todays_flavor(html)
            if not flavor_name:
                self.log_error("No flavor found for today")
                return []

            flavors = []
            for location in self.locations:
                location_name = location.get("name", self.brand)
                location_url = location.get("url", "https://georgieporgies.com")
                self.log_location(location_name, GEORGIE_PORGIES_FORECAST_URL)
                self.log_flavor(location_name, flavor_name)

                flavor_entry = self.create_flavor(
                    location_name,
                    flavor_name,
                    description,
                    None,
                    url=location_url,
                    location_id=location.get("id"),
                    lat=location.get("lat"),
                    lng=location.get("lng"),
                    address=location.get("address"),
                )
                flavors.append(flavor_entry)

            self.log_complete(len(flavors))
            return flavors
        except Exception as e:
            self.log_error(f"Failed to scrape: {e}", exc_info=True)
            return []

    def _extract_todays_flavor(self, html):
        """Extract today's flavor name and description from forecast HTML."""
        heading = html.find(
            ["h1", "h2", "h3", "h4"],
            string=lambda text: text and "today" in text.lower() and "flavor" in text.lower(),
        )
        if not heading:
            return None, ""

        image = heading.find_next("img")
        description = ""
        if image:
            desc_tag = image.find_next("p")
            if desc_tag:
                description = desc_tag.get_text(" ", strip=True)
        else:
            desc_tag = heading.find_next("p")
            if desc_tag:
                description = desc_tag.get_text(" ", strip=True)

        flavor_name = self._extract_flavor_from_image_alt(image.get("alt", "") if image else "")
        if not flavor_name:
            flavor_name = self._extract_flavor_from_description(description)

        return flavor_name, description

    def _extract_flavor_from_image_alt(self, alt_text):
        """Extract flavor name from image alt text when available."""
        if not alt_text:
            return None

        cleaned_alt = alt_text.strip()
        if "closed" in cleaned_alt.lower():
            return "Closed"

        match = re.search(r"flavor\s+of\s+the\s+day\s*-\s*(.+)", cleaned_alt, re.IGNORECASE)
        if not match:
            return None

        return match.group(1).strip(" -")

    def _extract_flavor_from_description(self, description):
        """Fallback extraction when only a closed message is present."""
        if description and "closed" in description.lower():
            return "Closed"
        return None


def scrape_georgieporgies():
    """Scrape Georgie Porgie's - called by generate_flavors.py."""
    scraper = GeorgiePorgiesScraper()
    return scraper.scrape()
