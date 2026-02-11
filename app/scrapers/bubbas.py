from datetime import datetime, timedelta

import requests

from app.scrapers.scraper_base import BaseScraper
from app.scrapers.utils import get_central_date_string

BUBBAS_SECTION_ID = 1332549


class BubbasScraper(BaseScraper):
    """Scraper for Bubba's Frozen Custard via GraphQL API."""

    def __init__(self):
        super().__init__("bubbas")

    def scrape(self):
        """Scrape Bubba's using their GraphQL API."""
        self.log_start()
        try:
            location = self.locations[0]
            location_name = location.get("name", "Bubbas")
            location_url = location.get("url")

            self.log_location(location_name)

            base_url = location_url.rstrip("/")
            graphql_endpoint = f"{base_url}/graphql"

            today_str = get_central_date_string()
            today_dt = datetime.strptime(today_str, "%Y-%m-%d")

            # Query a range that includes today
            range_start = today_dt - timedelta(days=1)
            range_end = today_dt + timedelta(days=2)

            payload = {
                "operationName": "customPageCalendarSection",
                "variables": {
                    "rangeEndAt": range_end.strftime("%Y-%m-%dT05:00:00.000Z"),
                    "rangeStartAt": range_start.strftime("%Y-%m-%dT05:00:00.000Z"),
                    "limit": None,
                    "sectionId": BUBBAS_SECTION_ID,
                },
                "extensions": {"operationId": "PopmenuClient/84a8c72179c517e7d584420f7a69a194"},
            }

            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "cache-control": "no-cache",
                "content-type": "application/json",
                "dnt": "1",
                "origin": base_url,
                "pragma": "no-cache",
                "referer": f"{base_url}/events",
                "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            }

            # NOTE: You must update this cookie string regularly or automate retrieval
            cookies = {}

            resp = requests.post(
                graphql_endpoint, json=payload, headers=headers, cookies=cookies, timeout=10
            )
            resp.raise_for_status()
            data = resp.json()

            events = (
                data.get("data", {}).get("customPageSection", {}).get("upcomingCalendarEvents", [])
            )
            self.logger.debug(f"BUBBAS: Found {len(events)} events")

            for event in events:
                event_date = event.get("startAt")
                if event_date == today_str:
                    flavor = event.get("name", "")
                    description = event.get("description", "")
                    date_str = event_date
                    url = base_url + event.get("calendarEventPageUrl", "/")
                    self.logger.info(f"🍨 BUBBAS: {flavor} ({date_str})")

                    flavor_entry = self.create_flavor(
                        location_name,
                        flavor,
                        description,
                        date_str,
                        url=url,
                    )
                    self.log_complete(1)
                    return [flavor_entry]

            self.logger.warning("BUBBAS: No flavor found for today.")
            return []

        except Exception as e:
            self.log_error(f"Failed to scrape: {e}", exc_info=True)
            return []


def scrape_bubbas():
    """Scrape Bubba's - called by generate_flavors.py."""
    scraper = BubbasScraper()
    return scraper.scrape()
