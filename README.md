# Daily Custard App 🍦

A web scraper application that collects daily flavor information from frozen custard shops and displays them in a modern web UI.

## Supported Locations

- **Bubba's**
- **Culver's**
- **Kopp's Frozen Custard**
- **Oscar's Frozen Custard**
- **Murf's Frozen Custard**

## Features
- Robust scrapers for each shop, extracting date, flavor, and description
- Modern UI with date-anchored cards
- Automated tests (unit, integration, and Selenium UI)
- CI/CD with linting, formatting, security, and coverage checks
- Pre-commit hooks for code quality

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

- **Run all tests:**
  ```bash
  pytest
  ```
- **Run pre-commit hooks manually:**
  ```bash
  pre-commit run --all-files
  ```
- **Install pre-commit hooks locally:**
  ```bash
  pre-commit install
  ```
- **Lint, format, and security checks:**
  - `flake8`, `black`, `isort`, `autoflake`, `pip-audit` are all run in CI and pre-commit

## Ecosystem Testing

A dedicated ecosystem test suite checks that all scrapers are working against live sites. This is run daily via GitHub Actions and can be run locally:

```bash
pytest --ecosystem
```

- The ecosystem test is skipped by default unless you pass the `--ecosystem` flag.
- The test will fail if any scraper fails to return a valid flavor for today.
- The daily workflow will alert you if a site changes or breaks scraping.

## Continuous Integration

- GitHub Actions workflow runs on PRs and main branch:
  - Linting, formatting, security audit, and test coverage

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

## Contributing

- Please run pre-commit and all tests before submitting a PR.
- All code is auto-formatted and linted in CI.

