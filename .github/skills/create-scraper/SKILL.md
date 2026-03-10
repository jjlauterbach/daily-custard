# Skill: Create a New Scraper (AI-first)

Use this skill when you want Copilot to create a brand scraper from only:
- brand/shop name
- primary source URL

Do not use or maintain a Python scaffolding template script.

## Inputs
- `name`: Display name (example: `Kraverz Custard`)
- `url`: Website or Facebook URL where flavor data is published

## Expected behavior
Given only `name` and `url`, Copilot should:

1. **Derive brand keys**
	- Generate `brand_id` from the name (lowercase, underscores, alphanumeric)
	- Use a readable `brand` label for output entries

2. **Research the source**
	- Navigate to the provided URL and inspect how flavor data appears
	- Choose the simplest robust scraper strategy:
	  - `BeautifulSoup` for static HTML
	  - `Playwright` for dynamic or JS-rendered content (preferred over Selenium)
	- Identify extraction rules and fallback patterns

3. **Discover location metadata**
	- Find the location address from the site (contact/about/footer or trusted business listing)
	- Use Google Maps to find the same business and capture coordinates (`lat`, `lng`)
	- Validate that map location matches the discovered address/business name

4. **Implement end-to-end integration**
	- Create `app/scrapers/<brand_id>.py` inheriting from `BaseScraper`
	- Add location entry to `app/locations.yaml` with:
	  - `id`, `name`, `brand_id`, `address`, `lat`, `lng`, `url`, `enabled`
	  - `facebook` when the source is Facebook or available as a backup source
	- Add unit tests at `tests/test_<brand_id>_scraper.py` with mocked network/browser interactions
	- Wire scraper into `scripts/generate_flavors.py` (import + `scrape_<brand_id>` in scraper list)
	- Add to ecosystem verification in `tests/test_scraper_ecosystem.py` if needed by current pattern
	 - Update frontend assets so the new brand appears correctly in the UI (follow existing patterns in `static/`)
		 - Ensure brand/location display is included wherever location/brand lists are surfaced
		 - Keep UI changes minimal and consistent with existing styling and behavior

5. **Validate**
	- Run targeted tests for the new scraper first
	- Run lint/format checks relevant to modified files

## Project constraints
- Follow repo conventions in `.github/copilot-instructions.md`
- Use `BaseScraper` helper methods and logging
- Handle missing data gracefully (return empty list, do not crash)
- Keep implementation minimal and robust; avoid speculative features
