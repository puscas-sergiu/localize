"""REST API routes."""

import asyncio
from typing import Optional
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from ..services.translation_service import TranslationService
from ..services.job_manager import JobStatus

router = APIRouter()


# Request/Response models
class TranslateRequest(BaseModel):
    languages: list[str] = ["de", "fr", "it", "es", "ro"]
    quality_threshold: float = 80.0


class VerifyRequest(BaseModel):
    language: str
    offset: int = 0  # For batch pagination
    include_reviewed: bool = False  # Re-check already reviewed strings


class UpdateTranslationRequest(BaseModel):
    translation: str
    state: str = "translated"


class TranslateSingleRequest(BaseModel):
    key: str
    source: str


class DirectFileConfigRequest(BaseModel):
    file_path: str


class AddLanguageRequest(BaseModel):
    language: str


class ReviewSingleRequest(BaseModel):
    key: str
    source: str
    translation: str


class ReviewSuggestion(BaseModel):
    text: str
    explanation: str


class ReviewSingleResponse(BaseModel):
    key: str
    issues: list[str]
    suggestions: list[ReviewSuggestion]
    original_translation: str


# File endpoints
@router.post("/files/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Upload an .xcstrings file."""
    file_storage = request.app.state.file_storage

    # Validate file type
    if not file.filename.endswith(".xcstrings"):
        raise HTTPException(400, "File must be a .xcstrings file")

    # Read and save content
    content = await file.read()

    # Validate JSON
    try:
        import json
        json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON in file")

    metadata = file_storage.save(content, file.filename)

    # Get stats
    service = TranslationService()
    stats = service.get_file_stats(content.decode("utf-8"))

    return {
        "file_id": metadata.file_id,
        "filename": metadata.original_name,
        "size_bytes": metadata.size_bytes,
        "stats": stats,
    }


@router.get("/files/{file_id}")
async def get_file_info(request: Request, file_id: str):
    """Get file metadata and stats."""
    file_storage = request.app.state.file_storage

    metadata = file_storage.get_metadata(file_id)
    if not metadata:
        raise HTTPException(404, "File not found")

    content = file_storage.get_content_string(file_id)
    service = TranslationService()
    stats = service.get_file_stats(content)

    return {
        "file_id": metadata.file_id,
        "filename": metadata.original_name,
        "upload_time": metadata.upload_time,
        "size_bytes": metadata.size_bytes,
        "stats": stats,
    }


@router.get("/files/{file_id}/download")
async def download_file(request: Request, file_id: str):
    """Download the processed file."""
    file_storage = request.app.state.file_storage

    metadata = file_storage.get_metadata(file_id)
    if not metadata:
        raise HTTPException(404, "File not found")

    content = file_storage.get_content(file_id)

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{metadata.original_name}"'
        }
    )


@router.delete("/files/{file_id}")
async def delete_file(request: Request, file_id: str):
    """Delete an uploaded file."""
    file_storage = request.app.state.file_storage

    if not file_storage.delete(file_id):
        raise HTTPException(404, "File not found")

    return {"status": "deleted"}


# Stats endpoints
@router.get("/stats/{file_id}")
async def get_stats(request: Request, file_id: str):
    """Get statistics for a file."""
    file_storage = request.app.state.file_storage

    content = file_storage.get_content_string(file_id)
    if not content:
        raise HTTPException(404, "File not found")

    service = TranslationService()
    stats = service.get_file_stats(content)

    return stats


@router.get("/stats/{file_id}/untranslated/{language}")
async def get_untranslated(request: Request, file_id: str, language: str):
    """Get untranslated strings for a language."""
    file_storage = request.app.state.file_storage

    content = file_storage.get_content_string(file_id)
    if not content:
        raise HTTPException(404, "File not found")

    service = TranslationService()
    untranslated = service.get_untranslated_keys(content, language)

    return {"language": language, "untranslated": untranslated}


@router.get("/stats/{file_id}/untranslated-count")
async def get_untranslated_count(request: Request, file_id: str):
    """Get total count of untranslated strings across all languages."""
    file_storage = request.app.state.file_storage

    content = file_storage.get_content_string(file_id)
    if not content:
        raise HTTPException(404, "File not found")

    service = TranslationService()
    stats = service.get_file_stats(content)

    # Calculate total untranslated across all languages
    total_untranslated = 0
    languages_with_missing = {}
    for lang, coverage in stats.get("coverage", {}).items():
        missing = coverage["total"] - coverage["translated"]
        if missing > 0:
            languages_with_missing[lang] = missing
            total_untranslated += missing

    return {
        "file_id": file_id,
        "total_untranslated": total_untranslated,
        "languages_with_missing": languages_with_missing,
    }


