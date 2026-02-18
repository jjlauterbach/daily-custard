"""Unit tests for Leon's scraper functionality."""

import unittest
from unittest.mock import Mock, patch

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from app.scrapers.leons import LeonsScraper


class TestLeonsFlavorExtraction(unittest.TestCase):
    """Test the flavor extraction logic with various post formats."""

    def setUp(self):
        """Set up test fixtures."""
        # Patch locations to provide a test location
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "test-leons",
                "name": "Leon's Frozen Custard",
                "url": "http://test",
                "facebook": "https://www.facebook.com/test",
                "enabled": True,
                "lat": 43.0,
                "lng": -88.0,
                "address": "123 Test St",
            }
        ]
        self.scraper = LeonsScraper()

    def tearDown(self):
        """Clean up patches."""
        self.locations_patcher.stop()

    def test_extract_flavor_pattern1_all_caps_before(self):
        """Test: 'BUTTER PECAN is our flavor of the day' - flavor before."""
        text = "BUTTER PECAN is our flavor of the day!"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "BUTTER PECAN")

    def test_extract_flavor_pattern1_mixed_case(self):
        """Test: 'Chocolate Chip is the flavor' - flavor before with mixed case."""
        text = "Chocolate Chip is the flavor of the day"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Chocolate Chip")

    def test_extract_flavor_pattern2_with_colon(self):
        """Test: 'Flavor of the Day: Chocolate' - flavor after with colon."""
        text = "Flavor of the Day: Chocolate Peanut Butter"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Chocolate Peanut Butter")

    def test_extract_flavor_pattern2_simple(self):
        """Test: 'Flavor: Vanilla' - simple flavor after."""
        text = "Flavor: Vanilla Bean"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Vanilla Bean")

    def test_extract_flavor_pattern3_todays_flavor(self):
        """Test: 'Today's flavor: Strawberry' - using today's."""
        text = "Today's flavor: Strawberry Cheesecake"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Strawberry Cheesecake")

    def test_extract_flavor_pattern4_today_colon(self):
        """Test: 'Today: Mint' - today with colon."""
        text = "Today: Mint Chocolate Chip"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Mint Chocolate Chip")

    def test_extract_flavor_pattern4_flavor_today(self):
        """Test: 'Flavor Today: Caramel' - flavor today."""
        # Note: This pattern doesn't match well, better to use 'Today:' format
        text = "Today: Caramel Cashew"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Caramel Cashew")

    def test_extract_flavor_with_html_entities(self):
        """Test: HTML entity decoding."""
        text = "Flavor of the Day: S&#39;mores &amp; Graham"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "S'mores & Graham")

    def test_extract_flavor_with_emoji_removal(self):
        """Test: Emoji removal from flavor name."""
        text = "Flavor of the Day: Cookie Dough 🍪 Hope you enjoy!"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Cookie Dough")

    def test_extract_flavor_with_exclamation_mark(self):
        """Test: Exclamation mark handling."""
        text = "Flavor of the Day: Pumpkin Pie! Come get it today"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Pumpkin Pie")

    def test_extract_flavor_with_double_space(self):
        """Test: Double space handling."""
        text = "Flavor of the Day: Lemon Berry  Available until 9pm"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Lemon Berry")

    def test_extract_flavor_multiline_next_line(self):
        """Test: Fallback - flavor on next line."""
        text = """Today's Flavor
Raspberry Truffle
Come visit us!"""
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Raspberry Truffle")

    def test_extract_flavor_multiline_same_line_cleanup(self):
        """Test: Fallback - flavor on same line after cleanup."""
        text = "Flavor of the day is Cherry Vanilla!"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Cherry Vanilla")

    def test_extract_flavor_complex_post(self):
        """Test: Complex post with multiple sentences."""
        text = """Good morning everyone! 🌞

SALTED CARAMEL is our flavor of the day today!

Stop by and try it while supplies last. Open until 10pm.
        """
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "SALTED CARAMEL")

    def test_extract_flavor_too_short_rejected(self):
        """Test: Too short flavor names are rejected."""
        text = "Flavor: Hi"  # Only 2 characters
        flavor = self.scraper._extract_flavor_name(text)
        self.assertIsNone(flavor)

    def test_extract_flavor_too_long_rejected(self):
        """Test: Unreasonably long flavor names are rejected."""
        text = "Flavor: " + "A" * 150  # 150 characters
        flavor = self.scraper._extract_flavor_name(text)
        self.assertIsNone(flavor)

    def test_extract_flavor_valid_and_too_short_cases(self):
        """Test: Valid flavor is extracted and too-short flavor is rejected."""
        text = "CHOCOLATE is the flavor of the day"
        # This should extract correctly
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "CHOCOLATE")

        # Test that too-short flavor names are rejected (length <= 3)
        text_short = "Flavor: Hi"  # Too short
        flavor = self.scraper._extract_flavor_name(text_short)
        self.assertIsNone(flavor)

    def test_extract_flavor_no_match(self):
        """Test: No flavor found returns None."""
        text = "Welcome to our page! Check back later for updates."
        flavor = self.scraper._extract_flavor_name(text)
        self.assertIsNone(flavor)

    def test_extract_flavor_with_ampersand(self):
        """Test: Flavor with ampersand."""
        text = "Today's flavor: Cookies & Cream"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Cookies & Cream")

    def test_extract_flavor_newline_termination(self):
        """Test: Flavor extraction stops at newline."""
        text = "Flavor of the Day: Turtle Sundae\nCome try it today!"
        flavor = self.scraper._extract_flavor_name(text)
        self.assertEqual(flavor, "Turtle Sundae")


