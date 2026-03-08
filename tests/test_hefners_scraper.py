"""Unit tests for Hefner's Custard scraper."""

import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from app.scrapers.hefners import HefnersScraper, scrape_hefners

TEST_LOCATION = {
    "id": "hefners-cedarburg",
    "name": "Hefner's Custard",
    "brand_id": "hefners",
    "address": "N71W5184 Columbia Rd, Cedarburg, WI 53012",
    "lat": 43.3019228,
    "lng": -87.9749195,
    "url": "https://www.hefnerscustard.com/",
    "enabled": True,
}


def _make_page_html(flavor_name, description="", extra_sections=""):
    """Build a minimal HTML page matching Hefner's homepage structure."""
    desc_block = f"<p>{description}</p>" if description else ""
    return f"""
    <html><body>
      <div class="page-main">
        <span>FLAVOR OF THE DAY</span>
        <h3>{flavor_name}</h3>
        {desc_block}
        {extra_sections}
      </div>
    </html>"""


def _make_soup(html):
    return BeautifulSoup(html, "html.parser")


class TestHefnersExtractFlavor(unittest.TestCase):
    """Unit tests for _extract_flavor()."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]
        self.scraper = HefnersScraper()

    def tearDown(self):
        self.locations_patcher.stop()

    def test_extract_flavor_with_description(self):
        """Typical page returns flavor name and description."""
        html = _make_page_html(
            "CHOCOLATE TRUFFLE",
            "Creamy vanilla custard flavored with chocolate, rum and loaded with milk chocolate flakes.",
        )
        flavor, desc = self.scraper._extract_flavor(_make_soup(html))
        self.assertEqual(flavor, "CHOCOLATE TRUFFLE")
        self.assertIn("chocolate", desc.lower())

    def test_extract_flavor_no_description(self):
        """Returns flavor name with empty description when no <p> follows."""
        html = _make_page_html("STRAWBERRY SHORTCAKE")
        flavor, desc = self.scraper._extract_flavor(_make_soup(html))
        self.assertEqual(flavor, "STRAWBERRY SHORTCAKE")
        self.assertEqual(desc, "")

    def test_extract_flavor_case_insensitive_label(self):
        """Label matching is case-insensitive (e.g. 'flavor of the day')."""
        html = """
        <html><body>
          <span>flavor of the day</span>
          <h3>BUTTER PECAN</h3>
        </body></html>"""
        flavor, desc = self.scraper._extract_flavor(_make_soup(html))
        self.assertEqual(flavor, "BUTTER PECAN")

    def test_extract_flavor_condensed_label(self):
        """Handles 'FLAVOROF THE DAY' (no space) as seen in page text extraction."""
        html = """
        <html><body>
          <div><span>FLAVOROF THE DAY</span>
          <h3>RASPBERRY CHEESECAKE</h3></div>
        </body></html>"""
        flavor, desc = self.scraper._extract_flavor(_make_soup(html))
        self.assertEqual(flavor, "RASPBERRY CHEESECAKE")

    def test_extract_flavor_ignores_sundae_section(self):
        """The FLAVOR OF THE DAY h3 is returned, not SUNDAE OF THE MONTH h3."""
        html = """
        <html><body>
          <div>
            <span>FLAVOR OF THE DAY</span>
            <h3>LEMON CUSTARD</h3>
            <p>Fresh lemons blended into vanilla custard.</p>
          </div>
          <div>
            <span>SUNDAE OF THE MONTH</span>
            <h3>HOT FUDGE BROWNIE</h3>
          </div>
        </body></html>"""
        flavor, desc = self.scraper._extract_flavor(_make_soup(html))
        self.assertEqual(flavor, "LEMON CUSTARD")

    def test_extract_flavor_missing_label(self):
        """Returns the first h3 that's not a monthly special, even without label."""
        # With the current implementation, any h3 not matching monthly keywords is returned
        html = "<html><body><h3>MYSTERY FLAVOR</h3></body></html>"
        flavor, desc = self.scraper._extract_flavor(_make_soup(html))
        # This now returns the h3 content since it doesn't match monthly keywords
        self.assertEqual(flavor, "MYSTERY FLAVOR")
        self.assertEqual(desc, "")

    def test_extract_flavor_only_monthly_specials(self):
        """Returns (None, None) when all h3 tags are monthly specials."""
        html = """
        <html><body>
            <h3>GIRL SCOUT THIN MINTS SHAKE</h3>
            <h3>HOT FUDGE SUNDAE</h3>
            <h3>LOBSTER ROLL</h3>
        </body></html>"""
        flavor, desc = self.scraper._extract_flavor(_make_soup(html))
        self.assertIsNone(flavor)
        self.assertIsNone(desc)

    def test_extract_flavor_missing_h3(self):
        """Returns (None, None) when no h3 follows the label."""
        html = """
        <html><body>
          <span>FLAVOR OF THE DAY</span>
          <p>Some other content.</p>
        </body></html>"""
        flavor, desc = self.scraper._extract_flavor(_make_soup(html))
        self.assertIsNone(flavor)

    def test_extract_flavor_multiword_name(self):
        """Multi-word flavor names are returned in full."""
        html = _make_page_html("HEATH BAR CRUNCH")
        flavor, desc = self.scraper._extract_flavor(_make_soup(html))
        self.assertEqual(flavor, "HEATH BAR CRUNCH")