# Translation endpoints
@router.post("/translate/{file_id}")
async def start_translation(request: Request, file_id: str, body: TranslateRequest):
    """Start a translation job."""
    file_storage = request.app.state.file_storage
    job_manager = request.app.state.job_manager

    if not file_storage.exists(file_id):
        raise HTTPException(404, "File not found")

    # Create job
    job = job_manager.create_job(
        job_type="translate",
        file_id=file_id,
        languages=body.languages,
    )

    # Start background translation
    direct_service = request.app.state.direct_file_service
    asyncio.create_task(
        _run_translation_job(
            file_storage,
            job_manager,
            direct_service,
            job.job_id,
            file_id,
            body.languages,
            body.quality_threshold,
        )
    )

    return {"job_id": job.job_id}


async def _run_translation_job(
    file_storage,
    job_manager,
    direct_service,
    job_id: str,
    file_id: str,
    languages: list[str],
    quality_threshold: float,
):
    """Run translation job in background."""
    job_manager.set_running(job_id)

    try:
        content = file_storage.get_content_string(file_id)
        service = TranslationService()

        async def progress_callback(current, total, message, language, **extra):
            await job_manager.send_progress(
                job_id, current, total, message, language, **extra
            )

        output, result = await service.translate_file(
            content,
            languages,
            quality_threshold,
            progress_callback,
        )

        if result.success:
            # Update file with translations
            file_storage.update_content(file_id, output.encode("utf-8"))

            # Auto-apply if using direct file mode
            config = direct_service.get_config()
            if config and config.file_id == file_id:
                direct_service.apply()

            job_manager.set_completed(job_id, {
                "languages_processed": result.languages_processed,
                "stats_by_language": result.stats_by_language,
            })
            await job_manager.send_complete(job_id, {
                "success": True,
                "languages_processed": result.languages_processed,
                "stats_by_language": result.stats_by_language,
            })
        else:
            job_manager.set_failed(job_id, result.error)
            await job_manager.send_error(job_id, result.error)

    except Exception as e:
        job_manager.set_failed(job_id, str(e))
        await job_manager.send_error(job_id, str(e))

    finally:
        job_manager.cleanup_job(job_id)


@router.get("/translate/{job_id}/status")
async def get_translation_status(request: Request, job_id: str):
    """Get translation job status (polling fallback)."""
    job_manager = request.app.state.job_manager

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "progress": job.progress.__dict__ if job.progress else None,
        "result": job.result,
        "error": job.error,
    }


# Review endpoints
@router.get("/review/{file_id}/{language}")
async def get_translations_for_review(
    request: Request,
    file_id: str,
    language: str,
    state: Optional[str] = None,
):
    """Get translations for review."""
    file_storage = request.app.state.file_storage

    content = file_storage.get_content_string(file_id)
    if not content:
        raise HTTPException(404, "File not found")

    service = TranslationService()
    translations = service.get_translations_for_review(content, language, state)

    return {"language": language, "translations": translations}


@router.put("/review/{file_id}/{language}/{key:path}")
async def update_translation(
    request: Request,
    file_id: str,
    language: str,
    key: str,
    body: UpdateTranslationRequest,
):
    """Update a single translation."""
    file_storage = request.app.state.file_storage
    review_history = request.app.state.review_history

    content = file_storage.get_content_string(file_id)
    if not content:
        raise HTTPException(404, "File not found")

    service = TranslationService()
    updated_content = service.update_translation(
        content,
        language,
        key,
        body.translation,
        body.state,
    )

    file_storage.update_content(file_id, updated_content.encode("utf-8"))

    # Clear review history for this key so it gets re-reviewed
    review_history.clear_key(file_id, language, key)

    # Auto-apply if using direct file mode
    direct_service = request.app.state.direct_file_service
    config = direct_service.get_config()
    if config and config.file_id == file_id:
        direct_service.apply()

    return {"status": "updated", "key": key}