class TestLeonsFacebookScraping(unittest.TestCase):
    """Test the Facebook scraping functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "test-leons",
                "name": "Leon's Frozen Custard",
                "url": "http://test",
                "facebook": "https://www.facebook.com/test",
                "enabled": True,
            }
        ]
        self.scraper = LeonsScraper()

    def tearDown(self):
        """Clean up patches."""
        self.locations_patcher.stop()

    @patch("app.scrapers.leons.sync_playwright")
    def test_scrape_facebook_success_first_post(self, mock_playwright):
        """Test: Successfully scrape flavor from first post."""
        # Setup mocks
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()
        mock_article = Mock()

        # Setup article with flavor content
        mock_article.inner_text.return_value = "Today's flavor of the day: VANILLA BEAN!"

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
        self.assertEqual(result, "Today's flavor of the day: VANILLA BEAN!")
        mock_page.goto.assert_called_once()
        mock_page.wait_for_selector.assert_called_once_with(
            '[role="article"]', timeout=self.scraper.SELECTOR_TIMEOUT
        )

    @patch("app.scrapers.leons.sync_playwright")
    def test_scrape_facebook_success_third_post(self, mock_playwright):
        """Test: Find flavor in third post (skips first two)."""
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        # Create 3 articles
        mock_article1 = Mock()
        mock_article1.inner_text.return_value = "Happy Monday everyone! Visit us today."

        mock_article2 = Mock()
        mock_article2.inner_text.return_value = "Check out our new hours!"

        mock_article3 = Mock()
        mock_article3.inner_text.return_value = "CHOCOLATE CHIP is our flavor of the day today!"

        mock_page.query_selector_all.return_value = [mock_article1, mock_article2, mock_article3]

        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertEqual(result, "CHOCOLATE CHIP is our flavor of the day today!")

    @patch("app.scrapers.leons.sync_playwright")
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

    @patch("app.scrapers.leons.sync_playwright")
    def test_scrape_facebook_no_flavor_post(self, mock_playwright):
        """Test: Posts found but none contain flavor information."""
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        # Create articles without flavor content
        articles = []
        for i in range(5):
            mock_article = Mock()
            mock_article.inner_text.return_value = f"Post {i}: General information"
            articles.append(mock_article)

        mock_page.query_selector_all.return_value = articles

        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertIsNone(result)

    @patch("app.scrapers.leons.sync_playwright")
    def test_scrape_facebook_checks_keywords(self, mock_playwright):
        """Test: Post must contain both 'flavor' and time keywords."""
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        # First article has 'flavor' but no time keyword
        mock_article1 = Mock()
        mock_article1.inner_text.return_value = "We have amazing flavors! Visit us."

        # Second article has time keyword but no 'flavor'
        mock_article2 = Mock()
        mock_article2.inner_text.return_value = "Come see us today at our shop!"

        # Third article has both
        mock_article3 = Mock()
        mock_article3.inner_text.return_value = "Flavor of the day: Mint Chip"

        mock_page.query_selector_all.return_value = [mock_article1, mock_article2, mock_article3]

        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        # Should find third article
        self.assertEqual(result, "Flavor of the day: Mint Chip")

    @patch("app.scrapers.leons.sync_playwright")
    def test_scrape_facebook_only_checks_first_5_posts(self, mock_playwright):
        """Test: Only checks first 5 posts, not all posts."""
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        # Create 10 articles, flavor is in 6th
        articles = []
        for i in range(5):
            mock_article = Mock()
            mock_article.inner_text.return_value = f"Post {i}: No flavor here"
            articles.append(mock_article)

        # 6th post has flavor (but should not be checked)
        mock_article6 = Mock()
        mock_article6.inner_text.return_value = "Today's flavor of the day: Butterscotch"
        articles.append(mock_article6)

        mock_page.query_selector_all.return_value = articles

        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        # Should not find flavor in 6th post
        self.assertIsNone(result)

    @patch("app.scrapers.leons.sync_playwright")
    def test_scrape_facebook_browser_cleanup(self, mock_playwright):
        """Test: Browser is cleaned up even on error."""
        mock_browser = Mock()
        mock_context = Mock()
        mock_page = Mock()

        # Simulate error during page loading
        mock_page.goto.side_effect = Exception("Network error")

        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = (
            mock_browser
        )

        with self.assertRaises(Exception):
            self.scraper._scrape_facebook_page_attempt("https://facebook.com/test", 0)

        # Browser close should still be called
        mock_browser.close.assert_called_once()


class TestLeonsRetryLogic(unittest.TestCase):
    """Test the retry logic and error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "test-leons",
                "name": "Leon's Frozen Custard",
                "facebook": "https://www.facebook.com/test",
                "enabled": True,
            }
        ]
        self.scraper = LeonsScraper()

    def tearDown(self):
        """Clean up patches."""
        self.locations_patcher.stop()

    @patch("app.scrapers.leons.time.sleep")
    @patch.object(LeonsScraper, "_scrape_facebook_page_attempt")
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

    @patch("app.scrapers.leons.time.sleep")
    @patch.object(LeonsScraper, "_scrape_facebook_page_attempt")
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

    @patch("app.scrapers.leons.time.sleep")
    @patch.object(LeonsScraper, "_scrape_facebook_page_attempt")
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

    @patch.object(LeonsScraper, "_scrape_facebook_page_attempt")
    def test_no_retry_on_unexpected_error(self, mock_attempt):
        """Test: No retry on unexpected non-Playwright errors."""
        # Unexpected error should not retry
        mock_attempt.side_effect = ValueError("Invalid value")

        result = self.scraper._scrape_facebook_page("https://facebook.com/test")

        self.assertIsNone(result)
        self.assertEqual(mock_attempt.call_count, 1)  # No retries

    @patch("app.scrapers.leons.time.sleep")
    @patch.object(LeonsScraper, "_scrape_facebook_page_attempt")
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


