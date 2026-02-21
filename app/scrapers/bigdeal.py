"""Scraper for Big Deal Burgers using Playwright to scrape Facebook."""

import html
import re
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.scrapers.scraper_base import USER_AGENT, BaseScraper
from app.scrapers.utils import is_facebook_post_from_today


class BigDealScraper(BaseScraper):
    """Scraper for Big Deal Burgers Facebook page."""

    # Facebook page timeouts - configured for slow-loading pages with anti-bot measures
    NAVIGATION_TIMEOUT = 60000  # 60 seconds for page navigation
    SELECTOR_TIMEOUT = 30000  # 30 seconds for selector wait
    MAX_RETRIES = 3  # Number of retry attempts for transient Playwright errors (including timeouts)
    RETRY_BASE_DELAY = (
        2  # Base delay multiplied by 2^attempt (produces 2s, 4s delays for 3 total attempts)
    )

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
        Use Playwright to scrape Big Deal Burgers Facebook page with retry logic.

        Args:
            url: Facebook page URL

        Returns:
            str: Text content of the most recent flavor post, or None if not found
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                return self._scrape_facebook_page_attempt(url, attempt)
            except PlaywrightTimeoutError as e:
                # Timeout errors are transient and should be retried
                if not self._handle_retry(attempt, f"Timeout: {e}"):
                    return None
            except PlaywrightError as e:
                # Other Playwright errors (network, page crash, etc.) may be transient
                if not self._handle_retry(attempt, f"Playwright error: {e}"):
                    return None
            except Exception as e:
                # Unexpected errors should not be retried
                self.logger.error(f"Unexpected error on attempt {attempt + 1}: {e}", exc_info=True)
                return None
        return None

    def _handle_retry(self, attempt, error_message):
        """
        Handle retry logic with exponential backoff.

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

    def _scrape_facebook_page_attempt(self, url, attempt):
        """
        Single attempt to scrape Facebook page.

        Args:
            url: Facebook page URL
            attempt: Current attempt number (0-indexed)

        Returns:
            str: Text content of the most recent flavor post, or None if not found

        Raises:
            PlaywrightTimeoutError: If page load or selector wait times out
            Exception: For other errors
        """
        with sync_playwright() as p:
            browser = None
            try:
                # Launch browser in headless mode
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=USER_AGENT)
                page = context.new_page()

                # Navigate to Facebook page with extended timeout
                self.logger.debug(
                    f"Loading Facebook page (attempt {attempt + 1}): {url} "
                    f"(timeout: {self.NAVIGATION_TIMEOUT}ms)"
                )
                page.goto(url, wait_until="networkidle", timeout=self.NAVIGATION_TIMEOUT)

                # Wait for posts to load with extended timeout
                self.logger.debug(f"Waiting for posts to load (timeout: {self.SELECTOR_TIMEOUT}ms)")
                page.wait_for_selector('[role="article"]', timeout=self.SELECTOR_TIMEOUT)

                # Scroll down to load more posts
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                    page.wait_for_timeout(1000)  # Let posts load
                except Exception:
                    pass

                # Expand "See more" links to reveal full post content
                try:
                    see_more_buttons = page.query_selector_all('text="See more"')
                    self.logger.debug(f"Found {len(see_more_buttons)} 'See more' buttons to expand")
                    for btn in see_more_buttons[:10]:  # Expand up to 10 posts
                        try:
                            if btn.is_visible():
                                btn.click()
                                page.wait_for_timeout(500)  # Wait for expansion
                        except Exception:
                            pass  # Continue if a button fails to click
                except Exception as e:
                    self.logger.debug(f"Could not expand 'See more' buttons: {e}")

                # Get all post articles (after expansion)
                articles = page.query_selector_all('[role="article"]')

                # Filter out nested articles (comments) so we only process top-level posts.
                # Facebook uses role="article" for both posts and comments. This logic mirrors
                # the approach used in the Leon's scraper to avoid treating comments as posts.
                top_level_articles = []
                for article in articles:
                    try:
                        # In the page context, check if this node has an ancestor with role="article"
                        # that is not itself. If it does, it's a nested article (e.g., a comment).
                        has_parent_article = article.evaluate(
                            """(node) => {
                                if (!node || !node.parentElement) {
                                    return false;
                                }
                                const parentArticle = node.parentElement.closest('[role="article"]');
                                return parentArticle !== null && parentArticle !== node;
                            }"""
                        )
                        if not has_parent_article:
                            top_level_articles.append(article)
                    except Exception:
                        # If anything goes wrong during evaluation, fall back to keeping the article
                        top_level_articles.append(article)

                self.logger.debug(
                    f"Found {len(articles)} total articles, {len(top_level_articles)} top-level posts on Facebook page"
                )

                # Look through recent posts for flavor information
                for i, article in enumerate(top_level_articles[:10]):  # Check first 10 posts
                    # Check if post is from today
                    if not is_facebook_post_from_today(article, self.logger):
                        self.logger.debug(f"Post {i} is not from today, skipping")
                        continue

                    # Fetch inner text once to avoid duplicate cross-browser calls.
                    # This is wrapped in try/except to avoid crashing on malformed posts.
                    try:
                        text_content = article.inner_text()
                    except PlaywrightError as e:
                        self.logger.debug(f"Failed to extract text from post {i}: {e}")
                        continue
                    except Exception as e:
                        # Catch any unexpected errors from Playwright DOM interaction.
                        self.logger.debug(f"Unexpected error extracting text from post {i}: {e}")
                        continue

                    if not text_content or not text_content.strip():
                        self.logger.debug(f"Post {i} has no text content, skipping")
                        continue
                    text_lower = text_content.lower()

                    # Use a more precise heuristic to detect flavor announcements.
                    # We require a flavor-related word and either a time-related word
                    # or an explicit announcement pattern. This mirrors the stricter
                    # approach used in other scrapers (e.g., Leon's) to avoid
                    # matching generic posts that just mention "today" or "custard".
                    has_flavor_word = "flavor" in text_lower or "custard" in text_lower
                    time_keywords = ["today", "daily", "of the day", "tonight"]
                    has_time_word = any(keyword in text_lower for keyword in time_keywords)

                    announcement_patterns = [
                        r"flavor of the day",
                        r"today['’]s flavor",
                        r"is our flavor",
                        r"our flavor(?: of the day)? is",
                        r"flavor:?[\s-]+",  # e.g., "Flavor of the day: ..."
                        r"custard flavor",
                    ]
                    has_announcement_pattern = any(
                        re.search(pattern, text_lower, re.IGNORECASE) for pattern in announcement_patterns
                    )

                    if has_flavor_word and (has_time_word or has_announcement_pattern):
                        self.logger.debug(f"Found flavor post at index {i}")
                        return text_content

                self.logger.warning("No recent flavor post found in first 10 posts")
                return None

            finally:
                if browser:
                    try:
                        browser.close()
                    except Exception:
                        pass

    def _sanitize_flavor_name(self, flavor):
        """
        Sanitize a flavor name by decoding HTML entities, removing emojis, and cleaning punctuation.

        This method:
        - Strips leading/trailing whitespace and common leading punctuation (:,-)
        - Decodes HTML entities (e.g., &amp; → &, &#39; → ')
        - Removes emojis and truncates everything after the first emoji
        - Truncates content after common terminators (!, ., double-space)

        Args:
            flavor: Raw flavor name extracted from text

        Returns:
            str: Sanitized flavor name
        """
        # Strip leading/trailing whitespace and common leading punctuation
        flavor = flavor.strip().lstrip(":,-")
        # Decode HTML entities
        flavor = html.unescape(flavor)
        # Remove emojis and everything after them
        # Covers: Emoticons, Transport/Map, Misc Symbols, Pictographs, Dingbats
        flavor = re.sub(
            r"\s*[\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F300-\U0001F5FF"
            r"\U0001F900-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]+.*$",
            "",
            flavor,
        )
        # Remove content after common terminators (for non-emoji cases)
        # Split on '!', double space, or '.' and take first part
        flavor = re.split(r"[!.]|  ", flavor)[0].strip()
        return flavor

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
                full_text = self._sanitize_flavor_name(match.group(1))

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
                            extracted = self._sanitize_flavor_name(next_line)
                            self.logger.debug(f"Extracted flavor from next line: {extracted}")
                            return (extracted, None)

                # Try to extract from the same line
                cleaned = re.sub(
                    r".*?flavor(?:\s+of\s+the\s+day)?[\s:]*", "", line, flags=re.IGNORECASE
                )
                cleaned = cleaned.strip(" :,-!.")
                if cleaned and 3 < len(cleaned) < 100 and not cleaned.lower().startswith("is"):
                    extracted = self._sanitize_flavor_name(cleaned)
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
