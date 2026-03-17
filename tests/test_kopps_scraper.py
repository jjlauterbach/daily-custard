"""Unit tests for Kopp's scraper."""

import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from app.scrapers.kopps import KoppsScraper, scrape_kopps

TEST_LOCATIONS = [
    {
        "id": "kopps-brookfield",
        "name": "Kopp's Frozen Custard (Brookfield)",
        "brand_id": "kopps",
        "url": "https://www.kopps.com",
        "enabled": True,
    },
    {
        "id": "kopps-glendale",
        "name": "Kopp's Frozen Custard (Glendale)",
        "brand_id": "kopps",
        "url": "https://www.kopps.com",
        "enabled": True,
    },
]


def _make_soup(html):
    return BeautifulSoup(html, "html.parser")


class TestKoppsFlavorExtraction(unittest.TestCase):
    """Tests for Kopp's extraction helpers."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = TEST_LOCATIONS
        self.scraper = KoppsScraper()

    def tearDown(self):
        self.locations_patcher.stop()

    def test_extract_flavors_from_primary_section(self):
        """Extracts flavors and date from original wp-block-todays-flavors section."""
        html = _make_soup(
            """
            <div class="wp-block-todays-flavors">
              <h2>TODAY'S FLAVORS – MARCH 15, 2026</h2>
              <h3>BUTTER PECAN</h3>
              <p>A butterscotch flavor and whole roasted pecans</p>
              <h3>SONG SUNG BLUEBERRY</h3>
              <p>Cream cheese custard + blueberry custard</p>
              <h3>SHAKE OF THE MONTH</h3>
              <h3>SUNDAE OF THE MONTH</h3>
            </div>
            """
        )

        date_str, rows = self.scraper._extract_flavors(html)

        self.assertEqual(date_str, "MARCH 15, 2026")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "BUTTER PECAN")
        self.assertIn("butterscotch", rows[0][1].lower())
        self.assertEqual(rows[1][0], "SONG SUNG BLUEBERRY")

    def test_extract_flavors_heading_fallback_when_class_missing(self):
        """Falls back to heading-order extraction when section class is missing."""
        html = _make_soup(
            """
            <main>
              <h2>TODAY’S FLAVORS –MARCH 15, 2026</h2>
              <h3>BUTTER PECAN</h3>
              <h3>SONG SUNG BLUEBERRY</h3>
              <h3>SHAKE OF THE MONTH</h3>
              <h4>IRISH MINT SHAKE</h4>
            </main>
            """
        )

        date_str, rows = self.scraper._extract_flavors(html)

        self.assertEqual(date_str, "MARCH 15, 2026")
        self.assertEqual([name for name, _ in rows], ["BUTTER PECAN", "SONG SUNG BLUEBERRY"])

    def test_extract_date_handles_curly_apostrophe(self):
        """Date parser supports curly apostrophes and em dashes."""
        date_str = self.scraper._extract_date_from_heading("TODAY’S FLAVORS — March 15, 2026")
        self.assertEqual(date_str, "March 15, 2026")

    def test_detects_bot_challenge_text(self):
        """Challenge page markers are detected for retry strategy."""
        html = _make_soup(
            "<html><body><h1>Just a moment...</h1><p>Checking your browser</p></body></html>"
        )
        self.assertTrue(self.scraper._looks_like_bot_challenge(html))


class TestKoppsScrape(unittest.TestCase):
    """Integration-style tests for scrape()."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = TEST_LOCATIONS

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.kopps.KoppsScraper.get_html")
    def test_scrape_uses_heading_fallback_and_returns_all_locations(self, mock_get_html):
        """Fallback extraction returns one entry per flavor per location."""
        mock_get_html.return_value = _make_soup(
            """
            <html><body>
              <h2>TODAY'S FLAVORS - March 15, 2026</h2>
              <h3>BUTTER PECAN</h3>
              <h3>SONG SUNG BLUEBERRY</h3>
              <h3>SHAKE OF THE MONTH</h3>
            </body></html>
            """
        )

        results = KoppsScraper().scrape()

        self.assertEqual(len(results), 4)
        flavors = {item["flavor"] for item in results}
        self.assertEqual(flavors, {"BUTTER PECAN", "SONG SUNG BLUEBERRY"})
        self.assertTrue(all(item["date"] == "March 15, 2026" for item in results))

    @patch("app.scrapers.kopps.KoppsScraper._try_playwright_browser_fetch")
    @patch("app.scrapers.kopps.KoppsScraper.get_html")
    def test_scrape_returns_empty_when_html_missing(self, mock_get_html, mock_try_playwright):
        """Returns [] when both initial HTML fetch and Playwright fallback fail."""
        mock_get_html.return_value = None
        mock_try_playwright.return_value = None
        results = KoppsScraper().scrape()
        self.assertEqual(results, [])
        mock_try_playwright.assert_called_once_with("https://www.kopps.com")

    @patch("app.scrapers.kopps.KoppsScraper._try_playwright_browser_fetch")
    @patch("app.scrapers.kopps.KoppsScraper.get_html")
    def test_scrape_uses_playwright_fallback_when_initial_html_is_none(
        self, mock_get_html, mock_try_playwright
    ):
        """When get_html returns None, scraper falls back to Playwright and returns flavors."""
        mock_get_html.return_value = None
        mock_try_playwright.return_value = _make_soup(
            """
            <html><body>
              <h2>TODAY'S FLAVORS - March 15, 2026</h2>
              <h3>BUTTER PECAN</h3>
              <h3>SHAKE OF THE MONTH</h3>
            </body></html>
            """
        )

        results = KoppsScraper().scrape()

        self.assertEqual(len(results), 2)
        self.assertTrue(all(item["flavor"] == "BUTTER PECAN" for item in results))
        mock_try_playwright.assert_called_once_with("https://www.kopps.com")

    @patch("app.scrapers.kopps.KoppsScraper._try_playwright_browser_fetch")
    @patch("app.scrapers.kopps.KoppsScraper.get_html")
    def test_scrape_tries_playwright_fetch_when_initial_page_has_no_flavors(
        self, mock_get_html, mock_try_playwright
    ):
        """If first HTML has no flavors, scraper uses Playwright browser fetch."""
        mock_get_html.return_value = _make_soup(
            "<html><body><h1>Just a moment...</h1></body></html>"
        )
        mock_try_playwright.return_value = _make_soup(
            """
            <html><body>
              <h2>TODAY'S FLAVORS - March 15, 2026</h2>
              <h3>BUTTER PECAN</h3>
              <h3>SHAKE OF THE MONTH</h3>
            </body></html>
            """
        )

        results = KoppsScraper().scrape()

        self.assertEqual(len(results), 2)
        self.assertTrue(all(item["flavor"] == "BUTTER PECAN" for item in results))
        mock_try_playwright.assert_called_once_with("https://www.kopps.com")


