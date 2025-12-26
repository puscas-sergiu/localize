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
    review_all: bool = False
    limit: Optional[int] = None


class UpdateTranslationRequest(BaseModel):
    translation: str
    state: str = "translated"


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
    asyncio.create_task(
        _run_translation_job(
            file_storage,
            job_manager,
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

    return {"status": "updated", "key": key}


# Verification endpoints
@router.post("/verify/{file_id}")
async def start_verification(request: Request, file_id: str, body: VerifyRequest):
    """Start a verification job."""
    file_storage = request.app.state.file_storage
    job_manager = request.app.state.job_manager

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
            job.job_id,
            file_id,
            body.language,
            body.review_all,
            body.limit,
        )
    )

    return {"job_id": job.job_id}


async def _run_verification_job(
    file_storage,
    job_manager,
    job_id: str,
    file_id: str,
    language: str,
    review_all: bool,
    limit: Optional[int],
):
    """Run verification job in background."""
    job_manager.set_running(job_id)

    try:
        content = file_storage.get_content_string(file_id)
        service = TranslationService()

        async def progress_callback(current, total, message, lang):
            await job_manager.send_progress(job_id, current, total, message, lang)

        result = await service.verify_translations(
            content,
            language,
            review_all,
            limit,
            progress_callback,
        )

        if result.success:
            job_manager.set_completed(job_id, {
                "total_reviewed": result.total_reviewed,
                "passed": result.passed,
                "needs_attention": result.needs_attention,
                "avg_semantic_score": result.avg_semantic_score,
                "avg_fluency_score": result.avg_fluency_score,
                "issues": result.issues,
            })
            await job_manager.send_complete(job_id, {
                "success": True,
                "total_reviewed": result.total_reviewed,
                "passed": result.passed,
                "needs_attention": result.needs_attention,
                "avg_semantic_score": result.avg_semantic_score,
                "avg_fluency_score": result.avg_fluency_score,
                "issues": result.issues,
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
