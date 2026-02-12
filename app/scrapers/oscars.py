import re
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.scrapers.scraper_base import BaseScraper
from app.scrapers.utils import get_central_date_string, get_central_time

SELENIUM_WAIT_TIMEOUT = 10


class OscarsScraper(BaseScraper):
    """Scraper for Oscar's Frozen Custard."""

    def __init__(self):
        super().__init__("oscars")

    def scrape(self):
        """Scrape Oscar's Frozen Custard."""
        self.log_start()
        chrome_options = self._get_chrome_options()
        driver = None
        try:
            try:
                driver = webdriver.Chrome(options=chrome_options)
            except Exception:
                service = Service("/usr/local/bin/chromedriver")
                driver = webdriver.Chrome(service=service, options=chrome_options)

            location = self.locations[0]
            location_name = location.get("name", "Oscar's Frozen Custard")
            location_url = location.get("url")

            self.log_location(location_name)

            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": 'Object.defineProperty(navigator, "webdriver", {get: () => undefined});'
                },
            )
            driver.set_window_size(1920, 1080)
            driver.get(location_url)
            WebDriverWait(driver, SELENIUM_WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)

            today = get_central_time()
            today_day = today.day
            today_weekday = today.strftime("%a")

            # Use starts-with to handle different day abbreviations, then filter in Python for precision
            calendar_xpath = (
                f"//table//tr[td[starts-with(normalize-space(text()), '{today_weekday}')]]"
            )
            today_display = f"{today_weekday}* {today_day}"

            all_candidate_rows = driver.find_elements(By.XPATH, calendar_xpath)
            calendar_rows = []

            # Filter rows to find exact day match (avoid false positives like "Thu 1" matching day "10")
            for row in all_candidate_rows:
                row_text = row.text.strip()
                # Check if the row contains the exact day pattern
                day_pattern = rf"{today_weekday}\w*\s+\b{today_day}\b"
                if re.search(day_pattern, row_text):
                    calendar_rows.append(row)
                    self.logger.info(f"OSCARS: Found matching row: '{row_text}'")

            if not calendar_rows:
                self.logger.warning(f"OSCARS: Could not find calendar row for {today_display}")
                driver.quit()
                return []

            row = calendar_rows[0]

            # Find all flavor links for today (there might be multiple flavors separated by "or")
            flavor_links = []

            # First, collect all links in the row
            for link in row.find_elements(By.TAG_NAME, "a"):
                if link.is_displayed():
                    flavor_links.append(link)

            # Look for the flavor text in table cells
            cells = row.find_elements(By.TAG_NAME, "td")
            full_flavor_text = ""
            flavor_cell = None
            self.logger.info(f"OSCARS: Found {len(cells)} cells in the row")

            for i, cell in enumerate(cells):
                cell_text = cell.text.strip()
                cell_html = cell.get_attribute("innerHTML")
                self.logger.info(f"OSCARS: Cell {i} text: '{cell_text}'")
                self.logger.info(f"OSCARS: Cell {i} HTML: {cell_html}")

                # Select the first cell that contains non-empty text or any links
                has_text = bool(cell_text)
                has_links = bool(cell.find_elements(By.TAG_NAME, "a"))
                if has_text or has_links:
                    full_flavor_text = cell_text
                    flavor_cell = cell
                    self.logger.info(f"OSCARS: Selected flavor cell text: '{cell_text}'")
                    break

            # If we found a flavor cell, get all the links from that specific cell
            if flavor_cell:
                cell_links = flavor_cell.find_elements(By.TAG_NAME, "a")
                if cell_links:
                    flavor_links = cell_links  # Use links from the flavor cell only
                    self.logger.info(
                        f"OSCARS: Found {len(flavor_links)} flavor links in the flavor cell"
                    )
                    for i, link in enumerate(flavor_links):
                        self.logger.info(f"OSCARS: Flavor link {i}: '{link.text.strip()}'")

            # If we didn't find it in cells, use the first link text as fallback
            if not full_flavor_text and flavor_links:
                full_flavor_text = flavor_links[0].text.strip()

            if not full_flavor_text:
                self.logger.warning("OSCARS: Could not find any flavor text for today")
                driver.quit()
                return []

            self.logger.info(f"OSCARS: Processing flavor text: {full_flavor_text}")

            flavors = []

            # Check if there are multiple flavors separated by "-or-"
            has_or_text = "-OR-" in full_flavor_text.upper() or " OR " in full_flavor_text.upper()
            has_multiple_links = len(flavor_links) > 1
            self.logger.info(f"OSCARS: Has '-or-' text: {has_or_text}")
            self.logger.info(
                f"OSCARS: Has multiple links: {has_multiple_links} (count: {len(flavor_links)})"
            )

            if has_or_text or has_multiple_links:
                # We have multiple flavors - extract individual flavor names from the links
                flavor_names = []
                for link in flavor_links:
                    flavor_name = link.text.strip()
                    if flavor_name:
                        flavor_names.append(flavor_name)

                # Fallback: if no individual links found, split the text
                if not flavor_names:
                    normalized_flavor_text = full_flavor_text.lower()
                    if "-or-" in normalized_flavor_text:
                        flavor_names = [
                            name.strip() for name in normalized_flavor_text.split("-or-")
                        ]
                    else:
                        flavor_names = [
                            name.strip() for name in normalized_flavor_text.split(" or ")
                        ]

                self.logger.info(f"OSCARS: Found multiple flavors: {flavor_names}")

                # Process each flavor by clicking its specific link
                for i, flavor_name in enumerate(flavor_names):
                    flavor_index = i + 1
                    if i < len(flavor_links):
                        try:
                            self.logger.info(
                                f"OSCARS: Clicking link {flavor_index} for flavor: {flavor_name}"
                            )
                            driver.execute_script("arguments[0].click();", flavor_links[i])
                            time.sleep(1)
                            flavor_data = _extract_flavor_from_modal(
                                driver,
                                flavor_name,
                                location_name,
                                location_url,
                                self.logger,
                            )
                            if flavor_data:
                                flavors.append(flavor_data)
                            _close_modal(driver, self.logger)
                        except Exception as e:
                            self.logger.warning(
                                f"OSCARS: Failed to process flavor {flavor_name}: {e}"
                            )
                            # Fallback: create basic flavor entry
                            flavors.append(
                                self.create_flavor(
                                    location_name,
                                    flavor_name,
                                    "",
                                    get_central_date_string(),
                                    url=location_url,
                                )
                            )
                    else:
                        # No corresponding link, create basic flavor entry
                        flavors.append(
                            self.create_flavor(
                                location_name,
                                flavor_name,
                                "",
                                get_central_date_string(),
                                url=location_url,
                            )
                        )
            else:
                # Single flavor - use existing logic
                if not flavor_links:
                    self.logger.warning("OSCARS: No clickable links found for single flavor")
                    driver.quit()
                    return []

                flavor_link = flavor_links[0]
                expected_flavor = full_flavor_text  # Use the full text we found
                self.logger.info(f"OSCARS: Clicking single flavor link: {expected_flavor}")
                driver.execute_script("arguments[0].click();", flavor_link)
                time.sleep(1)
                flavor_data = _extract_flavor_from_modal(
                    driver,
                    expected_flavor,
                    location_name,
                    location_url,
                    self.logger,
                )
                if flavor_data:
                    flavors.append(flavor_data)

            driver.quit()

            for flavor in flavors:
                self.logger.info(f"OSCARS: Flavor: {flavor['flavor']}")
                self.logger.info(f"OSCARS: Description: {flavor['description']}")

            # Oscar's has the same flavors at all locations, so duplicate for each location
            final_flavors = []
            for location in self.get_all_locations():
                for flavor in flavors:
                    location_flavor = self.create_flavor(
                        location.get("name"),
                        flavor["flavor"],
                        flavor.get("description", ""),
                        flavor.get("date"),
                        url=location.get("url"),
                        location_id=location.get("id"),
                        lat=location.get("lat"),
                        lng=location.get("lng"),
                        address=location.get("address"),
                    )
                    final_flavors.append(location_flavor)

            self.log_complete(len(final_flavors))
            return final_flavors

        except Exception as e:
            self.log_error(f"Failed to scrape: {e}", exc_info=True)
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
            return []


