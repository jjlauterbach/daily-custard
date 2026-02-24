"""Scraper for Le Duc's Frozen Custard."""

import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.scrapers.scraper_base import USER_AGENT, BaseScraper

# Timeouts
PAGE_TIMEOUT = 30000  # 30s
WAIT_AFTER_LOAD = 2000  # 2s after domcontentloaded for JS to settle


class LeducsScraper(BaseScraper):
    """Scraper for Le Duc's Frozen Custard.

    Scrapes the homepage for today's flavor.  The homepage shows 'CLOSED'
    prominently when the store is not open, so it is used as the authoritative
    source for both closed-day detection and flavor extraction.
    """

    def __init__(self):
        super().__init__("leducs")

    def scrape(self):
        """Scrape Le Duc's Frozen Custard."""
        self.log_start()

        if not self.locations:
            self.log_error("No locations found")
            return []

        location = self.locations[0]
        location_name = location.get("name", "LeDuc's Frozen Custard")
        base_url = location.get("url", "").rstrip("/")

        if not base_url:
            self.log_error("No URL found")
            return []

        try:
            self.log_location(location_name, base_url)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page(user_agent=USER_AGENT)
                    page.set_default_timeout(PAGE_TIMEOUT)

                    # Load the homepage — it shows both "CLOSED" and the flavor
                    page.goto(base_url, wait_until="domcontentloaded")
                    page.wait_for_timeout(WAIT_AFTER_LOAD)

                    page_text = page.inner_text("body")
                    self.logger.debug(
                        f"📄 LEDUCS: Page text (first 500 chars): {page_text[:500]!r}"
                    )

                    flavor_name = self._extract_flavor(page_text)

                    if flavor_name:
                        flavor_name = self._clean_flavor_name(flavor_name)
                        self.log_flavor(location_name, flavor_name)
                        flavor_entry = self.create_flavor(
                            location_name,
                            flavor_name,
                            "",
                            None,
                            url=base_url,
                        )
                        self.log_complete(1)
                        return [flavor_entry]
                    else:
                        self.log_error("Could not determine today's flavor")
                        return []

                finally:
                    browser.close()

        except PlaywrightTimeoutError as e:
            self.log_error(f"Page load timed out: {e}")
            return []
        except Exception as e:
            self.log_error(f"Failed to scrape: {e}", exc_info=True)
            return []

    def _extract_flavor(self, page_text: str) -> str | None:
        """Extract flavor from page text, returning None if the store is closed.

        The Le Duc's homepage renders a "FLAVOR OF THE DAY" block that looks like:
            FLAVOROF THE DAY
            CHOCOLATE PEANUT BUTTER CUP
            ◦ SUNDAY, FEB 22
        On closed days the same block shows "CLOSED" instead of a flavor name.
        """
        # Match the FLAVOR OF THE DAY block and capture whatever follows it
        match = re.search(
            r"FLAVOR\s*OF\s*THE\s*DAY\s*\n\s*([^\n]+)",
            page_text,
            re.IGNORECASE,
        )
        if not match:
            self.logger.warning("⚠️ LEDUCS: Could not find 'FLAVOR OF THE DAY' block")
            return None

        candidate = match.group(1).strip()
        self.logger.info(f"🍨 LEDUCS: Flavor candidate: {candidate!r}")

        return candidate

    def _clean_flavor_name(self, flavor_name: str) -> str:
        """Clean up extracted flavor name."""
        # Remove leading numbers / dates
        flavor_name = re.sub(r"^\d+\s*[/-]?\s*\d*\s*", "", flavor_name)

        # Remove day names at the start
        flavor_name = re.sub(
            r"^(SUNDAY|MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY)[,\s]*",
            "",
            flavor_name,
            flags=re.IGNORECASE,
        )

        # Remove bullet points and dashes at the start
        flavor_name = re.sub(r"^[•◦▪▫\-–—]\s*", "", flavor_name)

        # Title-case if all caps
        if flavor_name.isupper():
            flavor_name = flavor_name.title()

        return flavor_name.strip()


def scrape_leducs():
    """Scrape Le Duc's - called by generate_flavors.py."""
    scraper = LeducsScraper()
    return scraper.scrape()
