"""Scraper for Georgie Porgie's flavor forecast."""

import re

from bs4 import BeautifulSoup

from app.scrapers.scraper_base import USER_AGENT, BaseScraper
from app.scrapers.utils import get_central_date_string

GEORGIE_PORGIES_FORECAST_URL = "https://georgieporgies.com/georgies-flavor-forecast/"
PAGE_TIMEOUT = 30000  # 30s
WAIT_AFTER_LOAD = 2500  # 2.5s after domcontentloaded for JS to settle


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
            html = self.get_html(GEORGIE_PORGIES_FORECAST_URL, use_selenium_fallback=False)
            if not html:
                self.logger.warning(
                    "GEORGIEPORGIES: Initial HTML fetch returned no content; trying Playwright browser fetch"
                )
                html = self._try_playwright_browser_fetch(GEORGIE_PORGIES_FORECAST_URL)
                if not html:
                    self.log_error("Failed to get HTML")
                    return []

            flavor_name, description, extraction_path = self._extract_todays_flavor(html)
            if extraction_path:
                self.logger.info(
                    f"GEORGIEPORGIES: Extracted today's flavor using {extraction_path} path"
                )
            if not flavor_name:
                self.logger.warning(
                    "GEORGIEPORGIES: No flavor found; trying Playwright browser fetch"
                )
                html = self._try_playwright_browser_fetch(GEORGIE_PORGIES_FORECAST_URL) or html
                flavor_name, description, extraction_path = self._extract_todays_flavor(html)
                if extraction_path:
                    self.logger.info(
                        f"GEORGIEPORGIES: Extracted today's flavor using {extraction_path} path"
                    )
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
        flavor_name, description = self._extract_todays_flavor_from_data_date(html)
        if flavor_name:
            return flavor_name, description, "data-date"

        heading = self._find_legacy_today_heading(html)
        if not heading:
            return None, "", None

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

        if flavor_name:
            return flavor_name, description, "legacy-heading"

        return None, description, None

    def _extract_todays_flavor_from_data_date(self, html):
        """Extract today's flavor from forecast rows that include a YYYY-MM-DD data-date."""
        today = get_central_date_string()
        flavor_item = html.select_one(f'.flavor-item[data-date="{today}"]')
        if not flavor_item:
            return None, ""

        name_tag = flavor_item.select_one(".flavor-list-name")
        desc_tag = flavor_item.select_one(".flavor-list-desc")

        flavor_name = name_tag.get_text(" ", strip=True) if name_tag else ""
        description = desc_tag.get_text(" ", strip=True) if desc_tag else ""
        flavor_name = flavor_name.strip(" -\u2014")

        if not flavor_name:
            if description and "closed" in description.lower():
                return "Closed", description
            return None, description
        if "closed" in flavor_name.lower():
            return "Closed", description

        return flavor_name, description

    def _find_legacy_today_heading(self, html):
        """Locate the legacy heading that introduces today's flavor section."""
        for heading in html.find_all(["h1", "h2", "h3", "h4"]):
            heading_text = heading.get_text(" ", strip=True).lower()
            if "flavor of the day" in heading_text or (
                "today" in heading_text and "flavor" in heading_text
            ):
                return heading
        return None

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

    def _try_playwright_browser_fetch(self, url):
        """Attempt Playwright browser fetch when initial extraction fails."""
        try:
            self.logger.info("GEORGIEPORGIES: Trying Playwright browser fetch...")
            return self._get_html_playwright(url)
        except Exception as exc:
            self.logger.warning(f"GEORGIEPORGIES: Playwright fetch failed: {exc}")
        return None

    def _get_html_playwright(self, url):
        """Get HTML using Playwright as a fallback browser strategy."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = None
            try:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.set_default_timeout(PAGE_TIMEOUT)
                page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
                page.wait_for_timeout(WAIT_AFTER_LOAD)
                return BeautifulSoup(page.content(), "html.parser")
            finally:
                if browser:
                    browser.close()


def scrape_georgieporgies():
    """Scrape Georgie Porgie's - called by generate_flavors.py."""
    scraper = GeorgiePorgiesScraper()
    return scraper.scrape()
