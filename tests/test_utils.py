"""Unit tests for scraper utility functions."""

import unittest
from unittest.mock import Mock

from app.scrapers.utils import is_facebook_post_from_today


class TestIsFacebookPostFromToday(unittest.TestCase):
    """Test the is_facebook_post_from_today function."""

    def _create_mock_article(self, text):
        """Helper to create a mock article with inner_text."""
        article = Mock()
        article.inner_text.return_value = text
        return article

    def test_just_now_is_today(self):
        """Test: 'Just now' indicates today."""
        article = self._create_mock_article("Big Deal Burgers\nJust now\nToday's flavor is...")
        self.assertTrue(is_facebook_post_from_today(article))

    def test_minutes_ago_is_today(self):
        """Test: 'Xm' format indicates today."""
        article = self._create_mock_article("Big Deal Burgers\n15m\nFlavor of the day...")
        self.assertTrue(is_facebook_post_from_today(article))

    def test_hours_ago_is_today(self):
        """Test: 'Xh' format indicates today."""
        article = self._create_mock_article("Big Deal Burgers\n3h\nToday's flavor...")
        self.assertTrue(is_facebook_post_from_today(article))

    def test_hours_with_space_is_today(self):
        """Test: '3 h' with space indicates today."""
        article = self._create_mock_article("Big Deal Burgers\n5 h\nFlavor of the day...")
        self.assertTrue(is_facebook_post_from_today(article))

    def test_minutes_spelled_out_is_today(self):
        """Test: '30 mins' spelled out indicates today."""
        article = self._create_mock_article("Big Deal\n30 mins ago\nFlavor update...")
        self.assertTrue(is_facebook_post_from_today(article))

    def test_hours_spelled_out_is_today(self):
        """Test: '2 hours' spelled out indicates today."""
        article = self._create_mock_article("Big Deal Burgers\n2 hours ago\nToday's flavor...")
        self.assertTrue(is_facebook_post_from_today(article))

    def test_one_day_ago_not_today(self):
        """Test: '1d' indicates not today."""
        article = self._create_mock_article("Big Deal Burgers\n1d\nYesterday's flavor...")
        self.assertFalse(is_facebook_post_from_today(article))

    def test_multiple_days_ago_not_today(self):
        """Test: '3d' indicates not today."""
        article = self._create_mock_article("Big Deal Burgers\n3d\nOld flavor post...")
        self.assertFalse(is_facebook_post_from_today(article))

    def test_days_spelled_out_not_today(self):
        """Test: '2 days' spelled out indicates not today."""
        article = self._create_mock_article("Big Deal\n2 days ago\nOld post...")
        self.assertFalse(is_facebook_post_from_today(article))

    def test_month_name_not_today(self):
        """Test: Month name indicates specific date, not today."""
        article = self._create_mock_article("Big Deal Burgers\nFebruary 15\nOld flavor...")
        self.assertFalse(is_facebook_post_from_today(article))

    def test_abbreviated_month_not_today(self):
        """Test: Abbreviated month indicates not today."""
        article = self._create_mock_article("Big Deal\nFeb 10 at 3:00 PM\nOld post...")
        self.assertFalse(is_facebook_post_from_today(article))

    def test_realistic_today_post(self):
        """Test: Realistic Facebook 'today' post format."""
        text = """Big Deal Burgers & Custard
2h
·
Today's flavor is Orange Dream - orange and vanilla custard swirled together.
All reactions: 26"""
        article = self._create_mock_article(text)
        self.assertTrue(is_facebook_post_from_today(article))

    def test_realistic_yesterday_post(self):
        """Test: Realistic Facebook 'yesterday' post format."""
        text = """Big Deal Burgers & Custard
1d
·
Yesterday's flavor was Butter Pecan.
All reactions: 15"""
        article = self._create_mock_article(text)
        self.assertFalse(is_facebook_post_from_today(article))

    def test_realistic_old_post(self):
        """Test: Realistic old post with date."""
        text = """Big Deal Burgers & Custard
February 10 at 2:30 PM
·
Special flavor announcement!"""
        article = self._create_mock_article(text)
        self.assertFalse(is_facebook_post_from_today(article))

    def test_no_clear_timestamp_defaults_to_true(self):
        """Test: If no clear timestamp, assume it might be from today."""
        article = self._create_mock_article("Some post without a timestamp\nFlavor info...")
        self.assertTrue(is_facebook_post_from_today(article))

    def test_exception_handling_defaults_to_true(self):
        """Test: If error occurs, default to True (check the post)."""
        article = Mock()
        article.inner_text.side_effect = Exception("Test error")
        self.assertTrue(is_facebook_post_from_today(article))

    def test_with_logger(self):
        """Test: Function works with logger provided."""
        logger = Mock()
        article = self._create_mock_article("Big Deal\n5h\nFlavor post...")
        result = is_facebook_post_from_today(article, logger)
        self.assertTrue(result)
        # Logger should have been called
        self.assertTrue(logger.debug.called)

    def test_pre_fetched_text_is_used_without_calling_inner_text(self):
        """Test: When article_text is provided, inner_text() is not called."""
        article = Mock()
        result = is_facebook_post_from_today(article, article_text="Big Deal\n2h\nFlavor info...")
        self.assertTrue(result)
        article.inner_text.assert_not_called()

    def test_pre_fetched_text_not_today(self):
        """Test: Pre-fetched text indicating old post returns False."""
        article = Mock()
        result = is_facebook_post_from_today(article, article_text="Big Deal\n3d\nOld post...")
        self.assertFalse(result)
        article.inner_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
