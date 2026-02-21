"""Unit tests for Big Deal Burgers scraper functionality."""

import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.scrapers.bigdeal import BigDealScraper


class TestBigDealFlavorExtraction(unittest.TestCase):
    """Test the flavor extraction logic with various post formats."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch locations to provide a test location
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "test-bigdeal",
                "name": "Big Deal Burgers",
                "url": "http://test",
                "facebook": "https://www.facebook.com/test",
                "enabled": True,
                "lat": 43.0,
                "lng": -88.0,
                "address": "123 Test St",
            }
        ]
        self.scraper = BigDealScraper()

    def tearDown(self):
        """Clean up patches."""
        self.locations_patcher.stop()

    def test_extract_flavor_pattern1_all_caps_before(self):
        """Test: 'ORANGE DREAM is our flavor of the day' - flavor before."""
        text = "ORANGE DREAM is our flavor of the day!"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "ORANGE DREAM")
        self.assertIsNone(description)

    def test_extract_flavor_pattern1_mixed_case(self):
        """Test: 'Mint Oreo is the flavor' - flavor before with mixed case."""
        text = "Mint Oreo is the flavor of the day"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Mint Oreo")
        self.assertIsNone(description)

    def test_extract_flavor_pattern2_with_colon(self):
        """Test: 'Flavor of the Day: Chocolate' - flavor after with colon."""
        text = "Flavor of the Day: Chocolate Peanut Butter"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Chocolate Peanut Butter")
        self.assertIsNone(description)

    def test_extract_flavor_pattern2_simple(self):
        """Test: 'Flavor: Vanilla' - simple flavor after."""
        text = "Flavor: Vanilla Bean"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Vanilla Bean")
        self.assertIsNone(description)

    def test_extract_flavor_pattern3_todays_flavor(self):
        """Test: \"Today's flavor: Strawberry\" - using today's."""
        text = "Today's flavor: Strawberry Cheesecake"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Strawberry Cheesecake")
        self.assertIsNone(description)

    def test_extract_flavor_todays_flavor_is(self):
        """Test: \"Today's flavor is Orange Dream\" - realistic format with description."""
        text = "Today's flavor is Orange Dream - orange and vanilla custard swirled together."
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Orange Dream")
        self.assertEqual(description, "orange and vanilla custard swirled together")

    def test_extract_flavor_with_description_after_dash(self):
        """Test: Flavor with description after dash is captured."""
        text = "Today's flavor is Butter Pecan - creamy custard with pecans and caramel."
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Butter Pecan")
        self.assertEqual(description, "creamy custard with pecans and caramel")

    def test_extract_flavor_pattern4_today_colon(self):
        """Test: 'Today: Mint' - today with colon."""
        text = "Today: Mint Chocolate Chip"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Mint Chocolate Chip")
        self.assertIsNone(description)

    def test_extract_flavor_with_emoji_removal(self):
        """Test: Emoji removal from flavor name."""
        text = "Flavor of the Day: Cookie Dough 🍪 Hope you enjoy!"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Cookie Dough")
        self.assertIsNone(description)

    def test_extract_flavor_next_line_with_emoji(self):
        """Test: Fallback next-line extraction with emoji removal."""
        text = """what flavor do we have?
Chocolate Chip
Come visit us!"""
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Chocolate Chip")
        self.assertIsNone(description)

    def test_extract_flavor_with_exclamation_mark(self):
        """Test: Exclamation mark handling."""
        text = "Flavor of the Day: Pumpkin Pie! Come get it today"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Pumpkin Pie")
        self.assertIsNone(description)

    def test_extract_flavor_with_double_space(self):
        """Test: Double space handling."""
        text = "Flavor of the Day: Lemon Berry  Available until 9pm"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Lemon Berry")
        self.assertIsNone(description)

    def test_extract_flavor_multiline_next_line(self):
        """Test: Fallback - flavor on next line."""
        text = """Today's Flavor
Raspberry Truffle
Come visit us!"""
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Raspberry Truffle")
        self.assertIsNone(description)

    def test_extract_flavor_multiline_same_line_cleanup(self):
        """Test: Fallback - flavor on same line after cleanup."""
        text = "Flavor of the day is Cherry Vanilla!"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Cherry Vanilla")
        self.assertIsNone(description)

    def test_extract_flavor_complex_post(self):
        """Test: Complex post with multiple sentences."""
        text = """Good morning everyone! 🌞

SALTED CARAMEL is our flavor of the day today!

Stop by and try it while supplies last. Open until 10pm.
        """
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "SALTED CARAMEL")
        self.assertIsNone(description)

    def test_extract_flavor_realistic_bigdeal_post(self):
        """Test: Realistic Big Deal Burgers post format with description."""
        text = """Big Deal Burgers & Custard
1d

·
Today's flavor is Orange Dream - orange and vanilla custard swirled together.
All reactions:
26
2
6
Like
Comment"""
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Orange Dream")
        self.assertEqual(description, "orange and vanilla custard swirled together")

    def test_extract_flavor_too_short_rejected(self):
        """Test: Too short flavor names are rejected."""
        text = "Flavor: Hi"  # Only 2 characters
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertIsNone(flavor)
        self.assertIsNone(description)

    def test_extract_flavor_too_long_rejected(self):
        """Test: Unreasonably long flavor names are rejected."""
        text = "Flavor: " + "A" * 150  # 150 characters
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertIsNone(flavor)
        self.assertIsNone(description)

    def test_extract_flavor_no_match(self):
        """Test: No flavor found returns None."""
        text = "Welcome to our page! Check back later for updates."
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertIsNone(flavor)
        self.assertIsNone(description)

    def test_extract_flavor_with_ampersand(self):
        """Test: Flavor with ampersand."""
        text = "Today's flavor: Cookies & Cream"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Cookies & Cream")
        self.assertIsNone(description)

    def test_extract_flavor_html_entity_ampersand(self):
        """Test: HTML-encoded ampersand (&amp;) is decoded to &."""
        text = "Today's flavor: Cookies &amp; Cream"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Cookies & Cream")
        self.assertIsNone(description)

    def test_extract_flavor_html_entity_apostrophe(self):
        """Test: HTML-encoded apostrophe (&#39;) is decoded."""
        text = "Flavor of the Day: S&#39;mores Delight"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "S'mores Delight")
        self.assertIsNone(description)

    def test_extract_flavor_html_entity_quote(self):
        """Test: HTML-encoded double quote (&quot;) is decoded."""
        text = "Flavor of the Day: Grandma&quot;s Peach"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, 'Grandma"s Peach')
        self.assertIsNone(description)

    def test_sanitize_flavor_name_html_entities(self):
        """Test: _sanitize_flavor_name decodes HTML entities."""
        self.assertEqual(
            self.scraper._sanitize_flavor_name("Cookies &amp; Cream"), "Cookies & Cream"
        )
        self.assertEqual(self.scraper._sanitize_flavor_name("S&#39;mores"), "S'mores")

    def test_sanitize_flavor_name_removes_emojis(self):
        """Test: _sanitize_flavor_name strips emojis and trailing content."""
        self.assertEqual(self.scraper._sanitize_flavor_name("Cookie Dough 🍪 yum"), "Cookie Dough")

    def test_sanitize_flavor_name_strips_punctuation(self):
        """Test: _sanitize_flavor_name strips leading punctuation."""
        self.assertEqual(self.scraper._sanitize_flavor_name(": Vanilla Bean"), "Vanilla Bean")

    def test_extract_flavor_newline_termination(self):
        """Test: Flavor extraction stops at newline."""
        text = "Flavor of the Day: Turtle Sundae\nCome try it today!"
        flavor, description = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Turtle Sundae")
        self.assertIsNone(description)

    def test_extract_flavor_with_custard_keyword(self):
        """Test: Post with custard keyword."""
        text = "Today we have Vanilla custard available!"
        flavor, description = self.scraper._extract_flavor_name(text)
        # This should be picked up by fallback extraction
        self.assertIsNotNone(flavor)


