"""FastAPI application for the localization web UI."""

import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .routes import pages, api, sse
from .services.file_storage import FileStorage
from .services.job_manager import JobManager

# Paths
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Global services
file_storage = FileStorage()
job_manager = JobManager()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="MintDeck Localizer",
        description="iOS Localization Pipeline Web UI",
        version="0.1.0",
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Set up templates
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # Store services and templates in app state
    app.state.templates = templates
    app.state.file_storage = file_storage
    app.state.job_manager = job_manager

    # Include routers
    app.include_router(pages.router)
    app.include_router(api.router, prefix="/api")
    app.include_router(sse.router, prefix="/api")

    return app


app = create_app()


def main():
    """Entry point for the localize-web command."""
    import argparse

    parser = argparse.ArgumentParser(description="Run the MintDeck Localizer web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    print(f"Starting MintDeck Localizer at http://{args.host}:{args.port}")
    uvicorn.run(
        "src.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
