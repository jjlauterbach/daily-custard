"""Scraper for Big Deal Burgers using Playwright to scrape Facebook."""

import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.scrapers.scraper_base import USER_AGENT, BaseScraper
from app.scrapers.utils import is_facebook_post_from_today


class BigDealScraper(BaseScraper):
    """Scraper for Big Deal Burgers Facebook page."""

    def __init__(self):
        super().__init__("bigdeal")

    def scrape(self):
        """Scrape Big Deal Burgers Facebook page for today's flavor."""
        self.log_start()

        if not self.locations:
            self.log_error("No locations found")
            return []

        location = self.locations[0]
        location_name = location.get("name", "Big Deal Burgers")
        facebook_url = location.get("facebook")

        if not facebook_url:
            self.log_error("No Facebook URL found in location config")
            return []

        try:
            self.log_location(location_name, facebook_url)
            flavor_text = self._scrape_facebook_page(facebook_url)

            if not flavor_text:
                self.logger.warning("⚠️ BIGDEAL: No flavor post found on Facebook")
                return []

            # Parse the flavor name and description from the post
            flavor_name, description = self._extract_flavor_name(flavor_text)

            if not flavor_name:
                self.logger.warning(f"⚠️ BIGDEAL: Could not parse flavor from: {flavor_text[:100]}")
                return []

            self.log_flavor(location_name, flavor_name)

            flavor_entry = self.create_flavor(
                location_name=location_name,
                flavor=flavor_name,
                description=description,
                url=location.get("url"),
                location_id=location.get("id"),
                lat=location.get("lat"),
                lng=location.get("lng"),
                address=location.get("address"),
            )

            self.log_complete(1)
            return [flavor_entry]

        except Exception as e:
            self.log_error(f"Error scraping Big Deal Burgers: {e}", exc_info=True)
            return []

    def _scrape_facebook_page(self, url):
        """
        Use Playwright to scrape Big Deal Burgers Facebook page.

        Args:
            url: Facebook page URL

        Returns:
            str: Text content of the most recent flavor post, or None if not found
        """
        with sync_playwright() as p:
            try:
                # Launch browser in headless mode
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=USER_AGENT)
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
                    # Check if post is from today
                    if not is_facebook_post_from_today(article, self.logger):
                        self.logger.debug(f"Post {i} is not from today, skipping")
                        continue

                    text_content = article.inner_text().lower()

                    # Check if this post mentions flavor or custard
                    if any(keyword in text_content for keyword in ["flavor", "custard", "today"]):
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
                try:
                    browser.close()
                except Exception:
                    pass

    def _extract_flavor_name(self, text):
        """
        Extract the flavor name and description from a Facebook post.

        Args:
            text: Full text of the Facebook post

        Returns:
            tuple: (flavor_name, description) or (None, None) if not found
        """
        self.logger.debug(f"Extracting flavor from text: {text[:200]}")

        # Try various patterns to extract the flavor
        patterns = [
            # "FLAVOR NAME is our flavor of the day" - flavor comes BEFORE
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
                full_text = match.group(1).strip()
                # Clean up
                full_text = re.sub(
                    r"\s*[\U0001F300-\U0001F9FF]+.*$", "", full_text
                )  # Remove emojis and after
                full_text = full_text.split("!")[0].strip()
                full_text = full_text.split("  ")[0].strip()  # Remove double space and after

                # Extract flavor and description (separated by dash)
                description = None
                if " - " in full_text:
                    parts = full_text.split(" - ", 1)
                    flavor = parts[0].strip()
                    description = parts[1].strip() if len(parts) > 1 else None
                else:
                    flavor = full_text

                # Sanity check: make sure it's a reasonable flavor name
                if 3 < len(flavor) < 100 and not flavor.lower().startswith("of the"):
                    self.logger.debug(f"Extracted flavor: {flavor}, description: {description}")
                    return (flavor, description)

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
                            extracted = next_line.split("!")[0].split(".")[0].strip()
                            self.logger.debug(f"Extracted flavor from next line: {extracted}")
                            return (extracted, None)

                # Try to extract from the same line
                cleaned = re.sub(
                    r".*?flavor(?:\s+of\s+the\s+day)?[\s:]*", "", line, flags=re.IGNORECASE
                )
                cleaned = cleaned.strip(" :,-!.")
                if cleaned and 3 < len(cleaned) < 100 and not cleaned.lower().startswith("is"):
                    extracted = cleaned.split("!")[0].split(".")[0].strip()
                    self.logger.debug(f"Extracted flavor from same line: {extracted}")
                    return (extracted, None)

        self.logger.warning("Could not extract flavor name using any method")
        return (None, None)


def scrape_bigdeal():
    """
    Standalone function to scrape Big Deal Burgers.

    Returns:
        list: List of flavor dicts
    """
    scraper = BigDealScraper()
    return scraper.scrape()
