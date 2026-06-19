"""Unit tests for Robert's Frozen Custard scraper."""

import datetime
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from app.scrapers.roberts import RobertsScraper, scrape_roberts

TEST_LOCATION = {
    "id": "roberts-germantown",
    "name": "Robert's Frozen Custard",
    "brand_id": "roberts",
    "address": "N112W16040 Mequon Rd, Germantown, WI 53022",
    "lat": 43.22149598825682,
    "lng": -88.11066318472048,
    "url": "https://robertsfrozencustard.com/",
    "enabled": True,
}


def _make_soup(html):
    return BeautifulSoup(html, "html.parser")


def _make_flavor_calendar_html(*items):
    li_html = "\n".join(f"<li>{flavor}<br>{date_text}</li>" for flavor, date_text in items)
    return f"""
    <html><body>
      <h1>Flavor Calendar</h1>
      <ul>{li_html}</ul>
      <h1>Soup Calendar</h1>
      <ul><li>Soup Name<br>Mon, March 9, 2026</li></ul>
    </body></html>
    """


class TestRobertsExtractFlavor(unittest.TestCase):
    """Unit tests for Robert's extraction helpers."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]
        self.scraper = RobertsScraper()

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.roberts.get_central_time")
    def test_extract_todays_flavor_found(self, mock_central_time):
        """Returns today's flavor from the flavor calendar list."""
        mock_central_time.return_value = datetime.datetime(2026, 3, 9, 8, 0, 0)
        html = _make_flavor_calendar_html(
            ("Classic Mint Chip", "Sun, March 8, 2026"),
            ("Rice Krispie Crunch", "Mon, March 9, 2026"),
            ("French Silk Pie", "Tue, March 10, 2026"),
        )

        flavor, date_str = self.scraper._extract_todays_flavor(_make_soup(html))
        self.assertEqual(flavor, "Rice Krispie Crunch")
        self.assertEqual(date_str, "2026-03-09")

    @patch("app.scrapers.roberts.get_central_time")
    def test_extract_todays_flavor_not_found(self, mock_central_time):
        """Returns (None, None) when today's date is missing from list."""
        mock_central_time.return_value = datetime.datetime(2026, 3, 12, 8, 0, 0)
        html = _make_flavor_calendar_html(
            ("Rice Krispie Crunch", "Mon, March 9, 2026"),
            ("French Silk Pie", "Tue, March 10, 2026"),
        )

        flavor, date_str = self.scraper._extract_todays_flavor(_make_soup(html))
        self.assertIsNone(flavor)
        self.assertIsNone(date_str)

    def test_extract_todays_flavor_missing_heading(self):
        """Returns (None, None) when flavor calendar heading does not exist."""
        html = "<html><body><h1>Soup Calendar</h1><ul></ul></body></html>"
        flavor, date_str = self.scraper._extract_todays_flavor(_make_soup(html))
        self.assertIsNone(flavor)
        self.assertIsNone(date_str)

    def test_parse_calendar_item_invalid(self):
        """Invalid date text returns (None, None)."""
        html = "<li>Rice Krispie Crunch<br>Not a date</li>"
        li = _make_soup(html).find("li")
        flavor, parsed_date = self.scraper._parse_calendar_item(li)
        self.assertIsNone(flavor)
        self.assertIsNone(parsed_date)


class TestRobertsScrape(unittest.TestCase):
    """Integration-style tests for scrape()."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.roberts.get_central_time")
    @patch("app.scrapers.roberts.RobertsScraper.get_html")
    def test_scrape_returns_flavor_entry(self, mock_get_html, mock_central_time):
        """scrape() returns one well-formed flavor entry on success."""
        mock_central_time.return_value = datetime.datetime(2026, 3, 9, 8, 0, 0)
        html = _make_flavor_calendar_html(
            ("Rice Krispie Crunch", "Mon, March 9, 2026"),
            ("French Silk Pie", "Tue, March 10, 2026"),
        )
        mock_get_html.return_value = _make_soup(html)

        scraper = RobertsScraper()
        results = scraper.scrape()

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["flavor"], "Rice Krispie Crunch")
        self.assertEqual(result["location"], "Robert's Frozen Custard")
        self.assertEqual(result["brand"], "Robert's")
        self.assertEqual(result["brand_id"], "roberts")
        self.assertEqual(result["location_id"], "roberts-germantown")
        self.assertEqual(result["date"], "2026-03-09")
        self.assertEqual(result["url"], "https://robertsfrozencustard.com/")

    @patch("app.scrapers.roberts.RobertsScraper.get_html")
    def test_scrape_empty_when_html_fails(self, mock_get_html):
        """Returns [] when HTML retrieval fails."""
        mock_get_html.return_value = None
        results = RobertsScraper().scrape()
        self.assertEqual(results, [])

    @patch("app.scrapers.roberts.get_central_time")
    @patch("app.scrapers.roberts.RobertsScraper.get_html")
    def test_scrape_empty_when_today_missing(self, mock_get_html, mock_central_time):
        """Returns [] when no flavor exists for today's date."""
        mock_central_time.return_value = datetime.datetime(2026, 3, 20, 8, 0, 0)
        html = _make_flavor_calendar_html(
            ("Rice Krispie Crunch", "Mon, March 9, 2026"),
            ("French Silk Pie", "Tue, March 10, 2026"),
        )
        mock_get_html.return_value = _make_soup(html)

        results = RobertsScraper().scrape()
        self.assertEqual(results, [])

    @patch("app.scrapers.roberts.RobertsScraper.get_html")
    def test_scrape_handles_exception(self, mock_get_html):
        """Returns [] on unexpected exception."""
        mock_get_html.side_effect = RuntimeError("network error")
        results = RobertsScraper().scrape()
        self.assertEqual(results, [])

    def test_scrape_no_locations(self):
        """Returns [] when no locations are configured."""
        self.mock_get_locations.return_value = []
        results = RobertsScraper().scrape()
        self.assertEqual(results, [])


class TestScrapeRobertsFunction(unittest.TestCase):
    """Tests for module-level scrape_roberts()."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.roberts.get_central_time")
    @patch("app.scrapers.roberts.RobertsScraper.get_html")
    def test_scrape_roberts_function(self, mock_get_html, mock_central_time):
        """scrape_roberts() delegates to RobertsScraper.scrape()."""
        mock_central_time.return_value = datetime.datetime(2026, 3, 9, 8, 0, 0)
        html = _make_flavor_calendar_html(("Rice Krispie Crunch", "Mon, March 9, 2026"))
        mock_get_html.return_value = _make_soup(html)

        results = scrape_roberts()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "Rice Krispie Crunch")


if __name__ == "__main__":
    unittest.main()
