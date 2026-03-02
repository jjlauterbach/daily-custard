"""Unit tests for Le Duc's scraper."""

import unittest
from unittest.mock import MagicMock, Mock, patch

from app.scrapers.leducs import LeducsScraper, scrape_leducs


def _make_playwright_mocks(page_text=""):
    """Build a minimal tree of Playwright mocks and return (mock_sync_pw, page).

    Usage inside a test::

        mock_pw, mock_page = _make_playwright_mocks("...body text...")
        with patch("app.scrapers.leducs.sync_playwright", return_value=mock_pw):
            ...
    """
    mock_page = Mock()
    mock_page.inner_text.return_value = page_text
    mock_page.goto = Mock()
    mock_page.set_default_timeout = Mock()
    mock_page.wait_for_timeout = Mock()

    mock_browser = Mock()
    mock_browser.new_page.return_value = mock_page
    mock_browser.close = Mock()

    mock_chromium = Mock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw_instance = MagicMock()
    mock_pw_instance.__enter__ = Mock(return_value=mock_pw_instance)
    mock_pw_instance.__exit__ = Mock(return_value=False)
    mock_pw_instance.chromium = mock_chromium

    return mock_pw_instance, mock_page


class TestLeducsExtractFlavor(unittest.TestCase):
    """Test _extract_flavor() and _clean_flavor_name() directly."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "leducs-wales",
                "name": "LeDuc's Frozen Custard",
                "url": "https://leducscustard.com/",
                "enabled": True,
            }
        ]
        self.scraper = LeducsScraper()

    def tearDown(self):
        self.locations_patcher.stop()

    # --- _extract_flavor ---

    def test_extract_flavor_normal(self):
        """Typical homepage block returns the flavor name."""
        text = "FLAVOROF THE DAY\nCHOCOLATE PEANUT BUTTER CUP\n◦ SUNDAY, FEB 22"
        self.assertEqual(self.scraper._extract_flavor(text), "CHOCOLATE PEANUT BUTTER CUP")

    def test_extract_flavor_closed(self):
        """When the store is closed, CLOSED is returned as the flavor."""
        text = "FLAVOROF THE DAY\nCLOSED\n◦ MONDAY, FEB 23"
        self.assertEqual(self.scraper._extract_flavor(text), "CLOSED")

    def test_extract_flavor_closed_mixed_case(self):
        """Closed text is returned as-is."""
        text = "FLAVOR OF THE DAY\nClosed (Winter)\n"
        self.assertEqual(self.scraper._extract_flavor(text), "Closed (Winter)")

    def test_extract_flavor_missing_block(self):
        """Returns None when the FLAVOR OF THE DAY block is absent."""
        text = "Welcome to LeDuc's!"
        self.assertIsNone(self.scraper._extract_flavor(text))

    def test_extract_flavor_spaced_header(self):
        """Handles whitespace variants in the header."""
        text = "FLAVOR  OF  THE  DAY\nMINT OREO\n"
        self.assertEqual(self.scraper._extract_flavor(text), "MINT OREO")

    # --- _clean_flavor_name ---

    def test_clean_flavor_name_with_date_number(self):
        """Leading date number is stripped."""
        self.assertEqual(
            self.scraper._clean_flavor_name("22 CHOCOLATE PEANUT BUTTER CUP"),
            "Chocolate Peanut Butter Cup",
        )

    def test_clean_flavor_name_with_day_name(self):
        """Leading day name is stripped."""
        self.assertEqual(
            self.scraper._clean_flavor_name("SUNDAY CHOCOLATE PEANUT BUTTER CUP"),
            "Chocolate Peanut Butter Cup",
        )

    def test_clean_flavor_name_all_caps(self):
        """All-caps is title-cased."""
        self.assertEqual(self.scraper._clean_flavor_name("MINT OREO"), "Mint Oreo")

    def test_clean_flavor_name_bullet(self):
        """Leading bullet is stripped."""
        self.assertEqual(self.scraper._clean_flavor_name("• CARAMEL CASHEW"), "Caramel Cashew")

    def test_clean_flavor_name_with_ampersand(self):
        """Ampersands are preserved."""
        self.assertEqual(
            self.scraper._clean_flavor_name("CHOCOLATE CHIP & PEANUT BUTTER"),
            "Chocolate Chip & Peanut Butter",
        )

    def test_clean_flavor_name_internal_hyphen_preserved(self):
        """Internal hyphens are not removed."""
        self.assertEqual(self.scraper._clean_flavor_name("BUTTER-PECAN"), "Butter-Pecan")

    def test_clean_flavor_name_already_title_case(self):
        """Already properly cased names are unchanged."""
        self.assertEqual(
            self.scraper._clean_flavor_name("Salted Caramel Crunch"), "Salted Caramel Crunch"
        )


class TestLeducsScrapeIntegration(unittest.TestCase):
    """Test scrape() using mocked Playwright."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "leducs-wales",
                "name": "LeDuc's Frozen Custard",
                "url": "https://leducscustard.com/",
                "enabled": True,
            }
        ]

    def tearDown(self):
        self.locations_patcher.stop()

    def test_scrape_returns_flavor(self):
        """Happy path: homepage contains a flavor."""
        page_text = "FLAVOROF THE DAY\nCHOCOLATE PEANUT BUTTER CUP\n◦ SUNDAY, FEB 22"
        mock_pw, _ = _make_playwright_mocks(page_text)

        with patch("app.scrapers.leducs.sync_playwright", return_value=mock_pw):
            result = LeducsScraper().scrape()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["flavor"], "Chocolate Peanut Butter Cup")
        self.assertEqual(result[0]["location"], "LeDuc's Frozen Custard")
        self.assertEqual(result[0]["brand"], "Le Duc's")
        self.assertEqual(result[0]["brand_id"], "leducs")

    def test_scrape_store_closed(self):
        """Store is closed today — returns flavor as 'Closed'."""
        page_text = "FLAVOROF THE DAY\nCLOSED\n◦ MONDAY, FEB 23"
        mock_pw, _ = _make_playwright_mocks(page_text)

        with patch("app.scrapers.leducs.sync_playwright", return_value=mock_pw):
            result = LeducsScraper().scrape()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["flavor"], "Closed")

    def test_scrape_flavor_block_missing(self):
        """No FLAVOR OF THE DAY block on page — returns empty list."""
        mock_pw, _ = _make_playwright_mocks("Welcome to LeDuc's!")

        with patch("app.scrapers.leducs.sync_playwright", return_value=mock_pw):
            result = LeducsScraper().scrape()

        self.assertEqual(result, [])

    def test_scrape_playwright_timeout(self):
        """PlaywrightTimeoutError exhausts all retries and returns empty list."""
        from playwright.sync_api import TimeoutError as PWTimeout

        mock_pw, mock_page = _make_playwright_mocks()
        mock_page.goto.side_effect = PWTimeout("timeout")

        with (
            patch("app.scrapers.leducs.sync_playwright", return_value=mock_pw),
            patch("app.scrapers.leducs.time.sleep") as mock_sleep,
        ):
            result = LeducsScraper().scrape()

        self.assertEqual(result, [])
        # All MAX_RETRIES attempts were made
        self.assertEqual(mock_page.goto.call_count, LeducsScraper.MAX_RETRIES)
        # Exponential backoff sleep was called between retries (MAX_RETRIES - 1 times)
        self.assertEqual(mock_sleep.call_count, LeducsScraper.MAX_RETRIES - 1)

    def test_scrape_playwright_timeout_succeeds_on_retry(self):
        """PlaywrightTimeoutError on first attempt, success on second."""
        from playwright.sync_api import TimeoutError as PWTimeout

        page_text = "FLAVOROF THE DAY\nSTRAWBERRY CHEESECAKE\n"
        mock_pw, mock_page = _make_playwright_mocks(page_text)
        mock_page.goto.side_effect = [PWTimeout("timeout"), None]

        with (
            patch("app.scrapers.leducs.sync_playwright", return_value=mock_pw),
            patch("app.scrapers.leducs.time.sleep"),
        ):
            result = LeducsScraper().scrape()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["flavor"], "Strawberry Cheesecake")
        self.assertEqual(mock_page.goto.call_count, 2)

    def test_scrape_playwright_error_retried(self):
        """PlaywrightError (non-timeout) is also retried with backoff."""
        from playwright.sync_api import Error as PWError

        mock_pw, mock_page = _make_playwright_mocks()
        mock_page.goto.side_effect = PWError("network crash")

        with (
            patch("app.scrapers.leducs.sync_playwright", return_value=mock_pw),
            patch("app.scrapers.leducs.time.sleep") as mock_sleep,
        ):
            result = LeducsScraper().scrape()

        self.assertEqual(result, [])
        self.assertEqual(mock_page.goto.call_count, LeducsScraper.MAX_RETRIES)
        self.assertEqual(mock_sleep.call_count, LeducsScraper.MAX_RETRIES - 1)

    def test_scrape_generic_exception(self):
        """Unexpected exceptions are caught and return empty list."""
        mock_pw, mock_page = _make_playwright_mocks()
        mock_page.goto.side_effect = Exception("network error")

        with patch("app.scrapers.leducs.sync_playwright", return_value=mock_pw):
            result = LeducsScraper().scrape()

        self.assertEqual(result, [])

    def test_scrape_url_preserved_as_configured(self):
        """URL is used exactly as configured in locations.yaml (trailing slash preserved)."""
        page_text = "FLAVOROF THE DAY\nMINT OREO\n"
        mock_pw, mock_page = _make_playwright_mocks(page_text)

        with patch("app.scrapers.leducs.sync_playwright", return_value=mock_pw):
            result = LeducsScraper().scrape()

        called_url = mock_page.goto.call_args[0][0]
        self.assertEqual(called_url, "https://leducscustard.com/")
        self.assertEqual(result[0]["url"], "https://leducscustard.com/")


class TestLeducsScraperNoLocations(unittest.TestCase):
    """Test Le Duc's scraper when no locations are configured."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = []

    def tearDown(self):
        self.locations_patcher.stop()

    def test_scrape_no_locations(self):
        """Scraping with no locations returns empty list without hitting the network."""
        result = LeducsScraper().scrape()
        self.assertEqual(result, [])


class TestLeducsScrapeFunctionIntegration(unittest.TestCase):
    """Integration tests for scrape_leducs function."""

    @patch("app.scrapers.leducs.LeducsScraper.scrape")
    def test_scrape_leducs_function(self, mock_scrape):
        """Test the scrape_leducs convenience function."""
        mock_scrape.return_value = [
            {
                "location": "LeDuc's Frozen Custard",
                "flavor": "Test Flavor",
                "description": "",
                "date": "2026-02-22",
                "url": "https://leducscustard.com/",
                "brand": "Le Duc's",
                "brand_id": "leducs",
            }
        ]

        result = scrape_leducs()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["flavor"], "Test Flavor")
        mock_scrape.assert_called_once()


if __name__ == "__main__":
    unittest.main()
