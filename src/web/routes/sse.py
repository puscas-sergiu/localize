"""Server-Sent Events streaming routes."""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/translate/{job_id}/stream")
async def stream_translation_progress(request: Request, job_id: str):
    """
    Stream translation progress via Server-Sent Events.

    Events:
    - progress: {"current": int, "total": int, "percentage": float, "message": str, "language": str}
    - complete: {"complete": true, "result": {...}}
    - error: {"error": str}
    """
    job_manager = request.app.state.job_manager

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    return StreamingResponse(
        job_manager.stream_progress(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/verify/{job_id}/stream")
async def stream_verification_progress(request: Request, job_id: str):
    """
    Stream verification progress via Server-Sent Events.

    Events:
    - progress: {"current": int, "total": int, "percentage": float, "message": str, "language": str}
    - complete: {"complete": true, "result": {...}}
    - error: {"error": str}
    """
    job_manager = request.app.state.job_manager

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    return StreamingResponse(
        job_manager.stream_progress(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
