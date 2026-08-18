"""Scraper for Robert's Frozen Custard (Germantown, WI)."""

import datetime
import time

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.scrapers.scraper_base import USER_AGENT, BaseScraper
from app.scrapers.utils import get_central_time

# Website moved from /flavor.html to /page/see-this-months-flavors.
# Try the new URL first; fall back to the legacy URL in case it comes back.
ROBERTS_FLAVOR_CALENDAR_URL = "https://robertsfrozencustard.com/page/see-this-months-flavors"
ROBERTS_FLAVOR_CALENDAR_URL_LEGACY = "https://robertsfrozencustard.com/flavor.html"

PAGE_TIMEOUT = 30000  # 30 seconds
WAIT_AFTER_LOAD = 3000  # 3 seconds — allows Cloudflare JS challenge to resolve


class RobertsScraper(BaseScraper):
    """Scraper for Robert's Frozen Custard flavor calendar."""

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2  # seconds; doubles each attempt (2s, 4s)

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
            html = self._fetch_page(ROBERTS_FLAVOR_CALENDAR_URL)
            if html is None:
                self.logger.info("Primary URL failed; trying legacy URL...")
                html = self._fetch_page(ROBERTS_FLAVOR_CALENDAR_URL_LEGACY)
            if html is None:
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

    # ------------------------------------------------------------------
    # Playwright-based page fetching
    # ------------------------------------------------------------------

    def _fetch_page(self, url):
        """Fetch a page with Playwright and return parsed BeautifulSoup.

        Uses retry/backoff for transient Playwright errors.  Playwright
        handles the Cloudflare JS challenge that blocks plain HTTP requests.

        Args:
            url: URL to fetch

        Returns:
            BeautifulSoup | None: Parsed HTML, or None if all attempts fail
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                return self._fetch_page_attempt(url, attempt)
            except PlaywrightTimeoutError as e:
                if not self._handle_retry(attempt, f"Timeout: {e}"):
                    return None
            except PlaywrightError as e:
                if not self._handle_retry(attempt, f"Playwright error: {e}"):
                    return None
            except Exception as e:
                self.logger.error(f"Unexpected error on attempt {attempt + 1}: {e}", exc_info=True)
                return None
        return None

    def _fetch_page_attempt(self, url, attempt):
        """Single Playwright attempt to load *url* and return a BeautifulSoup.

        Args:
            url: URL to load
            attempt: 0-based attempt index (used for logging)

        Returns:
            BeautifulSoup: Parsed page HTML

        Raises:
            PlaywrightTimeoutError: On navigation timeout
            PlaywrightError: On other Playwright errors
        """
        self.logger.debug(f"Loading page (attempt {attempt + 1}): {url}")
        with sync_playwright() as p:
            browser = None
            try:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=USER_AGENT)
                page.set_default_timeout(PAGE_TIMEOUT)
                page.set_default_navigation_timeout(PAGE_TIMEOUT)
                page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
                # Extra wait so that the Cloudflare JS challenge can complete
                # and the real page content is rendered.
                page.wait_for_timeout(WAIT_AFTER_LOAD)
                return BeautifulSoup(page.content(), "html.parser")
            finally:
                if browser:
                    try:
                        browser.close()
                    except Exception:
                        pass

    def _handle_retry(self, attempt, error_message):
        """Log a warning and sleep with exponential backoff before the next retry.

        Args:
            attempt: 0-based current attempt index
            error_message: Human-readable description of what went wrong

        Returns:
            bool: True if a retry should be attempted; False if attempts exhausted
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

    # ------------------------------------------------------------------
    # Flavor extraction
    # ------------------------------------------------------------------

    def _extract_todays_flavor(self, html):
        """Extract today's flavor from the Flavor Calendar list.

        Searches for a heading (h1–h4) whose text contains "flavor calendar"
        or "this month", then parses the first <ul> that follows it.  This
        handles both the legacy /flavor.html layout (h1 heading) and the
        current /page/see-this-months-flavors layout (h2 heading).

        Returns:
            tuple[str | None, str | None]: (flavor, yyyy-mm-dd) or (None, None)
        """
        today = get_central_time().date()

        calendar_heading = None
        for heading in html.find_all(["h1", "h2", "h3", "h4"]):
            text = heading.get_text(strip=True).lower()
            if "flavor calendar" in text or "this month" in text:
                calendar_heading = heading
                break

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
        """Parse a single calendar <li> into (flavor, date).

        Expects each <li> to contain at least two text nodes:
            lines[0] – flavor name
            lines[1] – date string, e.g. "Mon, March 9, 2026"

        Returns:
            tuple[str | None, datetime.date | None]
        """
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
