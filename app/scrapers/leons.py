"""Scraper for Leon's Frozen Custard using Playwright to scrape Facebook."""

import html
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.scrapers.scraper_base import BaseScraper


class LeonsScraper(BaseScraper):
    """Scraper for Leon's Frozen Custard Facebook page."""

    def __init__(self):
        super().__init__("leons")

    def scrape(self):
        """Scrape Leon's Facebook page for today's flavor."""
        self.log_start()

        if not self.locations:
            self.log_error("No locations found")
            return []

        location = self.locations[0]
        location_name = location.get("name", "Leon's Frozen Custard")
        facebook_url = location.get("facebook")

        if not facebook_url:
            self.log_error("No Facebook URL found in location config")
            return []

        try:
            self.log_location(location_name, facebook_url)
            flavor_text = self._scrape_facebook_page(facebook_url)

            if not flavor_text:
                self.logger.warning("⚠️ LEONS: No flavor post found on Facebook")
                return []

            # Parse the flavor name from the post
            flavor_name = self._extract_flavor_name(flavor_text)

            if not flavor_name:
                self.logger.warning(f"⚠️ LEONS: Could not parse flavor from: {flavor_text[:100]}")
                return []

            self.log_flavor(location_name, flavor_name)

            flavor_entry = self.create_flavor(
                location_name=location_name,
                flavor=flavor_name,
                description=None,
                url=location.get("url"),
                location_id=location.get("id"),
                lat=location.get("lat"),
                lng=location.get("lng"),
                address=location.get("address"),
            )

            self.log_complete(1)
            return [flavor_entry]

        except Exception as e:
            self.log_error(f"Error scraping Leon's: {e}", exc_info=True)
            return []

    def _scrape_facebook_page(self, url):
        """
        Use Playwright to scrape Leon's Facebook page.

        Args:
            url: Facebook page URL

        Returns:
            str: Text content of the most recent flavor post, or None if not found
        """
        with sync_playwright() as p:
            browser = None
            try:
                # Launch browser in headless mode
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                # Navigate to Facebook page
                self.logger.debug(f"Loading Facebook page: {url}")
                page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait for posts to load
                page.wait_for_selector('[role="article"]', timeout=10000)

                # Get all post articles
                articles = page.query_selector_all('[role="article"]')
                self.logger.debug(f"Found {len(articles)} posts on Facebook page")

                # Look through recent posts for flavor information
                for i, article in enumerate(articles[:5]):  # Check first 5 posts
                    text_content = article.inner_text().lower()

                    # Check if this post mentions flavor
                    if "flavor" in text_content and any(
                        keyword in text_content
                        for keyword in ["today", "day", "daily", "of the day"]
                    ):
                        self.logger.debug(f"Found flavor post at index {i}")
                        return article.inner_text()

                self.logger.warning("No recent flavor post found in first 5 posts")
                return None

            except PlaywrightTimeoutError as e:
                self.logger.error(f"Timeout loading Facebook page: {e}")
                return None
            except Exception as e:
                self.logger.error(f"Error with Playwright: {e}")
                return None
            finally:
                if browser:
                    try:
                        browser.close()
                    except Exception:
                        pass

    def _extract_flavor_name(self, text):
        """
        Extract the flavor name from a Facebook post.

        Args:
            text: Full text of the Facebook post

        Returns:
            str: Extracted flavor name, or None if not found
        """
        self.logger.debug(f"Extracting flavor from text: {text[:200]}")

        # Try various patterns to extract the flavor
        patterns = [
            # "BUTTER PECAN is our flavor of the day" - flavor comes BEFORE
            r"([A-Z][A-Z\s&]+?)\s+is\s+(?:our\s+)?(?:the\s+)?flavor(?:\s+of\s+the\s+day)?",
            # "Flavor of the Day: Chocolate" or "Flavor: Chocolate" - flavor comes AFTER
            r"flavor(?:\s+of\s+the\s+day)?[\s:]+(?:is\s+)?([A-Z][^\n.!?]+?)(?:\n|$|!|\.|  )",
            # "Today's flavor: Chocolate"
            r"today'?s?\s+flavor[\s:]+(?:is\s+)?([A-Z][^\n.!?]+?)(?:\n|$|!|\.|  )",
            # "Today: Chocolate" or "Flavor Today: Chocolate"
            r"(?:flavor\s+)?today[\s:]+([A-Z][^\n.!?]+?)(?:\n|$|!|\.|  )",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                flavor = match.group(1).strip()
                # Decode HTML entities
                flavor = html.unescape(flavor)
                # Clean up the flavor name
                # Remove emojis and everything after them
                # Covers: Emoticons, Transport/Map, Misc Symbols, Pictographs, Dingbats
                flavor = re.sub(
                    r"\s*[\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F300-\U0001F5FF"
                    r"\U0001F900-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]+.*$",
                    "",
                    flavor,
                )
                flavor = flavor.split("!")[0].strip()
                flavor = flavor.split("  ")[0].strip()  # Remove double space and after

                # Sanity check: make sure it's a reasonable flavor name
                if 3 < len(flavor) < 100 and not flavor.lower().startswith("of the"):
                    self.logger.debug(f"Extracted flavor using pattern: {flavor}")
                    return flavor

        # Fallback: Look for flavor name in a structured way
        lines = text.split("\n")
        for i, line in enumerate(lines):
            lower_line = line.lower()
            if "flavor" in lower_line:
                # Try the next line first (common format)
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and len(next_line) > 3 and len(next_line) < 100:
                        # Check if it looks like a flavor name (starts with capital)
                        if next_line[0].isupper():
                            # Decode HTML entities
                            next_line = html.unescape(next_line)
                            self.logger.debug(f"Extracted flavor from next line: {next_line}")
                            return next_line.split("!")[0].split(".")[0].strip()

                # Try to extract from the same line
                cleaned = re.sub(
                    r".*?flavor(?:\s+of\s+the\s+day)?[\s:]*", "", line, flags=re.IGNORECASE
                )
                cleaned = cleaned.strip(" :,-!.")
                # Decode HTML entities
                cleaned = html.unescape(cleaned)
                if cleaned and 3 < len(cleaned) < 100 and not cleaned.lower().startswith("is"):
                    self.logger.debug(f"Extracted flavor from same line: {cleaned}")
                    return cleaned.split("!")[0].split(".")[0].strip()

        self.logger.warning("Could not extract flavor name using any method")
        return None


def scrape_leons():
    """
    Standalone function to scrape Leon's Frozen Custard.

    Returns:
        list: List of flavor dicts
    """
    scraper = LeonsScraper()
    return scraper.scrape()