@router.post("/review/{file_id}/{language}/translate-single")
async def translate_single_string(
    request: Request,
    file_id: str,
    language: str,
    body: TranslateSingleRequest,
):
    """Translate a single string and save it."""
    file_storage = request.app.state.file_storage

    content = file_storage.get_content_string(file_id)
    if not content:
        raise HTTPException(404, "File not found")

    # Import translator and run in thread pool
    from ...translation.translator import HybridTranslator

    translator = HybridTranslator()

    result = await asyncio.to_thread(
        translator.translate,
        body.key,
        body.source,
        language,
    )

    if not result.success:
        raise HTTPException(500, f"Translation failed: {result.error or 'Unknown error'}")

    # Save the translation
    service = TranslationService()
    updated_content = service.update_translation(
        content,
        language,
        body.key,
        result.translation,
        "translated",
    )

    file_storage.update_content(file_id, updated_content.encode("utf-8"))

    # Auto-apply if using direct file mode
    direct_service = request.app.state.direct_file_service
    config = direct_service.get_config()
    if config and config.file_id == file_id:
        direct_service.apply()

    return {
        "status": "translated",
        "key": body.key,
        "translation": result.translation,
        "state": "translated",
        "quality_score": result.quality_score.overall,
        "provider": result.provider,
    }


@router.post("/review/{file_id}/{language}/review-single")
async def review_single_translation(
    request: Request,
    file_id: str,
    language: str,
    body: ReviewSingleRequest,
) -> ReviewSingleResponse:
    """
    Review a single translation with LLM and get suggestions.

    Returns issues found and 2-3 alternative translation suggestions.
    """
    file_storage = request.app.state.file_storage

    if not file_storage.exists(file_id):
        raise HTTPException(404, "File not found")

    from ...validation.llm_reviewer import LLMReviewer

    reviewer = LLMReviewer()

    result = await asyncio.to_thread(
        reviewer.review_with_suggestions,
        source=body.source,
        translation=body.translation,
        target_lang=language,
        key=body.key,
        num_suggestions=3,
    )

    # Check if review failed
    if result.issues and len(result.issues) == 1 and result.issues[0].startswith("Review failed:"):
        raise HTTPException(500, result.issues[0])

    return ReviewSingleResponse(
        key=result.key,
        issues=result.issues,
        suggestions=[
            ReviewSuggestion(text=s.get("text", ""), explanation=s.get("explanation", ""))
            for s in result.suggestions
        ],
        original_translation=body.translation,
    )


@router.post("/review/{file_id}/{language}/translate-all-untranslated")
async def translate_all_untranslated(
    request: Request,
    file_id: str,
    language: str,
):
    """Start a job to translate all untranslated strings for a language."""
    file_storage = request.app.state.file_storage
    job_manager = request.app.state.job_manager

    if not file_storage.exists(file_id):
        raise HTTPException(404, "File not found")

    # Create job
    job = job_manager.create_job(
        job_type="translate",
        file_id=file_id,
        languages=[language],
    )

    # Start background translation for single language
    direct_service = request.app.state.direct_file_service
    asyncio.create_task(
        _run_translation_job(
            file_storage,
            job_manager,
            direct_service,
            job.job_id,
            file_id,
            [language],
            80.0,  # Default quality threshold
        )
    )

    return {"job_id": job.job_id}


# Verification endpoints
@router.post("/verify/{file_id}")
async def start_verification(request: Request, file_id: str, body: VerifyRequest):
    """Start a verification job."""
    file_storage = request.app.state.file_storage
    job_manager = request.app.state.job_manager
    direct_service = request.app.state.direct_file_service
    review_history = request.app.state.review_history

    if not file_storage.exists(file_id):
        raise HTTPException(404, "File not found")

    # Create job
    job = job_manager.create_job(
        job_type="verify",
        file_id=file_id,
        languages=[body.language],
    )

    # Start background verification
    asyncio.create_task(
        _run_verification_job(
            file_storage,
            job_manager,
            direct_service,
            review_history,
            job.job_id,
            file_id,
            body.language,
            body.offset,
            body.include_reviewed,
        )
    )

    return {"job_id": job.job_id}


async def _run_verification_job(
    file_storage,
    job_manager,
    direct_service,
    review_history,
    job_id: str,
    file_id: str,
    language: str,
    offset: int,
    include_reviewed: bool = False,
):
    """Run verification job in background."""
    job_manager.set_running(job_id)

    try:
        content = file_storage.get_content_string(file_id)
        service = TranslationService()

        async def progress_callback(current, total, message, lang):
            await job_manager.send_progress(job_id, current, total, message, lang)

        result, updated_content = await service.verify_translations(
            content,
            language,
            offset,
            include_reviewed,
            progress_callback,
            review_history=review_history,
            file_id=file_id,
        )

        if result.success:
            # Save the updated content (passed strings marked as reviewed)
            if result.auto_reviewed_count > 0:
                file_storage.update_content(file_id, updated_content.encode("utf-8"))

                # Auto-apply if using direct file mode
                config = direct_service.get_config()
                if config and config.file_id == file_id:
                    direct_service.apply()

            job_manager.set_completed(job_id, {
                "total_reviewed": result.total_reviewed,
                "passed": result.passed,
                "needs_attention": result.needs_attention,
                "issues": result.issues,
                "has_more": result.has_more,
                "total_unreviewed": result.total_unreviewed,
                "next_offset": result.next_offset,
                "auto_reviewed_count": result.auto_reviewed_count,
                "skipped_unchanged": result.skipped_unchanged,
            })
            await job_manager.send_complete(job_id, {
                "success": True,
                "total_reviewed": result.total_reviewed,
                "passed": result.passed,
                "needs_attention": result.needs_attention,
                "issues": result.issues,
                "has_more": result.has_more,
                "total_unreviewed": result.total_unreviewed,
                "next_offset": result.next_offset,
                "auto_reviewed_count": result.auto_reviewed_count,
                "skipped_unchanged": result.skipped_unchanged,
            })
        else:
            job_manager.set_failed(job_id, result.error)
            await job_manager.send_error(job_id, result.error)

    except Exception as e:
        job_manager.set_failed(job_id, str(e))
        await job_manager.send_error(job_id, str(e))

    finally:
        job_manager.cleanup_job(job_id)


@router.get("/verify/{job_id}/status")
async def get_verification_status(request: Request, job_id: str):
    """Get verification job status (polling fallback)."""
    job_manager = request.app.state.job_manager

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "progress": job.progress.__dict__ if job.progress else None,
        "result": job.result,
        "error": job.error,
    }


# Direct file endpoints
@router.get("/direct/config")
async def get_direct_config(request: Request):
    """Get current direct file configuration."""
    direct_service = request.app.state.direct_file_service

    config = direct_service.get_config()
    if not config:
        return {"configured": False}

    file_info = direct_service.get_file_info()
    return {
        "configured": True,
        "file_path": config.file_path,
        "file_id": config.file_id,
        "configured_at": config.configured_at,
        "last_synced": config.last_synced,
        **(file_info or {}),
    }


@router.post("/direct/config")
async def set_direct_config(request: Request, body: DirectFileConfigRequest):
    """Configure a direct file path."""
    direct_service = request.app.state.direct_file_service

    try:
        config, stats = direct_service.configure(body.file_path)
        return {
            "file_id": config.file_id,
            "file_path": config.file_path,
            "stats": stats,
        }
    except FileNotFoundError:
        raise HTTPException(404, f"File not found: {body.file_path}")
    except PermissionError:
        raise HTTPException(403, f"Permission denied: {body.file_path}")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/direct/config")
async def clear_direct_config(request: Request):
    """Clear direct file configuration."""
    direct_service = request.app.state.direct_file_service
    direct_service.clear_config()
    return {"status": "cleared"}


@router.post("/direct/refresh")
async def refresh_direct_file(request: Request):
    """Refresh content from configured file path."""
    direct_service = request.app.state.direct_file_service

    config = direct_service.get_config()
    if not config:
        raise HTTPException(400, "No direct file configured")

    success, result = direct_service.refresh()
    if not success:
        raise HTTPException(400, result)

    return {"status": "refreshed", "stats": result}


@router.post("/direct/apply")
async def apply_direct_file(request: Request):
    """Apply (save) current content to configured file path."""
    direct_service = request.app.state.direct_file_service

    config = direct_service.get_config()
    if not config:
        raise HTTPException(400, "No direct file configured")

    success, message = direct_service.apply()
    if not success:
        raise HTTPException(500, message)

    return {"status": "applied", "message": message}


# Language management endpoints
@router.post("/languages/{file_id}")
async def add_language(request: Request, file_id: str, body: AddLanguageRequest):
    """Add a new language to a file."""
    file_storage = request.app.state.file_storage
    direct_service = request.app.state.direct_file_service

    content = file_storage.get_content_string(file_id)
    if not content:
        raise HTTPException(404, "File not found")

    service = TranslationService()

    try:
        updated_content = service.add_language(content, body.language)
        file_storage.update_content(file_id, updated_content.encode("utf-8"))

        # Get updated stats
        stats = service.get_file_stats(updated_content)

        # Auto-apply if using direct file mode
        applied = False
        config = direct_service.get_config()
        if config and config.file_id == file_id:
            success, message = direct_service.apply()
            applied = success

        return {
            "status": "added",
            "language": body.language,
            "stats": stats,
            "applied_to_disk": applied,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
