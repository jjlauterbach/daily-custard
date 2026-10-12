"""Unit tests for Culver's scraper."""

import unittest
from unittest.mock import Mock, patch

import requests

from app.scrapers.culvers import CulversScraper


class TestCulversScraper(unittest.TestCase):
    """Tests for Culver's API fetching."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.locations_patcher.start().return_value = []
        self.scraper = CulversScraper()

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.culvers.time.sleep")
    def test_retries_api_timeout(self, mock_sleep):
        """A transient API timeout is retried before returning flavors."""
        response = Mock()
        response.json.return_value = {
            "data": {
                "geofences": [
                    {
                        "description": "Brookfield, WI - W Capitol Dr",
                        "metadata": {
                            "flavorOfDayName": "Butter Pecan",
                            "slug": "brookfield-capitol",
                            "city": "Brookfield",
                            "state": "WI",
                            "street": "123 Main St",
                            "postalCode": "53045",
                        },
                        "geometryCenter": {"coordinates": [-88.1, 43.0]},
                    }
                ]
            }
        }
        self.scraper.session.get = Mock(side_effect=[requests.Timeout(), response])

        results = self.scraper.scrape()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "Butter Pecan")
        self.assertEqual(self.scraper.session.get.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("app.scrapers.culvers.time.sleep")
    def test_returns_empty_after_retries_exhausted(self, mock_sleep):
        """Repeated timeouts stop after API_MAX_RETRIES and return no results."""
        self.scraper.session.get = Mock(side_effect=requests.Timeout())

        results = self.scraper.scrape()

        self.assertEqual(results, [])
        self.assertEqual(self.scraper.session.get.call_count, self.scraper.API_MAX_RETRIES)
        self.assertEqual(mock_sleep.call_count, self.scraper.API_MAX_RETRIES - 1)

    @patch("app.scrapers.culvers.time.sleep")
    def test_does_not_retry_permanent_http_error(self, mock_sleep):
        """A 404 response fails immediately without retrying."""
        response = Mock(status_code=404)
        error = requests.HTTPError(response=response)
        failing = Mock()
        failing.raise_for_status.side_effect = error
        self.scraper.session.get = Mock(return_value=failing)

        results = self.scraper.scrape()

        self.assertEqual(results, [])
        self.assertEqual(self.scraper.session.get.call_count, 1)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
