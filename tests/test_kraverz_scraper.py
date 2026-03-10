"""Unit tests for Kraverz scraper."""

import unittest
from datetime import date, datetime
from unittest.mock import patch

from bs4 import BeautifulSoup

from app.scrapers.kraverz import KraverzScraper, scrape_kraverz

TEST_LOCATION = {
    "id": "kraverz-main",
    "name": "Kraverz Frozen Custard",
    "brand_id": "kraverz",
    "address": "N88W15325 Main St, Menomonee Falls, WI 53051",
    "lat": 43.1777989,
    "lng": -88.1001884,
    "url": "https://www.kraverzcustard.com/",
    "enabled": True,
}


class TestKraverzFlavorExtraction(unittest.TestCase):
    """Unit tests for Kraverz extraction helpers."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]
        self.scraper = KraverzScraper()

    def tearDown(self):
        self.locations_patcher.stop()

    def test_extract_today_flavor_section(self):
        text = "Today's Flavor of the Day: CLOSED DON’T MISS OUT ON YOUR FAVORITE CUSTARD FLAVOR!"
        self.assertEqual(self.scraper._extract_today_flavor(text), "CLOSED")

    def test_extract_scheduled_flavor_for_date(self):
        text = "03/08 CLOSED 03/09 KIT KAT BAR 03/10 MINT BROWNIE"
        flavor = self.scraper._extract_scheduled_flavor(text, date(2026, 3, 9))
        self.assertEqual(flavor, "KIT KAT BAR")

    def test_normalize_flavor_closed(self):
        self.assertEqual(self.scraper._normalize_flavor("  CLOSED "), "CLOSED")

    def test_normalize_flavor_all_caps_title_cases(self):
        self.assertEqual(self.scraper._normalize_flavor("CHOC HEATH CRUNCH"), "Choc Heath Crunch")


class TestKraverzScrape(unittest.TestCase):
    """Integration-style tests for scrape()."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.kraverz.KraverzScraper.get_html")
    def test_scrape_returns_flavor_entry(self, mock_get_html):
        html = """
        <html><body>
          <h3>Today's Flavor of the Day:</h3>
          <p>CLOSED</p>
          <div>DON'T MISS OUT ON YOUR FAVORITE CUSTARD FLAVOR!</div>
        </body></html>
        """
        mock_get_html.return_value = BeautifulSoup(html, "html.parser")

        results = KraverzScraper().scrape()

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["flavor"], "CLOSED")
        self.assertEqual(result["location"], "Kraverz Frozen Custard")
        self.assertEqual(result["brand"], "Kraverz")
        self.assertEqual(result["brand_id"], "kraverz")
        self.assertEqual(result["location_id"], "kraverz-main")
        self.assertEqual(result["lat"], 43.1777989)
        self.assertEqual(result["lng"], -88.1001884)

    @patch("app.scrapers.kraverz.get_central_time")
    @patch("app.scrapers.kraverz.KraverzScraper.get_html")
    def test_scrape_falls_back_to_schedule_line(self, mock_get_html, mock_get_central_time):
        mock_get_central_time.return_value = datetime(2026, 3, 9, 12, 0, 0)
        html = """
        <html><body>
          <div>FLAVOR OF THE DAY SCHEDULE</div>
          <div>03/08 CLOSED 03/09 KIT KAT BAR 03/10 MINT BROWNIE</div>
        </body></html>
        """
        mock_get_html.return_value = BeautifulSoup(html, "html.parser")

        results = KraverzScraper().scrape()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "Kit Kat Bar")

    @patch("app.scrapers.kraverz.KraverzScraper.get_html")
    def test_scrape_returns_empty_when_no_flavor(self, mock_get_html):
        mock_get_html.return_value = BeautifulSoup(
            "<html><body>No schedule</body></html>", "html.parser"
        )

        results = KraverzScraper().scrape()

        self.assertEqual(results, [])

    @patch("app.scrapers.kraverz.KraverzScraper.get_html")
    def test_scrape_returns_empty_when_html_fails(self, mock_get_html):
        mock_get_html.return_value = None

        results = KraverzScraper().scrape()

        self.assertEqual(results, [])

    def test_scrape_returns_empty_when_no_locations(self):
        self.mock_get_locations.return_value = []
        results = KraverzScraper().scrape()
        self.assertEqual(results, [])


class TestScrapeKraverzFunction(unittest.TestCase):
    """Tests for module-level scrape_kraverz()."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.kraverz.KraverzScraper.get_html")
    def test_scrape_kraverz_function(self, mock_get_html):
        html = """
        <html><body>
          <h3>Today's Flavor of the Day:</h3>
          <p>CLOSED</p>
        </body></html>
        """
        mock_get_html.return_value = BeautifulSoup(html, "html.parser")

        results = scrape_kraverz()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "CLOSED")


if __name__ == "__main__":
    unittest.main()