def _extract_flavor_from_modal(driver, expected_flavor, location_name, location_url, logger):
    """Extract flavor information from the modal."""
    try:
        overlay = None
        overlays = driver.find_elements(By.XPATH, "//*[contains(@class, 'divioverlay-open')]")
        for o in overlays:
            if o.is_displayed():
                overlay = o
                break

        if not overlay:
            logger.warning("OSCARS: Could not find open overlay/modal after click")
            return None

        overlay_html = overlay.get_attribute("innerHTML")
        soup = BeautifulSoup(overlay_html, "html.parser")
        flavor_tag = soup.find("h4")
        flavor_name = flavor_tag.get_text(strip=True) if flavor_tag else expected_flavor
        description = ""

        if flavor_tag:
            next_tag = flavor_tag.find_next(["span", "div", "p"])
            while next_tag:
                desc_text = next_tag.get_text(strip=True)
                if desc_text and len(desc_text) > 10 and desc_text.upper() != flavor_name.upper():
                    description = desc_text
                    break
                next_tag = next_tag.find_next(["span", "div", "p"])

        if not description:
            desc_candidates = []
            for tag in soup.find_all(["span", "div", "p"]):
                t = tag.get_text(strip=True)
                if t and len(t) > 10 and t.upper() != flavor_name.upper():
                    desc_candidates.append(t)
            if desc_candidates:
                description = max(desc_candidates, key=len)

        return {
            "location_name": location_name,
            "flavor": flavor_name,
            "description": description,
            "date": get_central_date_string(),
            "url": location_url,
        }
    except Exception as e:
        logger.warning(f"OSCARS: Failed to extract flavor from modal: {e}")
        return None


def _close_modal(driver, logger):
    """Close the modal/overlay."""
    try:
        # Try to find and click close button
        close_buttons = driver.find_elements(
            By.XPATH, "//*[contains(@class, 'close') or contains(@class, 'divioverlay-close')]"
        )
        for btn in close_buttons:
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1)
                return

        # Fallback: press Escape key
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(1)
    except Exception as e:
        logger.warning(f"OSCARS: Failed to close modal: {e}")


def scrape_oscars():
    """Scrape Oscar's - called by generate_flavors.py."""
    scraper = OscarsScraper()
    return scraper.scrape()