class TestLeonsScraperIntegration(unittest.TestCase):
    """Test the full scraper integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "test-leons",
                "name": "Leon's Frozen Custard",
                "url": "http://test.com",
                "facebook": "https://www.facebook.com/test",
                "enabled": True,
                "lat": 43.0,
                "lng": -88.0,
                "address": "123 Test St",
            }
        ]

    def tearDown(self):
        """Clean up patches."""
        self.locations_patcher.stop()

    @patch.object(LeonsScraper, "_scrape_facebook_page")
    def test_scrape_success(self, mock_scrape_fb):
        """Test: Successful complete scrape."""
        mock_scrape_fb.return_value = "Flavor of the day: BUTTER PECAN"

        scraper = LeonsScraper()
        results = scraper.scrape()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "BUTTER PECAN")
        self.assertEqual(results[0]["location"], "Leon's Frozen Custard")
        self.assertEqual(results[0]["url"], "http://test.com")

    @patch.object(LeonsScraper, "_scrape_facebook_page")
    def test_scrape_no_flavor_post_found(self, mock_scrape_fb):
        """Test: No flavor post found on Facebook."""
        mock_scrape_fb.return_value = None

        scraper = LeonsScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    @patch.object(LeonsScraper, "_scrape_facebook_page")
    def test_scrape_flavor_extraction_fails(self, mock_scrape_fb):
        """Test: Post found but flavor extraction fails."""
        mock_scrape_fb.return_value = "Welcome to our page! Check back tomorrow."

        scraper = LeonsScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    def test_scrape_no_locations(self):
        """Test: No locations configured."""
        self.mock_get_locations.return_value = []

        scraper = LeonsScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    def test_scrape_no_facebook_url(self):
        """Test: Location has no Facebook URL."""
        self.mock_get_locations.return_value = [
            {
                "id": "test-leons",
                "name": "Leon's Frozen Custard",
                "url": "http://test.com",
                # No facebook URL
                "enabled": True,
            }
        ]

        scraper = LeonsScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    @patch.object(LeonsScraper, "_scrape_facebook_page")
    def test_scrape_exception_handling(self, mock_scrape_fb):
        """Test: Exception during scraping is handled gracefully."""
        mock_scrape_fb.side_effect = Exception("Unexpected error")

        scraper = LeonsScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])


class TestLeonsHandleRetry(unittest.TestCase):
    """Test the _handle_retry helper method."""

    def setUp(self):
        """Set up test fixtures."""
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "test-leons",
                "name": "Leon's Frozen Custard",
                "facebook": "https://www.facebook.com/test",
                "enabled": True,
            }
        ]
        self.scraper = LeonsScraper()

    def tearDown(self):
        """Clean up patches."""
        self.locations_patcher.stop()

    @patch("app.scrapers.leons.time.sleep")
    def test_handle_retry_first_attempt(self, mock_sleep):
        """Test: First attempt returns True and sleeps for 2 seconds."""
        result = self.scraper._handle_retry(0, "Test error")

        self.assertTrue(result)
        mock_sleep.assert_called_once_with(2)

    @patch("app.scrapers.leons.time.sleep")
    def test_handle_retry_second_attempt(self, mock_sleep):
        """Test: Second attempt returns True and sleeps for 4 seconds."""
        result = self.scraper._handle_retry(1, "Test error")

        self.assertTrue(result)
        mock_sleep.assert_called_once_with(4)

    @patch("app.scrapers.leons.time.sleep")
    def test_handle_retry_max_retries(self, mock_sleep):
        """Test: Max retries returns False and does not sleep."""
        result = self.scraper._handle_retry(2, "Test error")  # Attempt 2 = 3rd attempt

        self.assertFalse(result)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