class TestHefnersScrape(unittest.TestCase):
    """Integration-style tests for the full scrape() method."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.hefners.HefnersScraper.get_html")
    def test_scrape_returns_flavor_entry(self, mock_get_html):
        """scrape() returns a well-formed flavor dict when HTML is valid."""
        html = _make_page_html(
            "CHOCOLATE TRUFFLE",
            "Creamy vanilla custard flavored with chocolate, rum and loaded with milk chocolate flakes.",
        )
        mock_get_html.return_value = _make_soup(html)

        scraper = HefnersScraper()
        results = scraper.scrape()

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["flavor"], "CHOCOLATE TRUFFLE")
        self.assertEqual(result["location"], "Hefner's Custard")
        self.assertEqual(result["brand"], "Hefner's")
        self.assertEqual(result["brand_id"], "hefners")
        self.assertIn("chocolate", result["description"].lower())
        self.assertIn("date", result)
        self.assertEqual(result["lat"], 43.3019228)
        self.assertEqual(result["lng"], -87.9749195)
        self.assertEqual(result["address"], "N71W5184 Columbia Rd, Cedarburg, WI 53012")
        self.assertEqual(result["location_id"], "hefners-cedarburg")

    @patch("app.scrapers.hefners.HefnersScraper.get_html")
    def test_scrape_returns_empty_on_no_flavor(self, mock_get_html):
        """scrape() returns [] when the page has no FLAVOR OF THE DAY section."""
        mock_get_html.return_value = _make_soup("<html><body><p>Welcome!</p></body></html>")

        scraper = HefnersScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    @patch("app.scrapers.hefners.HefnersScraper.get_html")
    def test_scrape_returns_empty_on_html_failure(self, mock_get_html):
        """scrape() returns [] when get_html returns None."""
        mock_get_html.return_value = None

        scraper = HefnersScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    @patch("app.scrapers.hefners.HefnersScraper.get_html")
    def test_scrape_handles_exception(self, mock_get_html):
        """scrape() returns [] instead of raising when an unexpected error occurs."""
        mock_get_html.side_effect = RuntimeError("network error")

        scraper = HefnersScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    def test_scrape_returns_empty_when_no_locations(self):
        """scrape() returns [] gracefully when no locations are configured."""
        self.mock_get_locations.return_value = []
        scraper = HefnersScraper()
        results = scraper.scrape()
        self.assertEqual(results, [])


class TestScrapeHefnersFunction(unittest.TestCase):
    """Tests for the module-level scrape_hefners() convenience function."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.hefners.HefnersScraper.get_html")
    def test_scrape_hefners_function(self, mock_get_html):
        """scrape_hefners() delegates to HefnersScraper.scrape()."""
        html = _make_page_html("MINT CHIP")
        mock_get_html.return_value = _make_soup(html)

        results = scrape_hefners()

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "MINT CHIP")


if __name__ == "__main__":
    unittest.main()
