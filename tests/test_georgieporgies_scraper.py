"""Unit tests for Georgie Porgie's scraper."""

import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

from app.scrapers.georgieporgies import GeorgiePorgiesScraper, scrape_georgieporgies

TEST_LOCATIONS = [
    {
        "id": "georgieporgies-oak-creek",
        "name": "Georgie Porgie's Treefort (Oak Creek)",
        "brand_id": "georgieporgies",
        "address": "9555 S Howell Ave, Oak Creek, WI 53154",
        "lat": 42.86686,
        "lng": -87.940491,
        "url": "https://georgieporgies.com",
        "enabled": True,
    },
    {
        "id": "georgieporgies-racine",
        "name": "Georgie Porgie's Treefort (Racine)",
        "brand_id": "georgieporgies",
        "address": "5502 Washington Ave, Racine, WI 53406",
        "lat": 42.72695,
        "lng": -87.84831,
        "url": "https://georgieporgies.com",
        "enabled": True,
    },
]


def _make_soup(html):
    return BeautifulSoup(html, "html.parser")


def _forecast_html(flavor_alt, description):
    return f"""
    <html>
      <body>
        <h2>Today's Flavor</h2>
        <img alt="{flavor_alt}" src="/flavor.webp" />
        <p>{description}</p>

        <h2>Tomorrow's Flavor</h2>
        <img alt="Flavor of the Day - Tomorrow Flavor" src="/tomorrow.webp" />
        <p>Tomorrow description</p>
      </body>
    </html>
    """


class TestGeorgiePorgiesScraper(unittest.TestCase):
    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = TEST_LOCATIONS

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper.get_html")
    def test_scrape_returns_today_flavor_for_all_locations(self, mock_get_html):
        html = _forecast_html(
            "Flavor of the Day - Nutella Banana Crunch",
            "Vanilla custard, banana slices, waffle pieces, Nutella swirls",
        )
        mock_get_html.return_value = _make_soup(html)

        results = GeorgiePorgiesScraper().scrape()

        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["flavor"] == "Nutella Banana Crunch" for r in results))
        self.assertTrue(all(r["brand_id"] == "georgieporgies" for r in results))
        self.assertEqual(
            results[0]["description"],
            "Vanilla custard, banana slices, waffle pieces, Nutella swirls",
        )

    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper.get_html")
    def test_scrape_returns_closed(self, mock_get_html):
        html = _forecast_html(
            "Closed for a Day of Prayer and Rest",
            "Closed for a Day of Prayer and Rest",
        )
        mock_get_html.return_value = _make_soup(html)

        results = GeorgiePorgiesScraper().scrape()

        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["flavor"] == "Closed" for r in results))

    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper._try_playwright_browser_fetch")
    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper.get_html")
    def test_scrape_returns_empty_when_today_heading_missing(
        self, mock_get_html, mock_try_playwright
    ):
        html = "<html><body><h2>Flavor Forecast</h2><p>No heading</p></body></html>"
        mock_get_html.return_value = _make_soup(html)
        mock_try_playwright.return_value = None

        results = GeorgiePorgiesScraper().scrape()

        self.assertEqual(results, [])

    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper._try_playwright_browser_fetch")
    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper.get_html")
    def test_scrape_returns_empty_when_html_missing(self, mock_get_html, mock_try_playwright):
        """Returns [] when both initial HTML fetch and Playwright fallback fail."""
        mock_get_html.return_value = None
        mock_try_playwright.return_value = None

        results = GeorgiePorgiesScraper().scrape()

        self.assertEqual(results, [])
        mock_try_playwright.assert_called_once_with(
            "https://georgieporgies.com/georgies-flavor-forecast/"
        )

    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper._try_playwright_browser_fetch")
    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper.get_html")
    def test_scrape_uses_playwright_fallback_when_initial_html_is_none(
        self, mock_get_html, mock_try_playwright
    ):
        """When get_html returns None, scraper falls back to Playwright and returns flavors."""
        mock_get_html.return_value = None
        mock_try_playwright.return_value = _make_soup(
            _forecast_html(
                "Flavor of the Day - Strawberry Cheesecake",
                "Fresh strawberries, cream cheese swirl",
            )
        )

        results = GeorgiePorgiesScraper().scrape()

        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["flavor"] == "Strawberry Cheesecake" for r in results))
        mock_try_playwright.assert_called_once_with(
            "https://georgieporgies.com/georgies-flavor-forecast/"
        )

    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper._try_playwright_browser_fetch")
    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper.get_html")
    def test_scrape_uses_playwright_fallback_when_extraction_fails(
        self, mock_get_html, mock_try_playwright
    ):
        """When first extraction finds no flavor, Playwright fallback is tried and succeeds."""
        mock_get_html.return_value = _make_soup(
            "<html><body><h2>Flavor Forecast</h2><p>No heading</p></body></html>"
        )
        mock_try_playwright.return_value = _make_soup(
            _forecast_html(
                "Flavor of the Day - Mint Chocolate Chip",
                "Refreshing mint with chocolate chips",
            )
        )

        results = GeorgiePorgiesScraper().scrape()

        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["flavor"] == "Mint Chocolate Chip" for r in results))
        mock_try_playwright.assert_called_once_with(
            "https://georgieporgies.com/georgies-flavor-forecast/"
        )

    def test_scrape_returns_empty_when_no_locations(self):
        self.mock_get_locations.return_value = []

        results = GeorgiePorgiesScraper().scrape()

        self.assertEqual(results, [])

    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper.scrape")
    def test_scrape_georgieporgies_function(self, mock_scrape):
        mock_scrape.return_value = [{"flavor": "Sample"}]

        results = scrape_georgieporgies()

        self.assertEqual(results, [{"flavor": "Sample"}])
        mock_scrape.assert_called_once()


class TestGeorgiePorgiesPlaywrightFetch(unittest.TestCase):
    """Tests for _try_playwright_browser_fetch helper."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = TEST_LOCATIONS
        self.scraper = GeorgiePorgiesScraper()

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper._get_html_playwright")
    def test_try_playwright_browser_fetch_returns_html_on_success(self, mock_playwright):
        """Playwright HTML is returned when _get_html_playwright succeeds."""
        mock_playwright.return_value = _make_soup(
            _forecast_html("Flavor of the Day - Caramel Apple", "Rich caramel swirl with apple")
        )

        html = self.scraper._try_playwright_browser_fetch(
            "https://georgieporgies.com/georgies-flavor-forecast/"
        )

        self.assertIsNotNone(html)
        mock_playwright.assert_called_once()

    @patch("app.scrapers.georgieporgies.GeorgiePorgiesScraper._get_html_playwright")
    def test_try_playwright_browser_fetch_returns_none_on_exception(self, mock_playwright):
        """Returns None when Playwright raises an exception."""
        mock_playwright.side_effect = Exception("Browser launch failed")

        html = self.scraper._try_playwright_browser_fetch(
            "https://georgieporgies.com/georgies-flavor-forecast/"
        )

        self.assertIsNone(html)


if __name__ == "__main__":
    unittest.main()