class TestBigDealFacebookScraping(unittest.TestCase):
    """Test the Facebook scraping functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "test-bigdeal",
                "name": "Big Deal Burgers",
                "url": "http://test",
                "facebook": "https://www.facebook.com/test",
                "enabled": True,
                "lat": 43.0,
                "lng": -88.0,
                "address": "123 Test St",
            }
        ]
        self.scraper = BigDealScraper()

    def tearDown(self):
        """Clean up patches."""
        self.locations_patcher.stop()

    def _create_mock_article(self, text_content, is_nested=False):
        """
        Create a properly mocked article with all required methods.

        Args:
            text_content: The text content to return from inner_text()
            is_nested: Whether this article is nested within another (i.e., a comment)

        Returns:
            Mock article object
        """
        mock_article = Mock()
        mock_article.inner_text.return_value = text_content
        # Mock evaluate() to return whether article is nested (False = top-level post)
        mock_article.evaluate.return_value = is_nested
        # Mock query_selector() to return None (no "See more" button)
        mock_article.query_selector.return_value = None
        # Mock is_visible() in case it's checked
        mock_article.is_visible.return_value = True
        return mock_article

    @patch("app.scrapers.bigdeal.is_facebook_post_from_today")
    @patch("app.scrapers.bigdeal.sync_playwright")
    def test_scrape_facebook_success_first_post(self, mock_playwright, mock_is_today):
        """Test: Successfully scrape flavor from first post."""
        # Mock date validation to return True (post is from today)
        mock_is_today.return_value = True

        # Setup mocks
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()
        mock_article = Mock()

        # Setup article with flavor content
        mock_article.inner_text.return_value = "Today's flavor is Vanilla Bean!"
        # Simulate top-level post (not nested in another article/comment)
        mock_article.evaluate.return_value = False

        # Setup page to return one article
        mock_page.query_selector_all.return_value = [mock_article]

        # Setup browser chain
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        # Execute
        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        # Verify
        self.assertEqual(result, "Today's flavor is Vanilla Bean!")
        mock_page.goto.assert_called_once()
        mock_page.wait_for_selector.assert_called_once_with('[role="article"]', timeout=30000)

    @patch("app.scrapers.bigdeal.is_facebook_post_from_today")
    @patch("app.scrapers.bigdeal.sync_playwright")
    def test_scrape_facebook_success_third_post(self, mock_playwright, mock_is_today):
        """Test: Find flavor in third post (skips first two)."""
        # Mock date validation to return True (post is from today)
        mock_is_today.return_value = True

        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        # Create 3 articles - first two without flavor keywords
        mock_article1 = Mock()
        mock_article1.inner_text.return_value = "Happy Monday everyone! Visit us soon."
        mock_article1.evaluate.return_value = False

        mock_article2 = Mock()
        mock_article2.inner_text.return_value = "Check out our new hours!"
        mock_article2.evaluate.return_value = False

        mock_article3 = Mock()
        mock_article3.inner_text.return_value = "Today's custard flavor: CHOCOLATE CHIP!"
        mock_article3.evaluate.return_value = False

        mock_page.query_selector_all.return_value = [mock_article1, mock_article2, mock_article3]

        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertEqual(result, "Today's custard flavor: CHOCOLATE CHIP!")

    @patch("app.scrapers.bigdeal.sync_playwright")
    def test_scrape_facebook_no_posts(self, mock_playwright):
        """Test: No posts found on page."""
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        # No articles found
        mock_page.query_selector_all.return_value = []

        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertIsNone(result)

    @patch("app.scrapers.bigdeal.is_facebook_post_from_today")
    @patch("app.scrapers.bigdeal.sync_playwright")
    def test_scrape_facebook_no_flavor_post(self, mock_playwright, mock_is_today):
        """Test: Posts found but none contain flavor information."""
        # Mock date validation to return True (post is from today)
        mock_is_today.return_value = True

        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        # Create articles without flavor content
        articles = []
        for i in range(5):
            mock_article = Mock()
            mock_article.inner_text.return_value = f"General post {i} about our restaurant."
            # Simulate top-level post (not nested in another article/comment)
            mock_article.evaluate.return_value = False
            articles.append(mock_article)

        mock_page.query_selector_all.return_value = articles

        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertIsNone(result)

    @patch("app.scrapers.bigdeal.time.sleep")
    @patch.object(BigDealScraper, "_scrape_facebook_page_attempt")
    def test_scrape_facebook_timeout_error(self, mock_attempt, mock_sleep):
        """Test: Playwright timeout error handling with retries."""
        # All attempts time out
        mock_attempt.side_effect = PlaywrightTimeoutError("Timeout")

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertIsNone(result)
        # Should retry MAX_RETRIES times
        self.assertEqual(mock_attempt.call_count, 3)
        # Should sleep twice (before 2nd and 3rd attempts)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch.object(BigDealScraper, "_scrape_facebook_page_attempt")
    def test_scrape_facebook_general_error(self, mock_attempt):
        """Test: General error handling (no retry on unexpected errors)."""
        # Simulate general error - should not retry
        mock_attempt.side_effect = Exception("Network error")

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertIsNone(result)
        # Should only attempt once (no retries for unexpected errors)
        self.assertEqual(mock_attempt.call_count, 1)

    @patch("app.scrapers.bigdeal.is_facebook_post_from_today")
    @patch("app.scrapers.bigdeal.sync_playwright")
    def test_scrape_facebook_skips_old_posts(self, mock_playwright, mock_is_today):
        """Test: Old posts (not from today) are skipped."""
        # First two posts are old (return False), third is today (return True)
        mock_is_today.side_effect = [False, False, True]

        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        # Create 3 articles
        mock_article1 = Mock()
        mock_article1.inner_text.return_value = "Yesterday's flavor was Chocolate"
        mock_article1.evaluate.return_value = False

        mock_article2 = Mock()
        mock_article2.inner_text.return_value = "Old post about custard"
        mock_article2.evaluate.return_value = False

        mock_article3 = Mock()
        mock_article3.inner_text.return_value = "Today's flavor is Vanilla!"
        mock_article3.evaluate.return_value = False

        mock_page.query_selector_all.return_value = [mock_article1, mock_article2, mock_article3]

        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        # Should skip first two and find third
        self.assertEqual(result, "Today's flavor is Vanilla!")
        # Verify date check was called 3 times
        self.assertEqual(mock_is_today.call_count, 3)

    @patch("app.scrapers.bigdeal.is_facebook_post_from_today")
    @patch("app.scrapers.bigdeal.sync_playwright")
    def test_scrape_facebook_scrolls_before_querying(self, mock_playwright, mock_is_today):
        """Test: Page is scrolled before querying for articles."""
        mock_is_today.return_value = True

        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()
        mock_article = Mock()
        mock_article.inner_text.return_value = "Today's flavor is Vanilla Bean!"
        # Simulate top-level post (not nested in another article/comment)
        mock_article.evaluate.return_value = False

        mock_page.query_selector_all.return_value = [mock_article]
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        self.scraper._scrape_facebook_page("https://facebook.com/test")

        # Verify page was scrolled down before articles were queried
        mock_page.evaluate.assert_called_once_with(
            "window.scrollTo(0, document.body.scrollHeight / 2)"
        )

    @patch("app.scrapers.bigdeal.is_facebook_post_from_today")
    @patch("app.scrapers.bigdeal.sync_playwright")
    def test_scrape_facebook_page_expands_see_more_buttons(self, mock_playwright, mock_is_today):
        """Test: 'See more' buttons are expanded per-article (not page-wide)."""
        mock_is_today.return_value = True

        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        # Setup a visible "See more" button
        mock_see_more_btn = Mock()
        mock_see_more_btn.is_visible.return_value = True

        mock_article = Mock()
        mock_article.inner_text.return_value = "Today's flavor is Vanilla Bean!"
        # Simulate top-level post (not nested in another article/comment)
        mock_article.evaluate.return_value = False

        mock_page.query_selector_all.return_value = [mock_article]
        # Article returns a "See more" button when queried with per-article selector
        mock_article.query_selector.return_value = mock_see_more_btn

        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        # Verify "See more" button was clicked per-article to expand truncated content
        mock_see_more_btn.click.assert_called_once()
        self.assertEqual(result, "Today's flavor is Vanilla Bean!")

    @patch("app.scrapers.bigdeal.is_facebook_post_from_today")
    @patch("app.scrapers.bigdeal.sync_playwright")
    def test_scrape_facebook_browser_close_error(self, mock_playwright, mock_is_today):
        """Test: Browser close fails gracefully."""
        # Mock date validation to return True (post is from today)
        mock_is_today.return_value = True

        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        mock_article = Mock()
        mock_article.inner_text.return_value = "Today's flavor: Strawberry"
        # Simulate top-level post (not nested in another article/comment)
        mock_article.evaluate.return_value = False

        mock_page.query_selector_all.return_value = [mock_article]
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_browser.close.side_effect = Exception("Close failed")

        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        # Should not raise exception even if browser close fails
        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertEqual(result, "Today's flavor: Strawberry")

    @patch("app.scrapers.bigdeal.is_facebook_post_from_today")
    @patch("app.scrapers.bigdeal.sync_playwright")
    def test_scrape_facebook_inner_text_error_continues_to_next_post(
        self, mock_playwright, mock_is_today
    ):
        """Test: inner_text() error (e.g. detached element) skips post and continues."""
        mock_is_today.return_value = True

        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        # First article raises PlaywrightError (detached/stale element)
        mock_article1 = Mock()
        mock_article1.inner_text.side_effect = PlaywrightError("Element is detached from DOM")
        mock_article1.evaluate.return_value = False

        # Second article has valid flavor content
        mock_article2 = Mock()
        mock_article2.inner_text.return_value = "Today's flavor is Vanilla!"
        mock_article2.evaluate.return_value = False

        mock_page.query_selector_all.return_value = [mock_article1, mock_article2]
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        # Should skip the bad element and return flavor from second article
        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertEqual(result, "Today's flavor is Vanilla!")


class TestBigDealRetryLogic(unittest.TestCase):
    """Test the retry logic and error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "test-bigdeal",
                "name": "Big Deal Burgers",
                "facebook": "https://www.facebook.com/test",
                "enabled": True,
            }
        ]
        self.scraper = BigDealScraper()

    def tearDown(self):
        """Clean up patches."""
        self.locations_patcher.stop()

    @patch("app.scrapers.bigdeal.time.sleep")
    @patch.object(BigDealScraper, "_scrape_facebook_page_attempt")
    def test_retry_on_timeout_error_succeeds_second_attempt(self, mock_attempt, mock_sleep):
        """Test: Retry on TimeoutError, succeeds on second attempt."""
        # First attempt times out, second succeeds
        mock_attempt.side_effect = [
            PlaywrightTimeoutError("Timeout waiting for selector"),
            "Flavor: Vanilla",
        ]

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertEqual(result, "Flavor: Vanilla")
        self.assertEqual(mock_attempt.call_count, 2)
        mock_sleep.assert_called_once_with(2)  # 2^0 * 2 = 2 seconds

    @patch("app.scrapers.bigdeal.time.sleep")
    @patch.object(BigDealScraper, "_scrape_facebook_page_attempt")
    def test_retry_on_timeout_error_max_retries_reached(self, mock_attempt, mock_sleep):
        """Test: Max retries reached after multiple timeouts."""
        # All attempts time out
        mock_attempt.side_effect = PlaywrightTimeoutError("Timeout")

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertIsNone(result)
        self.assertEqual(mock_attempt.call_count, 3)  # MAX_RETRIES
        self.assertEqual(mock_sleep.call_count, 2)  # Delays before 2nd and 3rd attempts
        # Check exponential backoff: 2, 4 seconds
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)

    @patch("app.scrapers.bigdeal.time.sleep")
    @patch.object(BigDealScraper, "_scrape_facebook_page_attempt")
    def test_retry_on_playwright_error(self, mock_attempt, mock_sleep):
        """Test: Retry on PlaywrightError."""
        # First attempt has Playwright error, second succeeds
        mock_attempt.side_effect = [
            PlaywrightError("Browser disconnected"),
            "Flavor: Chocolate",
        ]

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertEqual(result, "Flavor: Chocolate")
        self.assertEqual(mock_attempt.call_count, 2)
        mock_sleep.assert_called_once_with(2)

    @patch.object(BigDealScraper, "_scrape_facebook_page_attempt")
    def test_no_retry_on_unexpected_error(self, mock_attempt):
        """Test: No retry on unexpected non-Playwright errors."""
        # Unexpected error should not retry
        mock_attempt.side_effect = ValueError("Invalid value")

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertIsNone(result)
        self.assertEqual(mock_attempt.call_count, 1)  # No retries

    @patch("app.scrapers.bigdeal.time.sleep")
    @patch.object(BigDealScraper, "_scrape_facebook_page_attempt")
    def test_exponential_backoff_delay(self, mock_attempt, mock_sleep):
        """Test: Exponential backoff delay calculation."""
        # All attempts fail
        mock_attempt.side_effect = PlaywrightTimeoutError("Timeout")

        self.scraper._scrape_facebook_page("https://facebook.com/test")

        # Verify delays: 2s (2^0 * 2), 4s (2^1 * 2)
        calls = mock_sleep.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0][0], 2)  # First delay: 2 seconds
        self.assertEqual(calls[1][0][0], 4)  # Second delay: 4 seconds


