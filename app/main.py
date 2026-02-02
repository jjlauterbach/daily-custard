# main.py

import logging
import os

import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def load_config():
    """Load configuration from YAML file or return defaults"""
    config_file = os.path.join(os.path.dirname(__file__), "config.yaml")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                return yaml.safe_load(f) or {}
        except (yaml.YAMLError, IOError) as e:
            print(f"Warning: Could not load config file: {e}")
    return {}


# FastAPI app
app = FastAPI(title="Daily Flavors", description="Daily custard flavors from local shops")

# Configure static file serving
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Configure logging
config = load_config()
log_level = getattr(logging, config.get("logging", {}).get("root", "INFO").upper())
logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s %(message)s", level=log_level)
loggers = config.get("logging", {}).get("loggers", {})
for logger_name, logger_level in loggers.items():
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, logger_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@app.get("/")
async def root():
    """Redirect to web UI for easier access"""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/ui")


@app.get("/ui")
async def web_ui():
    """Serve the web UI"""
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file, media_type="text/html")
    else:
        return {"message": f"Web UI not found. Looking for: {index_file}"}


@app.get("/privacy")
async def privacy_page():
    """Serve the privacy policy page"""
    privacy_file = os.path.join(static_dir, "privacy.html")
    if os.path.exists(privacy_file):
        return FileResponse(privacy_file, media_type="text/html")
    else:
        return {"message": "Privacy policy not found"}


@app.get("/about")
async def about_page():
    """Serve the about page"""
    about_file = os.path.join(static_dir, "about.html")
    if os.path.exists(about_file):
        return FileResponse(about_file, media_type="text/html")
    else:
        return {"message": "About page not found"}
