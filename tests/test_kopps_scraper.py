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

    @patch("app.scrapers.kopps.KoppsScraper.get_html")
    def test_scrape_returns_empty_when_html_missing(self, mock_get_html):
        """Returns [] when HTML fetch fails."""
        mock_get_html.return_value = None
        results = KoppsScraper().scrape()
        self.assertEqual(results, [])


class TestScrapeKoppsFunction(unittest.TestCase):
    """Tests for module-level scrape_kopps()."""

    @patch("app.scrapers.kopps.KoppsScraper.scrape")
    def test_scrape_kopps_function(self, mock_scrape):
        """scrape_kopps() delegates to KoppsScraper.scrape()."""
        mock_scrape.return_value = [{"flavor": "BUTTER PECAN"}]
        results = scrape_kopps()
        self.assertEqual(results, [{"flavor": "BUTTER PECAN"}])


if __name__ == "__main__":
    unittest.main()