class TestKoppsPlaywrightFetch(unittest.TestCase):
    """Tests for Playwright browser fetch strategy helpers."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = TEST_LOCATIONS
        self.scraper = KoppsScraper()

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.kopps.KoppsScraper._get_html_playwright")
    def test_try_playwright_browser_fetch_returns_html_when_markers_present(self, mock_playwright):
        """Playwright HTML is returned when it contains flavor markers."""
        mock_playwright.return_value = _make_soup(
            """
            <html><body>
              <h2>TODAY'S FLAVORS - March 15, 2026</h2>
              <h3>BUTTER PECAN</h3>
            </body></html>
            """
        )

        html = self.scraper._try_playwright_browser_fetch("https://www.kopps.com")

        self.assertIsNotNone(html)
        self.assertIn("TODAY'S FLAVORS", html.get_text(" "))
        mock_playwright.assert_called_once()

    @patch("app.scrapers.kopps.KoppsScraper._get_html_playwright")
    def test_try_playwright_browser_fetch_returns_none_without_markers(self, mock_playwright):
        """Playwright HTML is discarded when it does not contain flavor markers."""
        mock_playwright.return_value = _make_soup(
            "<html><body><h1>Access denied</h1></body></html>"
        )

        html = self.scraper._try_playwright_browser_fetch("https://www.kopps.com")

        self.assertIsNone(html)
        mock_playwright.assert_called_once()


class TestScrapeKoppsFunction(unittest.TestCase):
    """Tests for module-level scrape_kopps()."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = TEST_LOCATIONS

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.kopps.KoppsScraper.scrape")
    def test_scrape_kopps_function(self, mock_scrape):
        """scrape_kopps() delegates to KoppsScraper.scrape()."""
        mock_scrape.return_value = [{"flavor": "BUTTER PECAN"}]
        results = scrape_kopps()
        self.assertEqual(results, [{"flavor": "BUTTER PECAN"}])


if __name__ == "__main__":
    unittest.main()
