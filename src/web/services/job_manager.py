"""Job manager for tracking background translation/verification jobs."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, AsyncGenerator
import json


class JobStatus(str, Enum):
    """Job status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobProgress:
    """Progress update for a job."""
    current: int
    total: int
    percentage: float
    message: str
    language: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class Job:
    """Represents a background job."""
    job_id: str
    job_type: str  # "translate" or "verify"
    file_id: str
    status: JobStatus
    created_at: str
    languages: list[str] = field(default_factory=list)
    progress: Optional[JobProgress] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class JobManager:
    """Manages background jobs and their progress streams."""

    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.queues: dict[str, asyncio.Queue] = {}

    def create_job(
        self,
        job_type: str,
        file_id: str,
        languages: list[str] = None,
    ) -> Job:
        """Create a new job."""
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            job_type=job_type,
            file_id=file_id,
            status=JobStatus.PENDING,
            created_at=datetime.now().isoformat(),
            languages=languages or [],
        )
        self.jobs[job_id] = job
        self.queues[job_id] = asyncio.Queue()
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self.jobs.get(job_id)

    def update_status(self, job_id: str, status: JobStatus) -> None:
        """Update job status."""
        if job_id in self.jobs:
            self.jobs[job_id].status = status

    def set_running(self, job_id: str) -> None:
        """Mark job as running."""
        self.update_status(job_id, JobStatus.RUNNING)

    def set_completed(self, job_id: str, result: dict = None) -> None:
        """Mark job as completed."""
        if job_id in self.jobs:
            self.jobs[job_id].status = JobStatus.COMPLETED
            self.jobs[job_id].result = result

    def set_failed(self, job_id: str, error: str) -> None:
        """Mark job as failed."""
        if job_id in self.jobs:
            self.jobs[job_id].status = JobStatus.FAILED
            self.jobs[job_id].error = error

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        if job_id in self.jobs:
            self.jobs[job_id].status = JobStatus.CANCELLED
            return True
        return False

    async def send_progress(
        self,
        job_id: str,
        current: int,
        total: int,
        message: str,
        language: str = "",
        **extra,
    ) -> None:
        """Send a progress update to the job's stream."""
        if job_id not in self.queues:
            return

        progress = JobProgress(
            current=current,
            total=total,
            percentage=round(current / total * 100, 1) if total > 0 else 0,
            message=message,
            language=language,
            extra=extra,
        )

        if job_id in self.jobs:
            self.jobs[job_id].progress = progress

        await self.queues[job_id].put(progress)

    async def send_complete(self, job_id: str, result: dict = None) -> None:
        """Send completion event to the job's stream."""
        if job_id in self.queues:
            await self.queues[job_id].put({"complete": True, "result": result})

    async def send_error(self, job_id: str, error: str) -> None:
        """Send error event to the job's stream."""
        if job_id in self.queues:
            await self.queues[job_id].put({"error": error})

    async def stream_progress(self, job_id: str) -> AsyncGenerator[str, None]:
        """
        Yield Server-Sent Events for job progress.

        Yields SSE-formatted strings.
        """
        if job_id not in self.queues:
            yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
            return

        queue = self.queues[job_id]

        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)

                # Check for completion or error
                if isinstance(data, dict):
                    if data.get("complete"):
                        yield f"event: complete\ndata: {json.dumps(data)}\n\n"
                        break
                    if data.get("error"):
                        yield f"event: error\ndata: {json.dumps(data)}\n\n"
                        break
                    yield f"data: {json.dumps(data)}\n\n"
                elif isinstance(data, JobProgress):
                    event_data = {
                        "current": data.current,
                        "total": data.total,
                        "percentage": data.percentage,
                        "message": data.message,
                        "language": data.language,
                        **data.extra,
                    }
                    yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"

            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                yield ": heartbeat\n\n"

    def cleanup_job(self, job_id: str) -> None:
        """Clean up job resources."""
        if job_id in self.queues:
            del self.queues[job_id]
        # Keep job in self.jobs for status queries

    def list_jobs(self, file_id: str = None) -> list[Job]:
        """List jobs, optionally filtered by file_id."""
        jobs = list(self.jobs.values())
        if file_id:
            jobs = [j for j in jobs if j.file_id == file_id]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs
