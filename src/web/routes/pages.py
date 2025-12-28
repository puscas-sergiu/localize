"""HTML page routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Home page - Review translations.
    Shows review page if file is configured, otherwise shows setup prompt.
    """
    templates = request.app.state.templates
    direct_service = request.app.state.direct_file_service
    file_storage = request.app.state.file_storage

    config = direct_service.get_config()

    if not config:
        # No file configured - show friendly setup prompt
        return templates.TemplateResponse(
            "review.html",
            {
                "request": request,
                "file_configured": False,
            }
        )

    # Get file metadata
    metadata = file_storage.get_metadata(config.file_id)
    if not metadata:
        # File was deleted but config exists - show setup prompt
        return templates.TemplateResponse(
            "review.html",
            {
                "request": request,
                "file_configured": False,
            }
        )

    # Determine default language (first available or 'de')
    from ..services.translation_service import TranslationService
    content = file_storage.get_content_string(config.file_id)
    service = TranslationService()
    stats = service.get_file_stats(content)
    languages = list(stats.get("coverage", {}).keys())
    language = languages[0] if languages else "de"

    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "file_configured": True,
            "file_id": config.file_id,
            "language": language,
            "metadata": metadata,
        }
    )


@router.get("/review/{language}", response_class=HTMLResponse)
async def review_language(request: Request, language: str):
    """Review page for a specific language (uses configured file)."""
    templates = request.app.state.templates
    direct_service = request.app.state.direct_file_service
    file_storage = request.app.state.file_storage

    config = direct_service.get_config()

    if not config:
        return RedirectResponse(url="/settings", status_code=302)

    metadata = file_storage.get_metadata(config.file_id)
    if not metadata:
        return RedirectResponse(url="/settings", status_code=302)

    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "file_configured": True,
            "file_id": config.file_id,
            "language": language,
            "metadata": metadata,
        }
    )


@router.get("/stats")
async def stats_page_simple(request: Request):
    """Statistics page - redirects to dashboard (stats integrated into dashboard)."""
    return RedirectResponse(url="/", status_code=302)


@router.get("/translate")
async def translate_page_simple(request: Request):
    """Translation page - redirects to dashboard (translate integrated into dashboard)."""
    return RedirectResponse(url="/?tab=untranslated", status_code=302)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page for file configuration."""
    templates = request.app.state.templates
    file_storage = request.app.state.file_storage
    direct_service = request.app.state.direct_file_service

    files = file_storage.list_files()
    direct_config = direct_service.get_config()

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "files": files,
            "direct_config": direct_config,
        }
    )


# Legacy routes - redirect to dashboard
@router.get("/stats/{file_id}")
async def stats_page_legacy(request: Request, file_id: str):
    """Legacy statistics page - redirects to dashboard."""
    return RedirectResponse(url="/", status_code=302)


@router.get("/translate/{file_id}")
async def translate_page_legacy(request: Request, file_id: str):
    """Legacy translation page - redirects to dashboard."""
    return RedirectResponse(url="/?tab=untranslated", status_code=302)


@router.get("/review/{file_id}/{language}", response_class=HTMLResponse)
async def review_page_legacy(request: Request, file_id: str, language: str):
    """Legacy review page with file_id."""
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
            "file_configured": True,
            "file_id": file_id,
            "language": language,
            "metadata": metadata,
        }
    )
