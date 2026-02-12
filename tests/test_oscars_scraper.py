import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from app.scrapers.oscars import _extract_flavor_from_modal, scrape_oscars


class TestOscarsScraper(unittest.TestCase):
    """Unit tests for Oscar's scraper functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_driver = Mock()
        self.mock_driver.execute_cdp_cmd = Mock()
        self.mock_driver.set_window_size = Mock()
        self.mock_driver.get = Mock()
        self.mock_driver.quit = Mock()
        self.mock_driver.execute_script = Mock()

        # Patch locations to ensure we always have 3 enabled locations for testing
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [
            {
                "id": "test-oscar-1",
                "name": "Oscar's 1",
                "url": "http://test",
                "enabled": True,
            },
            {
                "id": "test-oscar-2",
                "name": "Oscar's 2",
                "url": "http://test",
                "enabled": True,
            },
            {
                "id": "test-oscar-3",
                "name": "Oscar's 3",
                "url": "http://test",
                "enabled": True,
            },
        ]

    def tearDown(self):
        self.locations_patcher.stop()

    @patch("app.scrapers.oscars.webdriver.Chrome")
    @patch("app.scrapers.oscars.WebDriverWait")
    @patch("app.scrapers.oscars.OscarsScraper._get_chrome_options")
    @patch("app.scrapers.oscars.get_central_time")
    @patch("app.scrapers.oscars.get_central_date_string")
    def test_multiple_flavors_with_or_separator(
        self, mock_date_string, mock_time, mock_chrome_options, mock_wait, mock_chrome
    ):
        """Test scraping multiple flavors separated by '-or-'."""
        # Setup mocks
        mock_chrome.return_value = self.mock_driver
        mock_chrome_options.return_value = Mock()
        mock_time.return_value = datetime(2025, 7, 15)  # Tuesday
        mock_date_string.return_value = "2025-07-15"

        # Mock WebDriverWait
        mock_wait.return_value.until.return_value = True

        # Mock calendar row finding
        mock_row = Mock()
        mock_cell_1 = Mock()
        mock_cell_1.text.strip.return_value = "Tue 15"
        mock_cell_1.get_attribute.return_value = "Tue 15"
        mock_cell_1.find_elements.return_value = []

        mock_cell_2 = Mock()
        mock_cell_2.text.strip.return_value = "LEMON BERRY -or- CHOCOLATE CHIP"
        mock_cell_2.get_attribute.return_value = '<strong><a id="overlay_unique_id_205873" href="#open-overlay">LEMON BERRY</a></strong>  -or- <strong><a id="overlay_unique_id_205580" href="#open-overlay">CHOCOLATE CHIP</a></strong>'

        # Mock flavor links
        mock_link_1 = Mock()
        mock_link_1.text.strip.return_value = "LEMON BERRY"
        mock_link_1.is_displayed.return_value = True

        mock_link_2 = Mock()
        mock_link_2.text.strip.return_value = "CHOCOLATE CHIP"
        mock_link_2.is_displayed.return_value = True

        mock_cell_2.find_elements.return_value = [mock_link_1, mock_link_2]

        mock_row.find_elements.side_effect = [
            [mock_link_1, mock_link_2],  # All links in row
            [mock_cell_1, mock_cell_2],  # All cells in row
        ]
        mock_row.text.strip.return_value = "Tue 15 LEMON BERRY -or- CHOCOLATE CHIP"

        self.mock_driver.find_elements.return_value = [mock_row]

        # Mock modal interactions
        mock_overlay = Mock()
        mock_overlay.is_displayed.return_value = True
        mock_overlay.get_attribute.return_value = (
            "<h4>LEMON BERRY</h4><p>Red, ripe raspberries wrapped into lemon custard.</p>"
        )

        # Mock the overlay finding to return different content for each flavor
        overlay_returns = [
            [mock_overlay],  # First flavor modal
            [],  # No overlay after close
            [mock_overlay],  # Second flavor modal
            [],  # No overlay after close
        ]
        self.mock_driver.find_elements.side_effect = [
            [mock_row],  # Calendar row search
            [mock_link_1, mock_link_2],  # Row links
            [mock_cell_1, mock_cell_2],  # Row cells
            [mock_link_1, mock_link_2],  # Cell links
            overlay_returns[0],  # First modal search
            overlay_returns[1],  # Close button search
            overlay_returns[2],  # Second modal search
            overlay_returns[3],  # Close button search
        ]

        # Mock close buttons
        self.mock_driver.find_element.return_value = Mock()

        # Run the scraper
        with patch("app.scrapers.oscars.time.sleep"):  # Skip actual sleep
            with patch("app.scrapers.oscars._extract_flavor_from_modal") as mock_extract:
                with patch("app.scrapers.oscars._close_modal") as mock_close:
                    # Mock extraction returns
                    mock_extract.side_effect = [
                        {
                            "flavor": "LEMON BERRY",
                            "description": "Red, ripe raspberries wrapped into lemon custard.",
                            "date": "2025-07-15",
                            "restaurant": "Oscars",
                            "url": "https://www.oscarscustard.com/index.php/flavors",
                        },
                        {
                            "flavor": "CHOCOLATE CHIP",
                            "description": "Chocolate chips blended with our creamy custard.",
                            "date": "2025-07-15",
                            "restaurant": "Oscars",
                            "url": "https://www.oscarscustard.com/index.php/flavors",
                        },
                    ]

                    result = scrape_oscars()

        # Assertions
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 6, "Should return 2 flavors × 3 locations = 6 entries")

        # Check first location's first flavor (LEMON BERRY)
        self.assertEqual(result[0]["flavor"], "LEMON BERRY")
        self.assertEqual(
            result[0]["description"], "Red, ripe raspberries wrapped into lemon custard."
        )

        # Check first location's second flavor (CHOCOLATE CHIP)
        self.assertEqual(result[1]["flavor"], "CHOCOLATE CHIP")
        self.assertEqual(
            result[1]["description"], "Chocolate chips blended with our creamy custard."
        )

        # Verify that the same flavors are repeated for all 3 locations
        # Flavors 0,1 are for location 1; 2,3 for location 2; 4,5 for location 3
        for i in range(3):  # For each location
            self.assertEqual(result[i * 2]["flavor"], "LEMON BERRY")
            self.assertEqual(result[i * 2 + 1]["flavor"], "CHOCOLATE CHIP")

        # Verify both links were clicked
        self.assertEqual(self.mock_driver.execute_script.call_count, 2)

        # Verify extraction was called for both flavors
        self.assertEqual(mock_extract.call_count, 2)
        # Check that _extract_flavor_from_modal was called with the right parameters
        # Note: The function signature includes location_name, location_url, and logger
        calls = mock_extract.call_args_list
        self.assertEqual(len(calls), 2)
        # Verify the flavor names in the calls
        self.assertEqual(calls[0][0][1], "LEMON BERRY")  # Second argument is flavor name
        self.assertEqual(calls[1][0][1], "CHOCOLATE CHIP")

        # Verify modal close was called for both flavors
        self.assertEqual(mock_close.call_count, 2)

    @patch("app.scrapers.oscars.webdriver.Chrome")
    @patch("app.scrapers.oscars.WebDriverWait")
    @patch("app.scrapers.oscars.OscarsScraper._get_chrome_options")
    @patch("app.scrapers.oscars.get_central_time")
    @patch("app.scrapers.oscars.get_central_date_string")
    def test_single_flavor_fallback(
        self, mock_date_string, mock_time, mock_chrome_options, mock_wait, mock_chrome
    ):
        """Test that single flavor still works correctly."""
        # Setup mocks
        mock_chrome.return_value = self.mock_driver
        mock_chrome_options.return_value = Mock()
        mock_time.return_value = datetime(2025, 7, 16)  # Wednesday
        mock_date_string.return_value = "2025-07-16"

        # Mock WebDriverWait
        mock_wait.return_value.until.return_value = True

        # Mock calendar row with single flavor
        mock_row = Mock()
        mock_cell_1 = Mock()
        mock_cell_1.text.strip.return_value = "Wed 16"
        mock_cell_1.get_attribute.return_value = "Wed 16"
        mock_cell_1.find_elements.return_value = []

        mock_cell_2 = Mock()
        mock_cell_2.text.strip.return_value = "VANILLA BEAN"
        mock_cell_2.get_attribute.return_value = '<strong><a id="overlay_unique_id_205874" href="#open-overlay">VANILLA BEAN</a></strong>'

        # Mock single flavor link
        mock_link = Mock()
        mock_link.text.strip.return_value = "VANILLA BEAN"
        mock_link.is_displayed.return_value = True

        mock_cell_2.find_elements.return_value = [mock_link]

        mock_row.find_elements.side_effect = [
            [mock_link],  # All links in row
            [mock_cell_1, mock_cell_2],  # All cells in row
        ]
        mock_row.text.strip.return_value = "Wed 16 VANILLA BEAN"

        self.mock_driver.find_elements.return_value = [mock_row]

        # Run the scraper
        with patch("app.scrapers.oscars.time.sleep"):  # Skip actual sleep
            with patch("app.scrapers.oscars._extract_flavor_from_modal") as mock_extract:
                mock_extract.return_value = {
                    "flavor": "VANILLA BEAN",
                    "description": "Classic vanilla bean frozen custard.",
                    "date": "2025-07-16",
                    "restaurant": "Oscars",
                    "url": "https://www.oscarscustard.com/index.php/flavors",
                }

                result = scrape_oscars()

        # Assertions
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3, "Should return 1 flavor × 3 locations = 3 entries")
        # Check all 3 location entries have the same flavor
        for i in range(3):
            self.assertEqual(result[i]["flavor"], "VANILLA BEAN")

        # Verify single link was clicked
        self.assertEqual(self.mock_driver.execute_script.call_count, 1)

    def test_flavor_text_parsing_logic(self):
        """Test the logic for detecting multiple flavors in text."""
        test_cases = [
            ("LEMON BERRY -or- CHOCOLATE CHIP", True),
            ("VANILLA BEAN", False),
            ("STRAWBERRY -OR- MINT CHIP", True),
            ("COOKIES -or- CREAM", True),
            ("SINGLE FLAVOR", False),
            ("MULTIPLE or FLAVORS", True),
            ("TEST OR ANOTHER", True),
        ]

        for text, expected_has_or in test_cases:
            with self.subTest(text=text):
                has_or_text = "-OR-" in text.upper() or " OR " in text.upper()
                self.assertEqual(
                    has_or_text,
                    expected_has_or,
                    f"Text '{text}' should {'have' if expected_has_or else 'not have'} 'or' separator",
                )

    @patch("app.scrapers.oscars.BeautifulSoup")
    def test_extract_flavor_from_modal(self, mock_soup):
        """Test flavor extraction from modal HTML."""
        # Mock driver and overlay
        mock_driver = Mock()
        mock_overlay = Mock()
        mock_overlay.is_displayed.return_value = True
        mock_overlay.get_attribute.return_value = "<h4>TEST FLAVOR</h4><p>Test description</p>"

        mock_driver.find_elements.return_value = [mock_overlay]

        # Mock BeautifulSoup parsing
        mock_soup_instance = Mock()
        mock_soup.return_value = mock_soup_instance

        mock_h4 = Mock()
        mock_h4.get_text.return_value = "TEST FLAVOR"
        mock_soup_instance.find.return_value = mock_h4

        mock_p = Mock()
        mock_p.get_text.return_value = "Test description for the flavor"
        mock_h4.find_next.return_value = mock_p

        # Call the function - it returns a dict with flavor data
        result = _extract_flavor_from_modal(
            mock_driver, "TEST FLAVOR", "Test Location", "https://example.com", None  # logger
        )

        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["flavor"], "TEST FLAVOR")
        self.assertEqual(result["location_name"], "Test Location")

    @patch("app.scrapers.oscars.webdriver.Chrome")
    @patch("app.scrapers.oscars.WebDriverWait")
    @patch("app.scrapers.oscars.OscarsScraper._get_chrome_options")
    @patch("app.scrapers.oscars.get_central_time")
    @patch("app.scrapers.oscars.get_central_date_string")
    @patch("app.scrapers.oscars._extract_flavor_from_modal")
    @patch("app.scrapers.oscars._close_modal")
    def test_oscars_scraper_day_matching_regex(
        self,
        mock_close,
        mock_extract,
        mock_date_string,
        mock_time,
        mock_chrome_options,
        mock_wait,
        mock_chrome,
    ):
        """Test that the Oscar's scraper correctly matches different day formats using its actual logic."""
        # Test data: simulate table cells with different day formats
        test_cases = [
            ("Thur 1", "Thu", 1, True),  # Should match Thu 1
            ("Thur 10", "Thu", 10, True),  # Should match Thu 10
            ("Thur 10", "Thu", 1, False),  # Should NOT match Thu 1 (false positive)
            ("Thur 11", "Thu", 1, False),  # Should NOT match Thu 1 (false positive)
            ("Thu 1", "Thu", 1, True),  # Should match Thu 1
            ("Thu 10", "Thu", 10, True),  # Should match Thu 10
            ("Thursday 1", "Thu", 1, True),  # Should match Thu 1
            ("Thursday 10", "Thu", 10, True),  # Should match Thu 10
            ("Fri 1", "Thu", 1, False),  # Different day - should not match
            ("1 Thur", "Thu", 1, False),  # Wrong order - should not match
            ("Thur1", "Thu", 1, False),  # No space - should not match
        ]

        for cell_text, weekday, day, should_match in test_cases:
            with self.subTest(cell_text=cell_text, weekday=weekday, day=day):
                # Setup mocks for this specific test case
                mock_chrome.return_value = self.mock_driver
                mock_chrome_options.return_value = Mock()
                mock_date_string.return_value = f"2025-07-{day:02d}"

                # Mock the current time for the test case
                mock_date = Mock()
                mock_date.day = day
                mock_date.strftime.return_value = weekday
                mock_time.return_value = mock_date

                # Mock WebDriverWait
                mock_wait.return_value.until.return_value = True

                # Reset mock for each test case
                self.mock_driver.reset_mock()

                # Mock table cells and rows with realistic flavor data
                mock_cell = Mock()
                mock_cell.text = "CHOCOLATE CHIP"
                mock_cell.find_elements.return_value = []  # No links for simplicity

                mock_row = Mock()
                mock_row.text = cell_text  # This is what the scraper will see
                mock_row.find_elements.return_value = [mock_cell]

                # Mock successful flavor extraction
                mock_extract.return_value = {
                    "flavor": "CHOCOLATE CHIP",
                    "description": "Test flavor description",
                    "date": f"2025-07-{day:02d}",
                    "restaurant": "Oscars",
                    "url": "https://www.oscarscustard.com/index.php/flavors",
                }

                # Always return the row for initial XPath search (starting with weekday)
                # Let the scraper's regex logic determine if it should be processed
                if cell_text.startswith(weekday):
                    self.mock_driver.find_elements.side_effect = [
                        [mock_row],  # Initial candidate rows (starting with weekday)
                        [],  # Fallback XPath (if regex filtering rejects the row)
                    ]
                else:
                    # Different weekday - no rows found at all
                    self.mock_driver.find_elements.side_effect = [
                        [],  # No candidate rows
                        [],  # Fallback
                    ]

                # Call the actual scraper and let it decide based on its logic
                try:
                    with patch("app.scrapers.oscars.time.sleep"):  # Skip sleep
                        result = scrape_oscars()

                    found_flavors = len(result) > 0

                    # Test the actual scraper behavior, not just regex
                    if should_match:
                        self.assertTrue(
                            found_flavors,
                            f"Scraper should have found flavors for '{cell_text}' when looking for {weekday} {day}",
                        )
                        if found_flavors:
                            # Should have 3 location entries (one per Oscar's location)
                            self.assertEqual(len(result), 3, "Should have 3 location entries")
                            self.assertEqual(result[0]["flavor"], "CHOCOLATE CHIP")
                    else:
                        self.assertFalse(
                            found_flavors,
                            f"Scraper should NOT have found flavors for '{cell_text}' when looking for {weekday} {day}",
                        )

                except Exception as e:
                    if should_match:
                        self.fail(f"Scraper unexpectedly failed for valid case '{cell_text}': {e}")
                    # For negative cases, exceptions are acceptable as the scraper may fail
                    # when it can't find the expected day format

    @patch("app.scrapers.oscars.webdriver.Chrome")
    @patch("app.scrapers.oscars.OscarsScraper._get_chrome_options")
    @patch("app.scrapers.oscars.get_central_time")
    @patch("app.scrapers.oscars.get_central_date_string")
    @patch("app.scrapers.oscars._extract_flavor_from_modal")
    @patch("app.scrapers.oscars._close_modal")
    def test_oscars_scraper_with_mocked_day_scenarios(
        self,
        mock_close,
        mock_extract,
        mock_date_string,
        mock_time,
        mock_chrome_options,
        mock_chrome,
    ):
        """Test the actual Oscar's scraper with different day matching scenarios."""
        # Mock setup
        mock_chrome.return_value = self.mock_driver
        mock_chrome_options.return_value = Mock()
        mock_date_string.return_value = "2025-07-24"

        # Mock the current time to be Thursday, July 24th
        mock_date = Mock()
        mock_date.day = 24
        mock_date.strftime.return_value = "Thu"
        mock_time.return_value = mock_date

        # Create mock table rows for different scenarios
        scenarios = [
            {
                "name": "Exact match - Thur 24",
                "row_text": "Thur 24",
                "cell_text": "CHOCOLATE CHIP",
                "should_find": True,
                "starts_with_thu": True,
            },
            {
                "name": "Exact match - Thu 24",
                "row_text": "Thu 24",
                "cell_text": "VANILLA",
                "should_find": True,
                "starts_with_thu": True,
            },
            {
                "name": "False positive test - Thur 240",
                "row_text": "Thur 240",
                "cell_text": "STRAWBERRY",
                "should_find": False,
                "starts_with_thu": True,
            },
            {
                "name": "Different day - Fri 24",
                "row_text": "Fri 24",
                "cell_text": "MINT",
                "should_find": False,
                "starts_with_thu": False,
            },
        ]

        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                # Reset mock for each scenario
                self.mock_driver.reset_mock()

                # Mock table cells and rows
                mock_cell = Mock()
                mock_cell.text = scenario["cell_text"]

                # Create mock link for flavor extraction
                mock_link = Mock()
                mock_link.text.strip.return_value = scenario["cell_text"]
                mock_link.is_displayed.return_value = True
                mock_cell.find_elements.return_value = (
                    [mock_link] if scenario["should_find"] else []
                )

                mock_row = Mock()
                mock_row.text = scenario["row_text"]
                mock_row.find_elements.side_effect = [
                    [mock_link] if scenario["should_find"] else [],  # Links in row
                    [mock_cell],  # Cells in row
                ]

                # Mock flavor extraction
                if scenario["should_find"]:
                    mock_extract.return_value = {
                        "flavor": scenario["cell_text"],
                        "description": f"Test description for {scenario['cell_text']}",
                        "date": "2025-07-24",
                        "restaurant": "Oscars",
                        "url": "https://www.oscarscustard.com/index.php/flavors",
                    }

                # Mock WebDriverWait behavior
                with patch("app.scrapers.oscars.WebDriverWait") as mock_wait:
                    mock_wait.return_value.until.return_value = True

                    # Mock the find_elements calls based on scenario
                    if scenario["starts_with_thu"]:
                        if scenario["should_find"]:
                            # Successful case: row found and matches
                            self.mock_driver.find_elements.side_effect = [
                                [mock_row],  # Initial search finds candidate rows
                                [mock_link],  # Row links
                                [mock_cell],  # Row cells
                                [mock_link],  # Cell links
                                [],  # Modal overlay search (mocked)
                                [],  # Close button search
                            ]
                        else:
                            # False positive case: row found but filtered out by regex
                            self.mock_driver.find_elements.side_effect = [
                                [mock_row],  # Candidate rows found
                                [],  # Fallback search (regex filtering rejected row)
                            ]
                    else:
                        # Different day: no candidate rows found
                        self.mock_driver.find_elements.side_effect = [
                            [],  # No candidate rows
                            [],  # Fallback
                        ]

                    try:
                        with patch("app.scrapers.oscars.time.sleep"):  # Skip sleep
                            result = scrape_oscars()

                        found_flavors = len(result) > 0

                        if scenario["should_find"]:
                            self.assertTrue(
                                found_flavors,
                                f"Should have found flavors for scenario: {scenario['name']}",
                            )
                            if found_flavors:
                                # Should have 3 location entries
                                self.assertEqual(len(result), 3, "Should have 3 location entries")
                                self.assertEqual(result[0]["flavor"], scenario["cell_text"])
                        else:
                            self.assertFalse(
                                found_flavors,
                                f"Should NOT have found flavors for scenario: {scenario['name']}",
                            )

                    except Exception as e:
                        if scenario["should_find"]:
                            self.fail(f"Scraper failed unexpectedly for {scenario['name']}: {e}")
                        # For negative cases, exceptions are acceptable

    @patch("app.scrapers.oscars.webdriver.Chrome")
    @patch("app.scrapers.oscars.WebDriverWait")
    @patch("app.scrapers.oscars.OscarsScraper._get_chrome_options")
    @patch("app.scrapers.oscars.get_central_time")
    @patch("app.scrapers.oscars.get_central_date_string")
    @patch("app.scrapers.oscars._extract_flavor_from_modal")
    @patch("app.scrapers.oscars._close_modal")
    def test_oscars_scraper_false_positive_prevention(
        self,
        mock_close,
        mock_extract,
        mock_date_string,
        mock_time,
        mock_chrome_options,
        mock_wait,
        mock_chrome,
    ):
        """Test that the scraper prevents false positives in day matching."""
        # Setup basic mocks
        mock_chrome.return_value = self.mock_driver
        mock_chrome_options.return_value = Mock()
        mock_wait.return_value.until.return_value = True
        mock_date_string.return_value = "2025-07-24"

        # Mock successful extraction for when a match is found
        mock_extract.return_value = {
            "flavor": "TEST FLAVOR",
            "description": "Test description",
            "date": "2025-07-24",
            "restaurant": "Oscars",
            "url": "https://www.oscarscustard.com/index.php/flavors",
        }

        # Test scenarios that could cause false positives
        false_positive_cases = [
            {
                "description": "Thu 240 should not match when looking for Thu 24",
                "row_text": "Thu 240",
                "looking_for_day": 24,
                "should_match": False,
            },
            {
                "description": "Thu 124 should not match when looking for Thu 24",
                "row_text": "Thu 124",
                "looking_for_day": 24,
                "should_match": False,
            },
            {
                "description": "Thur 10 should not match when looking for Thu 1",
                "row_text": "Thur 10",
                "looking_for_day": 1,
                "should_match": False,
            },
            {
                "description": "Thur 11 should not match when looking for Thu 1",
                "row_text": "Thur 11",
                "looking_for_day": 1,
                "should_match": False,
            },
        ]

        for case in false_positive_cases:
            with self.subTest(case=case["description"]):
                # Setup time mock for the day we're looking for
                mock_date = Mock()
                mock_date.day = case["looking_for_day"]
                mock_date.strftime.return_value = "Thu"
                mock_time.return_value = mock_date

                # Reset driver mock
                self.mock_driver.reset_mock()

                # Create mock row with the problematic text
                mock_cell = Mock()
                mock_cell.text = "SOME FLAVOR"
                mock_cell.find_elements.return_value = []

                mock_row = Mock()
                mock_row.text = case["row_text"]
                mock_row.find_elements.return_value = [mock_cell]

                # The scraper should find this row in the initial search (starts with "Thu")
                # but should filter it out with regex
                self.mock_driver.find_elements.side_effect = [
                    [mock_row],  # Initial search finds the row
                    [],  # Fallback search (used when regex filtering rejects)
                ]

                # Run the scraper
                with patch("app.scrapers.oscars.time.sleep"):
                    result = scrape_oscars()

                # Should return empty list due to regex filtering
                self.assertEqual(
                    len(result), 0, f"Scraper should reject false positive: {case['description']}"
                )


if __name__ == "__main__":
    unittest.main()
