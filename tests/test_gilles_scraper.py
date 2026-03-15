"""Unit tests for Gilles Frozen Custard scraper."""

import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from app.scrapers.gilles import GillesScraper, scrape_gilles

TEST_LOCATION = {
    "id": "gilles-main",
    "name": "Gilles Frozen Custard",
    "brand_id": "gilles",
    "address": "7515 W Bluemound Rd, Milwaukee, WI 53213",
    "lat": 43.03514241290648,
    "lng": -88.00660788914804,
    "url": "https://gillesfrozencustard.com/flavor-of-the-day",
    "enabled": True,
}


def _make_soup(html):
    return BeautifulSoup(html, "html.parser")


def _make_calendar_html_with_flavor(flavor_name="Butter Pecan"):
    """Build minimal calendar HTML with a flavor link in today's cell."""
    return f"""
    <html><body>
      <table>
        <td class="single-day today">
          <div class="flavor">
            <div class="views-field-title">
              Flavor of the day:
              <a href="/flavor/{flavor_name.lower().replace(' ', '-')}/">{flavor_name}</a>
            </div>
          </div>
          <div class="flavor">
            <div class="views-field-title">
              Flavor of the month:
              <a href="/flavor/mint-chocolate-chip/">Mint Chocolate Chip</a>
            </div>
          </div>
        </td>
      </table>
    </body></html>
    """


def _make_calendar_html_closed():
    """Build calendar HTML showing today's cell as closed (no flavor links)."""
    return """
    <html><body>
      <table>
        <td class="single-day today">
          Closed
        </td>
      </table>
    </body></html>
    """


def _make_calendar_html_closed_link():
    """Build calendar HTML where today's flavor link text is 'Closed'."""
    return """
    <html><body>
      <table>
        <td class="single-day today">
          <div class="flavor">
            <div class="views-field-title">
              Flavor of the day:
              <a href="/flavor/closed/">Closed</a>
            </div>
          </div>
        </td>
      </table>
    </body></html>
    """


class TestGillesScraperFlavor(unittest.TestCase):
    """Unit tests for Gilles flavor extraction."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_returns_flavor(self, mock_get_html):
        """scrape() returns flavor when calendar contains flavor link."""
        html = _make_calendar_html_with_flavor("Turtle")
        mock_get_html.return_value = _make_soup(html)

        scraper = GillesScraper()
        results = scraper.scrape()

        self.assertGreaterEqual(len(results), 1)
        flavors = [entry["flavor"] for entry in results]
        self.assertIn("Turtle", flavors)
        self.assertTrue(all(entry["location"] == "Gilles Frozen Custard" for entry in results))
        self.assertTrue(all(entry["brand"] == "Gilles" for entry in results))

    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_returns_closed_when_closed(self, mock_get_html):
        """scrape() returns 'Closed' flavor when today's cell shows closed."""
        html = _make_calendar_html_closed()
        mock_get_html.return_value = _make_soup(html)

        scraper = GillesScraper()
        results = scraper.scrape()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "Closed")
        self.assertEqual(results[0]["location"], "Gilles Frozen Custard")

    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_closed_link_skips_detail_page_fetch(self, mock_get_html):
        """scrape() returns 'Closed' and does NOT fetch a detail page when the
        flavor link text is 'Closed' (i.e. <a href="/flavor/closed/">Closed</a>)."""
        html = _make_calendar_html_closed_link()
        mock_get_html.return_value = _make_soup(html)

        scraper = GillesScraper()
        results = scraper.scrape()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "Closed")
        # Only the calendar page should have been fetched; no detail-page call
        self.assertEqual(mock_get_html.call_count, 1)

    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_returns_empty_when_no_today_cell(self, mock_get_html):
        """scrape() returns [] when today's cell is not found."""
        html = "<html><body><table></table></body></html>"
        mock_get_html.return_value = _make_soup(html)

        scraper = GillesScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_empty_html(self, mock_get_html):
        """scrape() returns [] when HTML retrieval fails."""
        mock_get_html.return_value = None

        scraper = GillesScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_handles_exception(self, mock_get_html):
        """scrape() returns [] on exception."""
        mock_get_html.side_effect = RuntimeError("network error")

        scraper = GillesScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    def test_scrape_no_locations(self):
        """scrape() returns [] when no locations configured."""
        self.mock_get_locations.return_value = []
        scraper = GillesScraper()
        results = scraper.scrape()
        self.assertEqual(results, [])


class TestScrapeGillesFunction(unittest.TestCase):
    """Tests for module-level scrape_gilles()."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_gilles_function(self, mock_get_html):
        """scrape_gilles() delegates to GillesScraper.scrape()."""
        html = _make_calendar_html_with_flavor("Red Raspberry")
        mock_get_html.return_value = _make_soup(html)

        results = scrape_gilles()

        self.assertGreaterEqual(len(results), 1)
        flavors = [entry["flavor"] for entry in results]
        self.assertIn("Red Raspberry", flavors)


if __name__ == "__main__":
    unittest.main()
