"""HTML page routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    templates = request.app.state.templates
    file_storage = request.app.state.file_storage

    files = file_storage.list_files()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "files": files,
        }
    )


@router.get("/stats/{file_id}", response_class=HTMLResponse)
async def stats_page(request: Request, file_id: str):
    """Statistics page for a file."""
    templates = request.app.state.templates
    file_storage = request.app.state.file_storage

    metadata = file_storage.get_metadata(file_id)
    if not metadata:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": "File not found"},
            status_code=404,
        )

    return templates.TemplateResponse(
        "stats.html",
        {
            "request": request,
            "file_id": file_id,
            "metadata": metadata,
        }
    )


@router.get("/translate/{file_id}", response_class=HTMLResponse)
async def translate_page(request: Request, file_id: str):
    """Translation page for a file."""
    templates = request.app.state.templates
    file_storage = request.app.state.file_storage

    metadata = file_storage.get_metadata(file_id)
    if not metadata:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": "File not found"},
            status_code=404,
        )

    return templates.TemplateResponse(
        "translate.html",
        {
            "request": request,
            "file_id": file_id,
            "metadata": metadata,
        }
    )


@router.get("/review/{file_id}/{language}", response_class=HTMLResponse)
async def review_page(request: Request, file_id: str, language: str):
    """Review page for a specific language."""
    templates = request.app.state.templates
    file_storage = request.app.state.file_storage

    metadata = file_storage.get_metadata(file_id)
    if not metadata:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": "File not found"},
            status_code=404,
        )

    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "file_id": file_id,
            "language": language,
            "metadata": metadata,
        }
    )