class TestBigDealHandleRetry(unittest.TestCase):
    """Test the _handle_retry helper method."""

    def setUp(self):
        """Set up test fixtures."""
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "test-bigdeal",
                "name": "Big Deal Burgers",
                "facebook": "https://www.facebook.com/test",
                "enabled": True,
            }
        ]
        self.scraper = BigDealScraper()

    def tearDown(self):
        """Clean up patches."""
        self.locations_patcher.stop()

    @patch("app.scrapers.bigdeal.time.sleep")
    def test_handle_retry_first_attempt(self, mock_sleep):
        """Test: First attempt returns True and sleeps for 2 seconds."""
        result = self.scraper._handle_retry(0, "Test error")

        self.assertTrue(result)
        mock_sleep.assert_called_once_with(2)

    @patch("app.scrapers.bigdeal.time.sleep")
    def test_handle_retry_second_attempt(self, mock_sleep):
        """Test: Second attempt returns True and sleeps for 4 seconds."""
        result = self.scraper._handle_retry(1, "Test error")

        self.assertTrue(result)
        mock_sleep.assert_called_once_with(4)

    @patch("app.scrapers.bigdeal.time.sleep")
    def test_handle_retry_max_retries(self, mock_sleep):
        """Test: Max retries returns False and does not sleep."""
        result = self.scraper._handle_retry(2, "Test error")  # Attempt 2 = 3rd attempt

        self.assertFalse(result)
        mock_sleep.assert_not_called()


