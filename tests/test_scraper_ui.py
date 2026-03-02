import time
import unittest

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


class TestScraperUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        cls.driver = webdriver.Chrome(options=options)
        cls.driver.set_window_size(1200, 900)
        # Change this URL if your app runs on a different port or path
        cls.url = "http://localhost:8080/"

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def test_flavor_cards_present(self):
        self.driver.get(self.url)
        # Wait for JS to load flavors (increase if your backend is slow)
        time.sleep(5)
        # Check for location cards (new UI) OR flavor cards (fallback check)
        cards = self.driver.find_elements(By.CLASS_NAME, "location-card")
        self.assertGreater(len(cards), 0, "No location cards found on the page")
        for card in cards:
            name = card.find_element(By.CLASS_NAME, "flavor-name").text
            self.assertTrue(name and len(name) > 1, "Flavor name missing or too short")
            desc = card.find_element(By.CLASS_NAME, "flavor-description").text
            self.assertTrue(desc is not None, "Flavor description missing")

    def test_stale_brand_in_localstorage_shows_all_locations(self):
        """Regression: a brand removed from the site should not cause zero locations to display.

        If a user's localStorage contains only a brand_id that no longer exists,
        loadSavedBrands() and pruneSavedBrands() must fall back to 'all' so that
        every location card is still shown.
        """
        # Navigate first so we're on the correct origin
        self.driver.get(self.url)
        time.sleep(2)

        # Capture the baseline card count with default (all) brands selected
        self.driver.execute_script("localStorage.removeItem('selectedBrands');")
        self.driver.refresh()
        time.sleep(5)
        baseline_cards = self.driver.find_elements(By.CLASS_NAME, "location-card")
        baseline_count = len(baseline_cards)
        self.assertGreater(baseline_count, 0, "Baseline: no location cards found")

        # Inject a stale brand that no longer exists into localStorage
        self.driver.execute_script(
            "localStorage.setItem('selectedBrands', JSON.stringify(['removed_brand']));"
        )

        # Reload the page; loadSavedBrands + pruneSavedBrands should prune the stale entry
        self.driver.refresh()
        time.sleep(5)

        cards = self.driver.find_elements(By.CLASS_NAME, "location-card")
        self.assertGreater(
            len(cards),
            0,
            "Stale localStorage brand caused zero locations to display",
        )
        self.assertEqual(
            len(cards),
            baseline_count,
            "Stale brand should fall back to showing all locations",
        )

    def test_stale_brand_mixed_with_valid_brand_keeps_valid(self):
        """Regression: valid brands should survive when mixed with a stale brand in localStorage.

        Only the stale entry should be stripped; the valid brand_id must remain so
        that only matching locations are shown (not all brands, not zero brands).
        """
        self.driver.get(self.url)
        time.sleep(2)

        # Pick the first available brand_id from the modal checkboxes
        first_brand_id = self.driver.execute_script(
            "const cb = document.querySelector('#modalBrandGrid input[type=checkbox]');"
            "return cb ? cb.value : null;"
        )
        self.assertIsNotNone(first_brand_id, "No brand checkboxes found in modal")

        # Store a mix of a valid brand and a removed brand
        self.driver.execute_script(
            f"localStorage.setItem('selectedBrands', "
            f"JSON.stringify(['removed_brand', '{first_brand_id}']));"
        )

        self.driver.refresh()
        time.sleep(5)

        cards = self.driver.find_elements(By.CLASS_NAME, "location-card")
        self.assertGreater(
            len(cards),
            0,
            "Mixing a stale brand with a valid brand caused zero locations to display",
        )

        # Verify the filter button does not say "All Brands" (the valid brand is still filtered)
        filter_btn_text = self.driver.find_element(By.ID, "openFiltersBtn").text
        self.assertNotIn(
            "All Brands",
            filter_btn_text,
            "Filter should still show a specific brand count, not 'All Brands'",
        )


if __name__ == "__main__":
    unittest.main()
