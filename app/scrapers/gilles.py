import re
from datetime import datetime
from io import BytesIO

import pytesseract
from PIL import Image

from app.scrapers.scraper_base import REQUEST_TIMEOUT, BaseScraper
from app.scrapers.utils import get_central_time

# Matches the weekly calendar graphic filenames Gilles' Wix site publishes,
# e.g. "October-11-17.png" for the week spanning the 11th through the 17th.
WEEK_IMAGE_PATTERN = re.compile(r"^([A-Za-z]+)-(\d{1,2})-(\d{1,2})\.(?:png|jpe?g)$", re.IGNORECASE)
# Strips Wix's crop/fill transform segments to download the undistorted original image.
WIX_ORIGINAL_IMAGE_PATTERN = re.compile(
    r"(https?://static\.wixstatic\.com/media/[^/]+~mv2\.(?:png|jpe?g))", re.IGNORECASE
)


class GillesScraper(BaseScraper):
    """Scraper for Gilles Frozen Custard.

    Gilles publishes its flavor calendar as a weekly graphic (one column per
    day) rather than text/HTML, so today's flavor is read from the image via OCR.
    """

    def __init__(self):
        super().__init__("gilles", "Gilles")

    @staticmethod
    def _parse_month(name):
        for fmt in ("%B", "%b"):
            try:
                return datetime.strptime(name, fmt).month
            except ValueError:
                continue
        return None

    def _find_week_image_url(self, html, today):
        """Find the weekly calendar image covering today, plus its day range."""
        for img in html.find_all("img"):
            src = img.get("src") or ""
            filename = src.rsplit("/", 1)[-1]
            match = WEEK_IMAGE_PATTERN.match(filename)
            if not match:
                continue
            month_name, start_day, end_day = match.groups()
            if self._parse_month(month_name) != today.month:
                continue
            start_day, end_day = int(start_day), int(end_day)
            if not (start_day <= today.day <= end_day):
                continue
            original = WIX_ORIGINAL_IMAGE_PATTERN.search(src)
            if original:
                return original.group(1), start_day, end_day
        return None, None, None

    def _download_image(self, url):
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGB")

    @staticmethod
    def _crop_day_column(image, day, start_day, end_day):
        """Crop out the column for `day` from the evenly divided week graphic."""
        ncols = end_day - start_day + 1
        col_index = day - start_day
        width, height = image.size
        col_width = width / ncols
        left = int(col_index * col_width)
        right = int((col_index + 1) * col_width)
        return image.crop((left, 0, right, height))

    @staticmethod
    def _clean_block(text):
        """Drop leading OCR noise tokens picked up from the photo above the name."""
        words = text.split()
        while len(words) > 1 and not words[0][0].isupper():
            words.pop(0)
        return " ".join(words)

    def _parse_day_column(self, column_image):
        """OCR a day's column, returning (flavor_name, description)."""
        raw_text = pytesseract.image_to_string(column_image)
        # Blank lines separate the day number/photo, flavor name, and description.
        paragraphs = re.split(r"\n\s*\n", raw_text)
        blocks = []
        for paragraph in paragraphs:
            joined = " ".join(line.strip() for line in paragraph.splitlines() if line.strip())
            if joined:
                blocks.append(joined)
        if not blocks:
            return None, ""
        name = self._clean_block(blocks[0])
        description = re.sub(r"^contains:?\s*", "", " ".join(blocks[1:]), flags=re.IGNORECASE)
        return name, description.strip()

    def scrape(self):
        """Scrape Gilles Frozen Custard's weekly flavor calendar graphic via OCR."""
        self.log_start()

        if not self.locations:
            self.log_error("No locations found")
            return []

        location = self.locations[0]
        location_name = location.get("name", "Gilles Frozen Custard")
        scrape_url = location.get("url")

        if not scrape_url:
            self.log_error("No URL found")
            return []

        try:
            self.log_location(location_name, scrape_url)
            html = self.get_html(scrape_url)
            if not html:
                self.log_error("Failed to get HTML")
                return []

            today = get_central_time()
            image_url, start_day, end_day = self._find_week_image_url(html, today)
            if not image_url:
                self.logger.warning("⚠️ GILLES: Could not find this week's calendar image")
                return []

            column_image = self._crop_day_column(
                self._download_image(image_url), today.day, start_day, end_day
            )
            flavor_name, description = self._parse_day_column(column_image)

            if not flavor_name:
                self.logger.warning(
                    "⚠️ GILLES: Could not read today's flavor from the calendar image"
                )
                return []

            if "closed" in flavor_name.lower():
                self.logger.info("🍨 GILLES: Today is closed")
                flavor_entry = self.create_flavor(location_name, "Closed", "", None, url=scrape_url)
            else:
                self.logger.info(f"🍨 GILLES: Found flavor: {flavor_name}")
                flavor_entry = self.create_flavor(
                    location_name, flavor_name, description, None, url=scrape_url
                )

            self.log_complete(1)
            return [flavor_entry]

        except Exception as e:
            self.log_error(f"Failed to scrape: {e}", exc_info=True)
            return []


def scrape_gilles():
    """Scrape Gilles - called by generate_flavors.py."""
    scraper = GillesScraper()
    return scraper.scrape()
