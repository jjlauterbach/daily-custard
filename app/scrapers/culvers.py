from app.scrapers.scraper_base import BaseScraper


class CulversScraper(BaseScraper):
    """Scraper for Culver's locations using the locator API."""

    API_URL = "https://www.culvers.com/api/locator/getLocations?lat=43.07970271852549&long=-88.22235303770586&radius=600000&limit=100"

    def __init__(self):
        super().__init__("culvers")

    def scrape(self):
        """Scrape all Culver's locations from the API."""
        self.log_start()
        flavors = []

        try:
            response = self.session.get(self.API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            geofences = data.get("data", {}).get("geofences", [])
            self.logger.info(f"Found {len(geofences)} locations in Culver's API response")

            for location in geofences:
                try:
                    metadata = location.get("metadata", {})
                    flavor_name = metadata.get("flavorOfDayName")

                    if not flavor_name:
                        continue

                    # Extract location details
                    slug = metadata.get("slug")
                    city = metadata.get("city")
                    state = metadata.get("state")

                    # Generate ID consistent with our format: culvers-<slug>
                    location_id = f"culvers-{slug}"

                    # Name formatting: "Culver's (City - Street)" or similar
                    # The API has "description": "Brookfield, WI - W Capitol Dr"
                    description_raw = location.get("description", "")
                    location_name = f"Culver's ({description_raw})"

                    flavor_description = metadata.get("flavorOfTheDayDescription")

                    # Address construction
                    street = metadata.get("street")
                    postal_code = metadata.get("postalCode")
                    address = f"{street}, {city}, {state} {postal_code}"

                    # Coordinates
                    # geometryCenter -> coordinates: [lng, lat]
                    geo_center = location.get("geometryCenter", {}).get("coordinates", [])
                    lng = geo_center[0] if len(geo_center) > 0 else None
                    lat = geo_center[1] if len(geo_center) > 1 else None

                    # URL construction
                    # https://www.culvers.com/restaurants/brookfield-capitol
                    url = f"https://www.culvers.com/restaurants/{slug}"

                    # Create Flavor Entry
                    # We pass the scraped location data directly instead of relying on locations.yaml
                    flavor_entry = self.create_flavor(
                        location_name,
                        flavor_name,
                        description=flavor_description,
                        date=None,  # Defaults to today
                        url=url,
                        location_id=location_id,
                        lat=lat,
                        lng=lng,
                        address=address,
                    )

                    flavors.append(flavor_entry)

                except Exception as e:
                    self.log_error(
                        f"Error processing location {location.get('description', 'Unknown')}: {e}"
                    )

        except Exception as e:
            self.log_error(f"Failed to fetch from API: {e}")

        self.log_complete(len(flavors))
        return flavors

    def _scrape_location(self, url):
        """Deprecated: Individual page scraping."""


def scrape_culvers():
    """Scrape Culver's - called by generate_flavors.py."""
    scraper = CulversScraper()
    return scraper.scrape()
