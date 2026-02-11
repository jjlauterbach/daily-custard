import re

from app.scrapers.scraper_base import BaseScraper


class KoppsScraper(BaseScraper):
    """Scraper for Kopp's Frozen Custard locations."""

    def __init__(self):
        super().__init__("kopps")

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
            flavors_section = html.find("div", class_="wp-block-todays-flavors")
            if not flavors_section:
                self.logger.warning("⚠️ KOPPS: Could not find wp-block-todays-flavors section")
                return []

            # Extract the date from the h2 inside the flavors section
            date_str = None
            heading = flavors_section.find("h2")
            if heading and heading.text:
                match = re.search(
                    r"TODAY[''`sS]* FLAVORS\s*[–-]\s*(.+)", heading.text, re.IGNORECASE
                )
                if match:
                    date_str = match.group(1).strip()
                    self.logger.info(f"📅 KOPPS: Found date: {date_str}")

            # Find all h3 tags in the flavors_section
            h3_elements = flavors_section.find_all("h3")
            flavors = []
            for h3 in h3_elements:
                flavor_name = h3.get_text(strip=True)
                # Skip section headers
                if any(
                    skip in flavor_name.lower()
                    for skip in ["shake of the month", "sundae of the month"]
                ):
                    continue

                description = ""
                # Look for the next sibling <p> as the description
                p_tag = h3.find_next_sibling()
                while p_tag and p_tag.name != "p" and p_tag.name is not None:
                    p_tag = p_tag.find_next_sibling()
                if p_tag and p_tag.name == "p":
                    desc_text = p_tag.get_text().strip() if p_tag.get_text() else ""
                    if desc_text and len(desc_text) > 5:
                        description = desc_text

                if flavor_name and len(flavor_name) > 2:
                    self.logger.info(f"🍨 KOPPS: Found flavor: {flavor_name}")
                    # Create entry for each location with this flavor
                    for location in self.get_all_locations():
                        location_name = location.get("name", "Kopps")
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


def scrape_kopps():
    """Scrape Kopp's - called by generate_flavors.py."""
    scraper = KoppsScraper()
    return scraper.scrape()