class TestBigDealScraperIntegration(unittest.TestCase):
    """Test the full scraper integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "bigdeal-test",
                "name": "Big Deal Burgers",
                "brand": "Bigdeal",
                "url": "https://bigdealburgers.com/",
                "facebook": "https://www.facebook.com/test",
                "enabled": True,
                "lat": 43.05627,
                "lng": -87.98273,
                "address": "5832 W Vliet St, Milwaukee, WI 53208",
            }
        ]

    def tearDown(self):
        """Clean up patches."""
        self.locations_patcher.stop()

    @patch("app.scrapers.bigdeal.BigDealScraper._scrape_facebook_page")
    @patch("app.scrapers.bigdeal.BigDealScraper._extract_flavor_name")
    def test_scrape_success(self, mock_extract, mock_scrape_fb):
        """Test: Successful full scrape."""
        mock_scrape_fb.return_value = "Today's flavor is Mint Oreo!"
        mock_extract.return_value = ("Mint Oreo", None)

        scraper = BigDealScraper()
        results = scraper.scrape()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "Mint Oreo")
        self.assertEqual(results[0]["location"], "Big Deal Burgers")
        self.assertEqual(results[0]["brand"], "Bigdeal")
        self.assertEqual(results[0]["location_id"], "bigdeal-test")

    @patch("app.scrapers.bigdeal.BigDealScraper._scrape_facebook_page")
    def test_scrape_no_facebook_url(self, mock_scrape_fb):
        """Test: No Facebook URL in location config."""
        # Remove Facebook URL
        self.mock_get_locations.return_value[0]["facebook"] = None

        scraper = BigDealScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])
        mock_scrape_fb.assert_not_called()

    @patch("app.scrapers.bigdeal.BigDealScraper._scrape_facebook_page")
    def test_scrape_no_flavor_text(self, mock_scrape_fb):
        """Test: Facebook scraping returns no text."""
        mock_scrape_fb.return_value = None

        scraper = BigDealScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    @patch("app.scrapers.bigdeal.BigDealScraper._scrape_facebook_page")
    @patch("app.scrapers.bigdeal.BigDealScraper._extract_flavor_name")
    def test_scrape_extraction_fails(self, mock_extract, mock_scrape_fb):
        """Test: Flavor extraction fails."""
        mock_scrape_fb.return_value = "Some post without clear flavor"
        mock_extract.return_value = (None, None)

        scraper = BigDealScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    @patch("app.scrapers.bigdeal.BigDealScraper._scrape_facebook_page")
    def test_scrape_exception_handling(self, mock_scrape_fb):
        """Test: Exception during scraping is handled."""
        mock_scrape_fb.side_effect = Exception("Unexpected error")

        scraper = BigDealScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    def test_scrape_no_locations(self):
        """Test: No locations configured."""
        self.mock_get_locations.return_value = []

        scraper = BigDealScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
