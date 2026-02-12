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


if __name__ == "__main__":
    unittest.main()
