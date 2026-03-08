"""Scraper for Hefner's Custard (Cedarburg, WI)."""

import re

from app.scrapers.scraper_base import BaseScraper

HEFNERS_URL = "https://www.hefnerscustard.com/"

# Matches "FLAVOR OF THE DAY" case-insensitively; also handles condensed
# forms such as "FLAVOROF THE DAY" occasionally seen in page extraction.
LABEL_PATTERN = re.compile(r"flavor\s*of\s*the\s*day", re.IGNORECASE)

# Keywords that identify monthly specials (NOT the daily flavor)
MONTHLY_KEYWORDS = ["SHAKE", "SUNDAE", "SANDWICH", "ROLL", "BURGER"]


class HefnersScraper(BaseScraper):
    """Scraper for Hefner's Custard."""

    def __init__(self):
        super().__init__("hefners", "Hefner's")

    def scrape(self):
        """Scrape Hefner's Custard flavor of the day."""
        self.log_start()

        if not self.locations:
            self.log_error("No locations found")
            return []

        location = self.locations[0]
        location_name = location.get("name", self.brand)
        location_url = location.get("url", HEFNERS_URL)

        self.log_location(location_name, location_url)

        try:
            html = self.get_html(location_url)
            if not html:
                self.log_error("Failed to get HTML")
                return []

            flavor_name, description = self._extract_flavor(html)

            if not flavor_name:
                self.log_error("No flavor of the day found")
                return []

            self.log_flavor(location_name, flavor_name)

            flavor_entry = self.create_flavor(
                location_name,
                flavor_name,
                description or "",
                None,
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

    def _get_next_description(self, h3):
        """Return the text of the first <p> sibling after h3, or empty string.

        Args:
            h3 (Tag): BeautifulSoup tag representing the flavor name heading.

        Returns:
            str: Description text, or empty string if no suitable sibling found.
        """
        next_elem = h3.find_next_sibling()
        while next_elem and next_elem.name not in ("p", "h3", "h2", "div"):
            next_elem = next_elem.find_next_sibling()
        if next_elem and next_elem.name == "p":
            desc_text = next_elem.get_text(strip=True)
            if desc_text and len(desc_text) > 5:
                return desc_text
        return ""

    def _extract_flavor(self, html):
        """
        Extract flavor name and description from the Hefner's homepage.

        Primary strategy: locate any text node that matches "FLAVOR OF THE DAY"
        (case-insensitive; also handles condensed forms such as "FLAVOROF THE DAY"),
        then return the next <h3> element as the flavor name.

        Fallback strategy: return the first <h3> that does not match a monthly-special
        keyword (SHAKE, SUNDAE, SANDWICH, ROLL, BURGER) when no label is found.

        Returns:
            tuple: (flavor_name, description) or (None, None) if not found
        """
        # Primary: anchor on the "FLAVOR OF THE DAY" label text node
        for label_text in html.find_all(string=LABEL_PATTERN):
            h3 = label_text.parent.find_next("h3")
            if h3:
                flavor_name = h3.get_text(strip=True)
                if flavor_name and len(flavor_name) >= 3:
                    return flavor_name, self._get_next_description(h3)

        # Fallback: first h3 that isn't a monthly special
        for h3 in html.find_all("h3"):
            flavor_name = h3.get_text(strip=True)
            if not flavor_name or len(flavor_name) < 3:
                continue
            if any(kw in flavor_name.upper() for kw in MONTHLY_KEYWORDS):
                continue
            return flavor_name, self._get_next_description(h3)

        return None, None


def scrape_hefners():
    """Scrape Hefner's - called by generate_flavors.py."""
    scraper = HefnersScraper()
    return scraper.scrape()
