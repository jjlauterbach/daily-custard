from urllib.parse import urljoin

from app.scrapers.scraper_base import BaseScraper


class GillesScraper(BaseScraper):
    """Scraper for Gilles Frozen Custard."""

    def __init__(self):
        super().__init__("gilles", "Gilles")

    def scrape(self):
        """Scrape Gilles Frozen Custard calendar page."""
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

            # Gilles uses a calendar view
            # Find today's single-day cell
            today_cell = html.find("td", class_="single-day today")
            if not today_cell:
                self.logger.warning("⚠️ GILLES: Could not find today's calendar cell")
                return []

            # Find all flavor divs - there are two types:
            # 1. Flavor of the day
            # 2. Flavor of the month
            flavor_divs = today_cell.find_all("div", class_="flavor")
            flavors = []

            for div in flavor_divs:
                div_text = div.get_text(strip=True)

                if "Flavor of the day:" in div_text or "Flavor of the month:" in div_text:
                    # Navigate up to the 'contents' container (3 levels up)
                    contents_div = div.parent.parent.parent

                    # Find the title field which contains the flavor link
                    title_div = contents_div.find("div", class_="views-field-title")
                    if title_div:
                        flavor_link = title_div.find("a", href=lambda x: x and "/flavor/" in x)
                        if flavor_link:
                            flavor_name = flavor_link.text.strip()
                            if flavor_name:
                                # Short-circuit if the link represents a closed day to avoid
                                # unnecessary detail page fetches that are likely to 404.
                                if flavor_name.lower() == "closed":
                                    self.logger.info("🍨 GILLES: Today is closed (link)")
                                    flavor_entry = self.create_flavor(
                                        location_name,
                                        "Closed",
                                        "",
                                        None,
                                        url=scrape_url,
                                    )
                                    flavors.append(flavor_entry)
                                    # Skip description fetching for closed days
                                    continue

                                # Extract flavor description from detail page
                                flavor_href = flavor_link.get("href", "")
                                description = ""

                                if flavor_href:
                                    # Construct full URL for flavor detail page
                                    flavor_url = urljoin(scrape_url, flavor_href)

                                    try:
                                        flavor_html = self.get_html(flavor_url)
                                        if flavor_html:
                                            # Look for description in common locations
                                            desc_div = flavor_html.find(
                                                "div", class_="field-name-body"
                                            )
                                            if desc_div:
                                                desc_content = desc_div.find(
                                                    "div", class_="field-item"
                                                )
                                                if desc_content:
                                                    description = desc_content.get_text(strip=True)
                                    except Exception as e:
                                        self.logger.warning(
                                            f"⚠️ GILLES: Could not fetch description for {flavor_name}: {e}"
                                        )

                                self.logger.info(f"🍨 GILLES: Found flavor: {flavor_name}")
                                flavor_entry = self.create_flavor(
                                    location_name,
                                    flavor_name,
                                    description,
                                    None,
                                    url=scrape_url,
                                )
                                flavors.append(flavor_entry)

            if not flavors:
                # Check if today's cell contains "Closed" text (no flavor links found)
                today_cell_text = today_cell.get_text(strip=True)
                if "closed" in today_cell_text.lower():
                    self.logger.info("🍨 GILLES: Today is closed")
                    flavor_entry = self.create_flavor(
                        location_name,
                        "Closed",
                        "",
                        None,
                        url=scrape_url,
                    )
                    flavors.append(flavor_entry)
                else:
                    self.logger.warning("⚠️ GILLES: No flavors found in today's cell")

            self.log_complete(len(flavors))
            return flavors

        except Exception as e:
            self.log_error(f"Failed to scrape: {e}", exc_info=True)
            return []


def scrape_gilles():
    """Scrape Gilles - called by generate_flavors.py."""
    scraper = GillesScraper()
    return scraper.scrape()
