"""Scraper for Leon's Frozen Custard using Playwright to scrape Facebook."""

import html
import re
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.scrapers.scraper_base import USER_AGENT, BaseScraper
from app.scrapers.utils import is_facebook_post_from_today


class LeonsScraper(BaseScraper):
    """Scraper for Leon's Frozen Custard Facebook page."""

    # Facebook page timeouts - configured for slow-loading pages with anti-bot measures
    NAVIGATION_TIMEOUT = 60000  # 60 seconds for page navigation
    SELECTOR_TIMEOUT = 30000  # 30 seconds for selector wait
    MAX_RETRIES = 3  # Number of retry attempts for transient Playwright errors (including timeouts)
    RETRY_BASE_DELAY = (
        2  # Base delay multiplied by 2^attempt (produces 2s, 4s delays for 3 total attempts)
    )

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
        Use Playwright to scrape Leon's Facebook page with retry logic.

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

                # Get all post articles first
                all_articles = page.query_selector_all('[role="article"]')
                self.logger.debug(f"Found {len(all_articles)} total articles (including comments)")

                # Filter out nested articles (comments) - only keep top-level posts
                # Comments are article elements nested within post article elements
                top_level_articles = []
                for article in all_articles:
                    # Check if this article is nested within another article
                    # by looking for a parent with role="article"
                    try:
                        parent_article = article.evaluate(
                            """(element) => {
                                let parent = element.parentElement;
                                while (parent) {
                                    if (parent.getAttribute('role') === 'article' && parent !== element) {
                                        return true;
                                    }
                                    parent = parent.parentElement;
                                }
                                return false;
                            }"""
                        )
                        if not parent_article:
                            top_level_articles.append(article)
                    except Exception:
                        # If evaluation fails, include the article to be safe
                        top_level_articles.append(article)

                self.logger.debug(
                    f"Filtered to {len(top_level_articles)} top-level posts (excluding comments)"
                )

                # Now expand "See more" links ONLY in top-level posts to reveal full content
                expanded_count = 0
                for idx, article in enumerate(top_level_articles[:10]):  # Process first 10 posts
                    try:
                        # Look for "See more" button within this specific article
                        # Try multiple selectors as Facebook structure can vary
                        see_more = None
                        selectors = [
                            'div[role="button"]:has-text("See more")',
                            '[role="button"]:has-text("See more")',
                            'text="See more"',
                        ]

                        for selector in selectors:
                            try:
                                see_more = article.query_selector(selector)
                                if see_more:
                                    break
                            except Exception:
                                continue

                        if see_more and see_more.is_visible():
                            self.logger.debug(f"Expanding 'See more' in post {idx}")
                            see_more.click()
                            page.wait_for_timeout(500)  # Wait for expansion
                            expanded_count += 1
                        else:
                            self.logger.debug(f"No 'See more' button found in post {idx}")
                    except Exception as e:
                        self.logger.debug(f"Could not expand 'See more' in article {idx}: {e}")
                        pass  # Continue if expansion fails

                self.logger.debug(
                    f"Expanded {expanded_count} 'See more' buttons in top-level posts"
                )

                # Wait a bit longer after all expansions to let content fully render
                if expanded_count > 0:
                    page.wait_for_timeout(1000)

                # Look through recent posts for flavor information
                for i, article in enumerate(top_level_articles[:10]):  # Check first 10 posts
                    # Fetch inner text once for both date validation and content processing
                    try:
                        text_content = article.inner_text()
                        if not text_content or text_content.strip() == "":
                            self.logger.debug(f"Post {i}: Empty content, skipping")
                            continue
                    except Exception as e:
                        self.logger.debug(f"Post {i}: Error getting text content: {e}")
                        continue

                    # Check if post is from today using pre-fetched text
                    if not is_facebook_post_from_today(
                        article, self.logger, article_text=text_content
                    ):
                        self.logger.debug(f"Post {i} is not from today, skipping")
                        continue

                    text_lower = text_content.lower()

                    # Log a preview of the post content
                    preview = text_content[:100].replace("\n", " ")
                    self.logger.debug(f"Post {i}: {preview}...")

                    # For debugging, log if the text seems unusually short
                    if len(text_content) < 20:
                        self.logger.debug(
                            f"Post {i}: Unusually short content (length={len(text_content)}): {repr(text_content)}"
                        )

                    # Check if this post mentions flavor and is specifically about today/of the day
                    if "flavor" in text_lower and any(
                        keyword in text_lower for keyword in ["today", "daily", "of the day"]
                    ):
                        # Additional check: make sure it's announcing a flavor, not just mentioning it
                        # Look for patterns like "is our flavor", "is the flavor", "flavor of the day:"
                        if any(
                            pattern in text_lower
                            for pattern in [
                                "is our flavor",
                                "is the flavor",
                                "flavor of the day:",
                                "flavor today:",
                                "today's flavor",
                                "daily flavor",
                            ]
                        ):
                            self.logger.debug(f"Found flavor post at index {i}")
                            return text_content
                        else:
                            self.logger.debug(
                                f"Post {i} has 'flavor' but doesn't appear to be announcing one"
                            )

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
        - Decodes HTML entities (e.g., &amp; → &)
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
                flavor = self._sanitize_flavor_name(flavor)

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
                            next_line = self._sanitize_flavor_name(next_line)
                            self.logger.debug(f"Extracted flavor from next line: {next_line}")
                            return next_line

                # Try to extract from the same line
                cleaned = re.sub(
                    r".*?flavor(?:\s+of\s+the\s+day)?[\s:]*", "", line, flags=re.IGNORECASE
                )
                cleaned = self._sanitize_flavor_name(cleaned)
                if cleaned and 3 < len(cleaned) < 100 and not cleaned.lower().startswith("is"):
                    self.logger.debug(f"Extracted flavor from same line: {cleaned}")
                    return cleaned

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
