# GitHub Copilot Instructions for Daily Custard App

## Project Overview
A web scraping application that collects daily frozen custard flavors from multiple custard shops in the Milwaukee area. The app scrapes websites and Facebook pages to provide up-to-date flavor information.

## Technology Stack
- **Language**: Python 3.12+
- **Web Framework**: FastAPI (for future API endpoints)
- **Scraping**: Playwright (Facebook), Selenium (dynamic sites), BeautifulSoup (static sites)
- **Testing**: pytest with unittest
- **Formatting**: black, flake8, isort, autoflake
- **Package Management**: pip with pyproject.toml

## Project Structure
```
app/
  scrapers/          # Individual scraper implementations
    scraper_base.py  # Base class with common functionality
    bigdeal.py       # Facebook scraper example
    oscars.py        # Selenium scraper example
    kopps.py         # BeautifulSoup scraper example
  locations.yaml     # Location configuration registry
tests/
  test_*_scraper.py  # Unit tests for scrapers
  test_scraper_ecosystem.py  # Integration tests
static/              # Frontend files
  data/flavors.json  # Output data
```

## Coding Conventions

### Scrapers
1. **Always inherit from `BaseScraper`**:
   ```python
   from app.scrapers.scraper_base import BaseScraper
   
   class MyNewScraper(BaseScraper):
       def __init__(self):
           super().__init__("brand_key")  # Must match locations.yaml key
   ```

2. **Implement the `scrape()` method**:
   ```python
   def scrape(self):
       """Scrape flavors for this brand."""
       self.log_start()
       
       if not self.locations:
           self.log_error("No locations found")
           return []
       
       results = []
       for location in self.locations:
           # Scraping logic here
           pass
       
       self.log_complete(len(results))
       return results
   ```

3. **Use base class methods**:
   - `self.create_flavor()` - Creates standardized flavor dict
   - `self.log_start()`, `self.log_complete()`, `self.log_error()` - Logging
   - `self.log_location()`, `self.log_flavor()` - Info logging
   - `self.locations` - Auto-loaded from locations.yaml

4. **Error handling**:
   ```python
   try:
       # Scraping logic
       return results
   except Exception as e:
       self.log_error(f"Error scraping: {e}", exc_info=True)
       return []
   ```

### Playwright (Facebook Scrapers)
- Use `sync_playwright` context manager
- Set realistic user agent
- Implement retry logic with exponential backoff
- Click "See more" buttons to expand truncated posts
- Always close browser in `finally` block
- Use extended timeouts (60s navigation, 30s selectors)

### Locations Configuration
Add new locations to `app/locations.yaml`:
```yaml
brand_key:
  - id: unique-location-id
    name: "Display Name"
    brand: BrandName
    address: "Street address"
    lat: 43.0
    lng: -88.0
    url: "https://website.com"
    facebook: "https://facebook.com/page"  # Optional
    enabled: true
```

### Testing Requirements
1. **Create comprehensive unit tests** for each scraper
2. **Test all edge cases**:
   - Multiple flavor extraction patterns
   - HTML entity decoding
   - Emoji removal
   - Missing/malformed data
   - Network errors and retries
3. **Use mocking** to avoid actual web requests in unit tests
4. **Ecosystem tests** verify real scraping (run with `--ecosystem` flag)

### Test Structure
```python
class TestMyScraperFlavorExtraction(unittest.TestCase):
    def setUp(self):
        # Mock locations
        self.locations_patcher = patch("app.scrapers.scraper_base.get_locations_for_brand")
        self.mock_get_locations = self.locations_patcher.start()
        self.mock_get_locations.return_value = [test_location_dict]
        self.scraper = MyScraper()
    
    def tearDown(self):
        self.locations_patcher.stop()
    
    def test_extract_flavor_pattern1(self):
        # Test specific extraction pattern
        pass
```

## Development Process
- All code changes must be made in feature branches and go through pull requests
- PRs must include unit tests and pass all checks (formatting, linting, tests
- Use descriptive commit messages
- Regularly pull from main to keep branches up to date
- Document any non-obvious logic or patterns in code comments and docstrings
- Update README.md as appropriate with new features or changes to usage instructions


## Common Patterns

### Flavor Extraction
Use multiple regex patterns to handle different post formats:
```python
patterns = [
    r"([A-Z][A-Z\s&]+?)\s+is\s+(?:our\s+)?(?:the\s+)?flavor",
    r"flavor[\s:]+(?:is\s+)?([A-Z][^\n.!?]+?)(?:\n|$|!|\.)",
]

for pattern in patterns:
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if match:
        flavor = match.group(1).strip()
        # Clean up: decode entities, remove emojis
        return flavor
```

### Retry Logic
```python
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2

for attempt in range(MAX_RETRIES):
    try:
        return self._attempt_operation()
    except RetryableError:
        if attempt < MAX_RETRIES - 1:
            delay = RETRY_BASE_DELAY * (2**attempt)
            time.sleep(delay)
        else:
            raise
```

### Output Format
All scrapers return list of dicts:
```python
{
    "location": "Location Name",
    "flavor": "Flavor Name",
    "description": "Optional description",
    "date": "2026-02-18",
    "url": "https://website.com",
    "location_id": "unique-id",
    "lat": 43.0,
    "lng": -88.0,
    "address": "Street address",
    "brand": "BrandName"
}
```

## Best Practices
1. **Always use logging** instead of print statements
2. **Handle missing data gracefully** - return empty list, don't crash
3. **Validate extracted data** - check length, format, sanity
4. **Use descriptive variable names** and add type hints
5. **Write docstrings** for all classes and methods
6. **Test extensively** - aim for high coverage
7. **Follow PEP 8** - code will be checked by flake8
8. **Keep functions focused** - single responsibility principle
9. **Use constants** for magic numbers (timeouts, retries, etc.)
10. **Document complex regex patterns** with examples

## Commands
- Run tests: `pytest tests/ -v`
- Run ecosystem tests: `pytest --ecosystem`
- Format code: `black app/ tests/`
- Lint: `flake8 app/ tests/`
- Sort imports: `isort app/ tests/`

## When Adding New Scrapers
1. Create scraper class inheriting from `BaseScraper`
2. Add location(s) to `locations.yaml`
3. Update ui to include new brand
4. Write comprehensive unit tests for the scraper
5. Add to ecosystem test in `test_scraper_ecosystem.py`
6. Test with real data manually before committing
7. Document any quirks or special handling needed

## Special Considerations
- **Facebook scrapers**: Posts may be truncated with "See more" - always expand
- **Selenium**: Use headless mode, set window size, handle stale elements
- **Time zones**: Use Central time for dates (custard shops are in Milwaukee)
- **Rate limiting**: Be respectful, use appropriate delays between requests
- **Error messages**: Log detailed info for debugging but don't expose to users
