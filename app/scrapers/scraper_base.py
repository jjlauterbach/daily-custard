"""Base class for all scrapers with common functionality."""

import logging
import random
import time
from contextlib import closing

import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from app.scrapers.utils import get_central_date_string, get_locations_for_brand

# Constants
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 30


class BaseScraper:
    """Base class for flavor scrapers."""

    def __init__(self, brand_key):
        """
        Initialize scraper for a brand.

        Args:
            brand_key: String key matching the brand in locations.yaml (e.g., 'culvers', 'kopps')
        """
        self.brand_key = brand_key
        self.logger = logging.getLogger(self.__class__.__name__)
        self.locations = self._load_locations()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _load_locations(self):
        """Load enabled locations for this brand from registry."""
        locations = get_locations_for_brand(self.brand_key)
        if not locations:
            self.logger.warning(f"⚠️ {self.brand_key.upper()}: No locations found in locations.yaml")
        return locations

    def create_flavor(
        self,
        location_name,
        flavor,
        description=None,
        date=None,
        url=None,
        location_id=None,
        lat=None,
        lng=None,
        address=None,
    ):
        """
        Create a flavor entry with location metadata.

        Args:
            location_name: Name of the location
            flavor: Flavor name
            description: Flavor description (optional)
            date: Date string (uses central date if None)
            url: Location URL
            location_id: Location ID from registry
            lat: Latitude
            lng: Longitude
            address: Street address

        Returns:
            dict: Flavor entry
        """
        if date is None:
            date = get_central_date_string()

        result = {
            "location": location_name,
            "flavor": flavor,
            "description": description or "",
            "date": date,
            "url": url,
        }

        if location_id:
            result["location_id"] = location_id
        if lat is not None and lng is not None:
            result["lat"] = lat
            result["lng"] = lng
        if address:
            result["address"] = address

        result["brand"] = self.brand_key.capitalize()

        return result

    def get_location_url(self, index=0):
        """Get URL for a location by index."""
        if index < len(self.locations):
            return self.locations[index].get("url")
        return None

    def get_location_name(self, index=0):
        """Get name for a location by index."""
        if index < len(self.locations):
            return self.locations[index].get("name")
        return None

    def get_all_locations(self):
        """Get all enabled locations."""
        return self.locations

    def get_html(self, url, max_retries=3, use_selenium_fallback=True):
        """Get HTML with retry logic, varying strategies, and optional Selenium fallback"""
        for attempt in range(max_retries):
            html = self._get_html_attempt(url, attempt)
            if html is not None:
                return html
            if attempt < max_retries - 1:
                wait_time = random.uniform(1, 3)
                self.logger.info(f"Retry {attempt + 1} failed, waiting {wait_time:.1f}s")
                time.sleep(wait_time)

        if use_selenium_fallback:
            self.logger.info("All regular requests failed, trying Selenium fallback...")
            return self.get_html_selenium(url)
        return None

    def _get_html_attempt(self, url, attempt):
        self.logger.debug(f"GET {url} (attempt {attempt + 1})")
        delay = random.uniform(1.0, 3.0) + (attempt * random.uniform(0.5, 1.5))
        time.sleep(delay)
        headers = self._get_request_headers(attempt)
        try:
            with closing(
                self.session.get(
                    url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                    stream=False,
                )
            ) as resp:
                if resp.status_code == 403:
                    self.logger.warning(f"403 Forbidden on attempt {attempt + 1}")
                    return None
                elif self._is_valid_response(resp):
                    return BeautifulSoup(resp.text, "html.parser")
                else:
                    self.logger.error(f"Invalid response: status={resp.status_code}")
                    return None
        except RequestException as e:
            self.logger.error(f"Request failed (attempt {attempt + 1}): {e}")
            return None

    def _get_request_headers(self, attempt=0):
        user_agents = [
            USER_AGENT,
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
        ]
        headers = {
            "User-Agent": user_agents[attempt % len(user_agents)],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none" if attempt == 0 else "cross-site",
            "Sec-Fetch-User": "?1",
            "Accept-Charset": "utf-8, iso-8859-1;q=0.5",
        }
        if attempt > 0:
            headers["Referer"] = "https://www.google.com/"
        return headers

    def _is_valid_response(self, resp):
        content_type = resp.headers.get("Content-Type", "").lower()
        return resp.status_code == 200 and content_type is not None and "html" in content_type

    def get_html_selenium(self, url):
        """Get HTML using Selenium WebDriver"""
        options = self._get_chrome_options()
        driver = webdriver.Chrome(options=options)
        try:
            driver.get(url)
            time.sleep(3)
            return BeautifulSoup(driver.page_source, "html.parser")
        finally:
            driver.quit()

    def get_html_selenium_undetected(self, url):
        """Get HTML using undetected-chromedriver if available, fallback to Selenium otherwise"""
        try:
            import undetected_chromedriver as uc

            options = self._get_chrome_options()
            driver = uc.Chrome(options=options)
            try:
                driver.get(url)
                time.sleep(3)
                return BeautifulSoup(driver.page_source, "html.parser")
            finally:
                driver.quit()
        except ImportError:
            self.logger.warning("undetected-chromedriver not available, using standard Selenium")
            return self.get_html_selenium(url)

    def _get_chrome_options(self):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-browser-side-navigation")
        options.add_argument("--disable-features=VizDisplayCompositor")
        return options

    def scrape(self):
        """
        Scrape flavors for all locations.

        Must be implemented by subclasses.

        Returns:
            list: List of flavor dicts
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement scrape()")

    def log_start(self):
        """Log scraper start message."""
        self.logger.info(f"🚀 {self.brand_key.upper()}: Starting scrape...")

    def log_location(self, location_name, url=None):
        """Log location scrape start."""
        self.logger.info(f"📍 {self.brand_key.upper()}: Scraping {location_name}...")

    def log_flavor(self, location_name, flavor, date=None):
        """Log found flavor."""
        date_str = f" ({date})" if date else ""
        self.logger.info(f"🍨 {self.brand_key.upper()}: {location_name} - {flavor}{date_str}")

    def log_complete(self, count):
        """Log scraper completion."""
        self.logger.info(f"✅ {self.brand_key.upper()}: Completed - found {count} flavor(s)")

    def log_error(self, message, exc_info=False):
        """Log error."""
        self.logger.error(f"❌ {self.brand_key.upper()}: {message}", exc_info=exc_info)
