# Daily Custard App 🍦

A web scraping application that collects daily flavor information from frozen custard shops in the Milwaukee area and displays them in a modern web UI.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](https://docs.pytest.org/)

## Table of Contents

- [Technology Stack](#technology-stack)
- [Supported Locations](#supported-locations)
- [Features](#features)
- [Quick Start](#quick-start)
- [Testing & Quality](#testing--quality)
- [Ecosystem Testing](#ecosystem-testing)
- [Scraper Architecture](#scraper-architecture)
- [Development Workflow](#development-workflow)
- [Docker Deployment](#docker-deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Technology Stack

- **Language**: Python 3.12+
- **Web Scraping**: 
  - BeautifulSoup (static sites)
  - Selenium with ChromeDriver (dynamic sites)
  - Playwright (Facebook pages)
- **Testing**: pytest with unittest, comprehensive mocking
- **Code Quality**: black, flake8, isort, autoflake, pre-commit hooks
- **CI/CD**: GitHub Actions with automated testing and deployment
- **Deployment**: Docker, Docker Compose, Cloudflare Pages
- **Package Management**: pip with pyproject.toml

## Supported Locations

- **Bubba's Frozen Custard**
- **Culver's**
- **Gilles**
- **Kopp's Frozen Custard**
- **Murf's Frozen Custard**
- **Oscar's Frozen Custard**

## Features
- **Robust scrapers** for each shop using multiple strategies:
  - BeautifulSoup for static sites (Kopp's, Bubba's, Murf's)
  - Selenium for dynamic sites (Oscar's, Culver's)
  - Playwright for Facebook pages (Big Deal Burgers)
- **Base scraper architecture** with common functionality and error handling
- **Location registry** (locations.yaml) for easy configuration
- **Modern UI** with date-anchored cards and interactive map
- **Comprehensive testing**:
  - Unit tests
  - Integration tests
  - Ecosystem tests against live sites
- **CI/CD** with linting, formatting, security, and coverage checks
- **Pre-commit hooks** for code quality

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone <your-repo-url>
cd daily-flavors-app

# Run with Docker Compose
docker compose up

# Access the app in your browser
open http://localhost:8080
```

### Local Development

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .[dev]

# Generate the static flavors data
python scripts/generate_flavors.py

# Serve the static site
python -m http.server --directory static 8080
```

## Testing & Quality

### Running Tests

- **Run all unit tests:**
  ```bash
  pytest tests/ -v
  ```
  
- **Run tests for a specific scraper:**
  ```bash
  pytest tests/test_bigdeal_scraper.py -v
  ```
  
- **Run with coverage:**
  ```bash
  pytest --cov=app tests/
  ```

### Code Quality

- **Run pre-commit hooks manually:**
  ```bash
  pre-commit run --all-files
  ```
  
- **Install pre-commit hooks locally:**
  ```bash
  pre-commit install
  ```
  
- **Format code:**
  ```bash
  black app/ tests/
  isort app/ tests/
  ```
  
- **Lint code:**
  ```bash
  flake8 app/ tests/
  ```

All checks (`flake8`, `black`, `isort`, `autoflake`, `pip-audit`) run automatically in CI and pre-commit hooks.

## Ecosystem Testing

A dedicated ecosystem test suite checks that all scrapers are working against live sites. This is run daily via GitHub Actions and can be run locally:

```bash
pytest --ecosystem
```

**Important Notes:**
- The ecosystem test is **skipped by default** unless you pass the `--ecosystem` flag
- Tests run against **live websites** - network connection required
- Each scraper must return at least one valid flavor with all required fields
- The daily workflow alerts you if a site changes or breaks scraping

## Scraper Architecture

All scrapers inherit from `BaseScraper` which provides common functionality:

### Creating a New Scraper

1. **Create scraper class**:
   ```python
   from app.scrapers.scraper_base import BaseScraper
   
   class MyNewScraper(BaseScraper):
       def __init__(self):
           super().__init__("brand_key")  # Must match locations.yaml
       
       def scrape(self):
           self.log_start()
           
           if not self.locations:
               self.log_error("No locations found")
               return []
           
           results = []
           # Scraping logic here
           
           self.log_complete(len(results))
           return results
   ```

2. **Add locations to `app/locations.yaml`**:
   ```yaml
   brand_key:
     - id: unique-location-id
       name: "Display Name"
       brand: BrandName
       address: "123 Main St"
       lat: 43.0
       lng: -88.0
       url: "https://website.com"
       facebook: "https://facebook.com/page"  # Optional
       enabled: true
   ```

3. **Write comprehensive unit tests** (`tests/test_brand_scraper.py`):
   - Test flavor extraction with various patterns
   - Mock external services (no real network calls)
   - Cover edge cases and error handling
   - Aim for 40+ test cases

4. **Add to ecosystem test** (`tests/test_scraper_ecosystem.py`)

5. **Test manually** with real data before committing

### Base Scraper Methods

- `self.create_flavor()` - Creates standardized flavor dict
- `self.log_start()`, `self.log_complete()`, `self.log_error()` - Logging helpers
- `self.locations` - Auto-loaded from locations.yaml
- Built-in session management and user agents

## Continuous Integration

- GitHub Actions workflow runs on PRs and main branch:
  - Linting, formatting, security audit, and test coverage

## Cloudflare Pages Deployment

This project uses Cloudflare Pages for hosting. Preview deployments are automatically created for each pull request and cleaned up when the PR is merged or closed.

### Setup Required Secrets

To enable automatic cleanup of preview deployments, add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

1. **CLOUDFLARE_API_TOKEN**: Create an API token in Cloudflare Dashboard
   - Go to My Profile → API Tokens → Create Token
   - Use "Edit Cloudflare Pages" template or custom token with:
     - Account → Cloudflare Pages → Edit permissions
   
2. **CLOUDFLARE_ACCOUNT_ID**: Found in Cloudflare Dashboard
   - Click on any site → Copy your Account ID from the right sidebar
   
3. **CLOUDFLARE_PROJECT_NAME**: Your Cloudflare Pages project name
   - Example: `daily-flavors-app`

The cleanup workflow automatically runs when pull requests are closed (merged or abandoned) and removes all associated preview deployments.

## Configuration

Static content is served from the `static/` directory. The daily data file is generated at `static/data/flavors.json` by the scraper script.

## Docker Deployment

### Build and Run

```bash
# Build the container (uses pyproject.toml, not requirements.txt)
docker build -t daily-custard-app .

# Run the container (serves static site on port 8000 inside container)
docker run -p 8080:8000 daily-custard-app

# Or use Docker Compose (recommended for local dev)
docker compose up
```

- The Dockerfile now uses `pyproject.toml` for dependency management. You do not need `requirements.txt`.
- The image is automatically tagged with the release version and `latest` in CI/CD.

## Troubleshooting

### Common Issues

1. **ChromeDriver not found**
   ```bash
   # Install ChromeDriver manually
   brew install chromedriver  # macOS
   ```

2. **Module import errors**
   ```bash
   # Ensure all dependencies are installed
   pip install .[dev]
   ```

3. **Encoding issues**
   - Enable debug logging to see detailed encoding attempts
   - The scrapers include multiple encoding fallback strategies

4. **Site structure changes**
   - Enable debug logging to inspect HTML structure
   - Update selectors in the relevant scraper function

5. **Facebook scraper issues (Big Deal Burgers)**
   - Posts may be truncated - scraper automatically clicks "See more" buttons
   - Flavor announcements must match specific patterns (e.g., "is our flavor of the day")
   - Check up to 10 recent posts for flavor announcements

6. **Playwright browser issues**
   ```bash
   # Install Playwright browsers
   playwright install chromium
   ```

## Development Workflow

### Adding a New Scraper

See the [Scraper Architecture](#scraper-architecture) section above for detailed instructions.

**Quick checklist:**
1. ✅ Create scraper class inheriting from `BaseScraper`
2. ✅ Add location(s) to `locations.yaml`
3. ✅ Write comprehensive unit tests
4. ✅ Add to ecosystem test
5. ✅ Update README with new location
6. ✅ Test manually with real data
7. ✅ Ensure all tests pass and code is formatted

### Making Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/my-changes
   ```

2. **Make your changes** following project conventions

3. **Run tests and checks**:
   ```bash
   pytest tests/ -v                # Run unit tests
   pytest --ecosystem             # Test against live sites
   black app/ tests/              # Format code
   flake8 app/ tests/             # Lint code
   pre-commit run --all-files     # Run all hooks
   ```

4. **Commit with descriptive messages**:
   ```bash
   git commit -m "Add Big Deal Burgers scraper with Facebook integration"
   ```

5. **Push and create PR**:
   ```bash
   git push origin feature/my-changes
   ```

### GitHub Copilot Instructions

This project includes GitHub Copilot instructions at `.github/copilot-instructions.md` to help AI-assisted development follow project conventions.

## Contributing

All contributions are welcome! Please follow these guidelines:

- **Code Quality**: All code must pass linting (flake8), formatting (black, isort), and security checks (pip-audit)
- **Testing**: Write comprehensive unit tests (40+ tests for new scrapers) and ensure all tests pass
- **Documentation**: Update README and docstrings for any new features
- **Feature Branches**: All changes must go through pull requests - no direct commits to main
- **Commit Messages**: Use descriptive commit messages explaining what and why
- **Pre-commit Hooks**: Install and run pre-commit hooks before committing

Run `pre-commit install` to automatically check code quality before each commit.
