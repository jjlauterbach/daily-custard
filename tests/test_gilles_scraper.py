"""Unit tests for Gilles Frozen Custard scraper (OCR-based calendar image parsing)."""

import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from PIL import Image

from app.scrapers.gilles import GillesScraper, scrape_gilles
from app.scrapers.utils import get_central_time

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


def _week_range_for_today():
    """Return (start_day, end_day) for a 7-day window containing today."""
    today = get_central_time().day
    start = max(1, today - 3)
    return start, start + 6


def _make_page_html(start_day=None, end_day=None, month_name=None, matching=True):
    """Build minimal page HTML with an <img> pointing at a weekly calendar graphic."""
    today = get_central_time()
    if start_day is None or end_day is None:
        start_day, end_day = _week_range_for_today()
    month_name = month_name or today.strftime("%B")
    if not matching:
        # Shift the range so today's day-of-month falls outside it.
        start_day, end_day = 90, 96
    filename = f"{month_name}-{start_day}-{end_day}.png"
    src = (
        "https://static.wixstatic.com/media/6dbc8c_abc123~mv2.png"
        f"/v1/fill/w_976,h_381,al_c,q_85,enc_avif,quality_auto/{filename}"
    )
    return BeautifulSoup(
        f'<html><body><img src="{src}" alt="{filename}"></body></html>', "html.parser"
    )


def _make_image():
    return Image.new("RGB", (700, 100), color="white")


class TestGillesScraperFlavor(unittest.TestCase):
    """Unit tests for Gilles flavor extraction."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.gilles.pytesseract.image_to_string")
    @patch("app.scrapers.gilles.GillesScraper._download_image")
    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_returns_flavor(self, mock_get_html, mock_download, mock_ocr):
        """scrape() returns today's flavor read from the calendar image via OCR."""
        mock_get_html.return_value = _make_page_html()
        mock_download.return_value = _make_image()
        mock_ocr.return_value = "Turtle\n\nContains: Vanilla, Fudge swirl, Pecans"

        scraper = GillesScraper()
        results = scraper.scrape()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "Turtle")
        self.assertEqual(results[0]["description"], "Vanilla, Fudge swirl, Pecans")
        self.assertEqual(results[0]["location"], "Gilles Frozen Custard")
        self.assertEqual(results[0]["brand"], "Gilles")

    @patch("app.scrapers.gilles.pytesseract.image_to_string")
    @patch("app.scrapers.gilles.GillesScraper._download_image")
    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_returns_closed_when_closed(self, mock_get_html, mock_download, mock_ocr):
        """scrape() returns 'Closed' when OCR reads the closed-day column."""
        mock_get_html.return_value = _make_page_html()
        mock_download.return_value = _make_image()
        mock_ocr.return_value = "CLOSED"

        scraper = GillesScraper()
        results = scraper.scrape()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "Closed")
        self.assertEqual(results[0]["description"], "")

    @patch("app.scrapers.gilles.pytesseract.image_to_string")
    @patch("app.scrapers.gilles.GillesScraper._download_image")
    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_strips_leading_ocr_noise(self, mock_get_html, mock_download, mock_ocr):
        """scrape() drops stray lowercase/symbol tokens OCR picks up from the photo."""
        mock_get_html.return_value = _make_page_html()
        mock_download.return_value = _make_image()
        mock_ocr.return_value = "\u2122\u00bb Black Raspberry\n\nContains: Black raspberry"

        scraper = GillesScraper()
        results = scraper.scrape()

        self.assertEqual(results[0]["flavor"], "Black Raspberry")

    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_no_matching_week_image(self, mock_get_html):
        """scrape() returns [] when no calendar image covers today's date."""
        mock_get_html.return_value = _make_page_html(matching=False)

        scraper = GillesScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    @patch("app.scrapers.gilles.pytesseract.image_to_string")
    @patch("app.scrapers.gilles.GillesScraper._download_image")
    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_returns_empty_when_ocr_unreadable(self, mock_get_html, mock_download, mock_ocr):
        """scrape() returns [] when OCR produces no usable text."""
        mock_get_html.return_value = _make_page_html()
        mock_download.return_value = _make_image()
        mock_ocr.return_value = "   \n\n  "

        scraper = GillesScraper()
        results = scraper.scrape()

        self.assertEqual(results, [])

    @patch("app.scrapers.gilles.GillesScraper._download_image")
    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_image_download_failure(self, mock_get_html, mock_download):
        """scrape() returns [] when the calendar image fails to download."""
        mock_get_html.return_value = _make_page_html()
        mock_download.side_effect = RuntimeError("network error")

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


class TestGillesColumnParsing(unittest.TestCase):
    """Unit tests for the column-cropping and OCR-block parsing helpers."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]
        self.scraper = GillesScraper()

    def tearDown(self):
        self.locations_patcher.stop()

    def test_crop_day_column_picks_correct_slice(self):
        """_crop_day_column() isolates the column matching the requested day."""
        image = Image.new("RGB", (700, 100))
        pixels = image.load()
        # Paint each of the 7 columns (100px wide) a distinct shade of red.
        for col in range(7):
            for x in range(col * 100, (col + 1) * 100):
                for y in range(100):
                    pixels[x, y] = (col * 30, 0, 0)

        cropped = self.scraper._crop_day_column(image, day=13, start_day=11, end_day=17)

        self.assertEqual(cropped.size, (100, 100))
        self.assertEqual(cropped.getpixel((50, 50)), (2 * 30, 0, 0))

    def test_parse_day_column_splits_name_and_description(self):
        """_parse_day_column() separates the flavor name from the description."""
        with patch("app.scrapers.gilles.pytesseract.image_to_string") as mock_ocr:
            mock_ocr.return_value = "Pumpkin Deluxe\n\nPumpkin Real pumpkin puree,\nPecans"
            name, description = self.scraper._parse_day_column(Image.new("RGB", (10, 10)))

        self.assertEqual(name, "Pumpkin Deluxe")
        self.assertEqual(description, "Pumpkin Real pumpkin puree, Pecans")

    def test_parse_day_column_empty_text_returns_none(self):
        """_parse_day_column() returns (None, '') when OCR finds nothing."""
        with patch("app.scrapers.gilles.pytesseract.image_to_string") as mock_ocr:
            mock_ocr.return_value = ""
            name, description = self.scraper._parse_day_column(Image.new("RGB", (10, 10)))

        self.assertIsNone(name)
        self.assertEqual(description, "")


class TestScrapeGillesFunction(unittest.TestCase):
    """Tests for module-level scrape_gilles()."""

    def setUp(self):
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [TEST_LOCATION]

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.gilles.pytesseract.image_to_string")
    @patch("app.scrapers.gilles.GillesScraper._download_image")
    @patch("app.scrapers.gilles.GillesScraper.get_html")
    def test_scrape_gilles_function(self, mock_get_html, mock_download, mock_ocr):
        """scrape_gilles() delegates to GillesScraper.scrape()."""
        mock_get_html.return_value = _make_page_html()
        mock_download.return_value = _make_image()
        mock_ocr.return_value = "Red Raspberry\n\nContains: Raspberry"

        results = scrape_gilles()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["flavor"], "Red Raspberry")


if __name__ == "__main__":
    unittest.main()
