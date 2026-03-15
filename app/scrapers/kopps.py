import re

from app.scrapers.scraper_base import BaseScraper


class KoppsScraper(BaseScraper):
    """Scraper for Kopp's Frozen Custard locations."""

    def __init__(self):
        super().__init__("kopps", "Kopp's")

    def scrape(self):
        """Scrape Kopp's Frozen Custard."""
        self.log_start()
        # Kopps has the same flavor for all locations, so scrape once
        scrape_url = self.get_location_url(0)
        if not scrape_url:
            self.log_error("No Kopp's URL found")
            return []

        try:
            html = self.get_html(scrape_url)
            if not html:
                self.log_error("Could not retrieve HTML")
                return []

            date_str, flavor_rows = self._extract_flavors(html)
            if not flavor_rows:
                self.logger.warning("⚠️ KOPPS: Could not extract flavors from page")
                return []

            flavors = []
            for flavor_name, description in flavor_rows:
                self.logger.info(f"🍨 KOPPS: Found flavor: {flavor_name}")
                for location in self.get_all_locations():
                    location_name = location.get("name", self.brand)
                    location_url = location.get("url")
                    flavor_entry = self.create_flavor(
                        location_name,
                        flavor_name,
                        description or "",
                        date_str,
                        url=location_url,
                    )
                    flavors.append(flavor_entry)

            self.log_complete(len(flavors))
            return flavors
        except Exception as e:
            self.log_error(f"Failed to scrape: {e}", exc_info=True)
            return []

    def _extract_flavors(self, html):
        """Extract (date, flavors) from the page with resilient fallbacks."""
        date_str, flavor_rows = self._extract_flavors_from_section(html)
        if flavor_rows:
            return date_str, flavor_rows

        self.logger.warning(
            "⚠️ KOPPS: No flavors extracted from primary section "
            "(section missing or no valid flavor headings); trying heading-based fallback"
        )
        return self._extract_flavors_from_headings(html)

    def _extract_flavors_from_section(self, html):
        """Extract flavors from the original wp-block-todays-flavors section."""
        flavors_section = html.find("div", class_="wp-block-todays-flavors")
        if not flavors_section:
            return None, []

        heading = flavors_section.find(re.compile(r"^h[1-6]$"))
        date_str = self._extract_date_from_heading(
            heading.get_text(" ", strip=True) if heading else ""
        )
        if date_str:
            self.logger.info(f"📅 KOPPS: Found date: {date_str}")

        flavor_rows = []
        for heading_tag in flavors_section.find_all("h3"):
            flavor_name = heading_tag.get_text(strip=True)
            if not self._is_valid_flavor_name(flavor_name):
                continue

            description = ""
            sibling = heading_tag.find_next_sibling()
            if sibling and sibling.name == "p":
                desc_text = sibling.get_text(strip=True) if sibling.get_text() else ""
                if len(desc_text) > 5:
                    description = desc_text

            flavor_rows.append((flavor_name, description))

        return date_str, flavor_rows

    def _extract_flavors_from_headings(self, html):
        """Extract flavors by traversing heading order when section classes are missing."""
        heading_tags = html.find_all(re.compile(r"^h[1-6]$"))
        if not heading_tags:
            return None, []

        start_index = None
        date_str = None
        for idx, heading_tag in enumerate(heading_tags):
            heading_text = heading_tag.get_text(" ", strip=True)
            normalized = heading_text.lower()
            if "today" in normalized and "flavor" in normalized:
                start_index = idx
                date_str = self._extract_date_from_heading(heading_text)
                if date_str:
                    self.logger.info(f"📅 KOPPS: Found date: {date_str}")
                break

        if start_index is None:
            return None, []

        stop_markers = [
            "shake of the month",
            "sundae of the month",
            "keep tabs on your top flavors",
            "need a side of fries",
            "stay connected",
            "nothing beats the gift",
        ]

        flavor_rows = []
        seen_flavors = set()
        for heading_tag in heading_tags[start_index + 1 :]:
            heading_text = heading_tag.get_text(" ", strip=True)
            normalized = heading_text.lower()

            if any(marker in normalized for marker in stop_markers):
                break

            if self._is_valid_flavor_name(heading_text):
                flavor_key = heading_text.lower()
                if flavor_key in seen_flavors:
                    continue
                seen_flavors.add(flavor_key)
                flavor_rows.append((heading_text, ""))

        return date_str, flavor_rows

    def _extract_date_from_heading(self, heading_text):
        """Extract date text from a 'TODAY'S FLAVORS - ...' heading."""
        if not heading_text:
            return None

        normalized = heading_text.replace("’", "'").replace("`", "'")
        match = re.search(
            r"TODAY'?S\s+FLAVORS?\s*[–—\-:]?\s*(.+)",
            normalized,
            re.IGNORECASE,
        )
        if not match:
            return None

        date_str = match.group(1).strip(" -–—")
        return date_str or None

    def _is_valid_flavor_name(self, flavor_name):
        """Return True when heading text appears to be a real flavor name."""
        if not flavor_name:
            return False

        normalized = flavor_name.strip().replace("’", "'").replace("`", "'")
        if len(normalized) < 3:
            return False

        blocked_phrases = [
            "today's flavors",
            "shake of the month",
            "sundae of the month",
            "flavor preview",
            "find your flavor",
            "greenfield",
            "brookfield",
            "glendale",
            "order now",
        ]
        normalized_lower = normalized.lower()
        if any(phrase in normalized_lower for phrase in blocked_phrases):
            return False

        return bool(re.match(r"^[A-Za-z0-9&'’\-\s]+$", normalized))


def scrape_kopps():
    """Scrape Kopp's - called by generate_flavors.py."""
    scraper = KoppsScraper()
    return scraper.scrape()
