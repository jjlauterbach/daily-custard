"""Scraper for Le Duc's Frozen Custard."""

import re
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.scrapers.scraper_base import USER_AGENT, BaseScraper

# Timeouts
PAGE_TIMEOUT = 30000  # 30s
WAIT_AFTER_LOAD = 2000  # 2s after domcontentloaded for JS to settle


class LeducsScraper(BaseScraper):
    """Scraper for Le Duc's Frozen Custard.

    Scrapes the homepage for today's flavor.
    """

    MAX_RETRIES = 3  # Number of retry attempts for transient Playwright errors
    RETRY_BASE_DELAY = 2  # Base delay in seconds; doubled each attempt (2s, 4s)

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
        base_url = location.get("url", "")

        if not base_url:
            self.log_error("No URL found")
            return []

        try:
            self.log_location(location_name, base_url)

            page_text = self._scrape_page(base_url)

            if page_text is None:
                self.log_error("Could not load page after retries")
                return []

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

        except Exception as e:
            self.log_error(f"Failed to scrape: {e}", exc_info=True)
            return []

    def _scrape_page(self, url):
        """Scrape the Le Duc's homepage with retry/backoff on transient Playwright errors.

        Args:
            url: Homepage URL to scrape

        Returns:
            str: Page body text, or None if all attempts failed
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                return self._scrape_page_attempt(url, attempt)
            except PlaywrightTimeoutError as e:
                if not self._handle_retry(attempt, f"Timeout: {e}"):
                    return None
            except PlaywrightError as e:
                if not self._handle_retry(attempt, f"Playwright error: {e}"):
                    return None
            except Exception as e:
                self.logger.error(
                    f"Unexpected error on attempt {attempt + 1}: {e}", exc_info=True
                )
                return None
        return None

    def _handle_retry(self, attempt, error_message):
        """Handle retry logic with exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)
            error_message: Error message to log

        Returns:
            bool: True if should retry, False if max retries reached
        """
        if attempt < self.MAX_RETRIES - 1:
            delay = self.RETRY_BASE_DELAY * (2**attempt)
            self.logger.warning(
                f"{error_message} on attempt {attempt + 1}/{self.MAX_RETRIES}. "
                f"Retrying in {delay}s..."
            )
            time.sleep(delay)
            return True

        self.logger.error(f"{error_message} after {self.MAX_RETRIES} attempts")
        return False

    def _scrape_page_attempt(self, url, attempt):
        """Single attempt to load the Le Duc's homepage and return body text.

        Args:
            url: Homepage URL to scrape
            attempt: Current attempt number (0-indexed)

        Returns:
            str: Page body text

        Raises:
            PlaywrightTimeoutError: If page load times out
            PlaywrightError: For other Playwright errors
            Exception: For unexpected errors
        """
        with sync_playwright() as p:
            browser = None
            try:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.set_default_timeout(PAGE_TIMEOUT)

                self.logger.debug(f"Loading page (attempt {attempt + 1}): {url}")
                # Load the homepage — it shows both "CLOSED" and the flavor
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(WAIT_AFTER_LOAD)

                page_text = page.inner_text("body")
                self.logger.debug(
                    f"📄 LEDUCS: Page text (first 500 chars): {page_text[:500]!r}"
                )
                return page_text
            finally:
                if browser:
                    try:
                        browser.close()
                    except Exception:
                        pass

    def _extract_flavor(self, page_text: str) -> str | None:
        """Extract flavor from page text.

        The Le Duc's homepage renders a "FLAVOR OF THE DAY" block that looks like:
            FLAVOROF THE DAY
            CHOCOLATE PEANUT BUTTER CUP
            ◦ SUNDAY, FEB 22
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
