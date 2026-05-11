from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from threading import Lock, Thread
from uuid import uuid4


class ChapterJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ChapterProductionJob:
    id: str
    chapter_id: int
    status: ChapterJobStatus
    thread: Thread | None = None
    result_chapter_id: int | None = None
    error_message: str | None = None


class ChapterProductionJobs:
    def __init__(self) -> None:
        self._jobs: dict[str, ChapterProductionJob] = {}
        self._lock = Lock()

    def create_pending(self, chapter_id: int) -> ChapterProductionJob:
        job = ChapterProductionJob(
            id=str(uuid4()),
            chapter_id=chapter_id,
            status=ChapterJobStatus.PENDING,
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def start(self, chapter_id: int, worker: Callable[[], int]) -> ChapterProductionJob:
        job = self.create_pending(chapter_id)

        def run_worker() -> None:
            with self._lock:
                if job.status == ChapterJobStatus.CANCELLED:
                    return
                job.status = ChapterJobStatus.RUNNING
            try:
                result = worker()
            except Exception as error:  # noqa: BLE001
                with self._lock:
                    job.status = ChapterJobStatus.FAILED
                    job.error_message = str(error)
                return

            with self._lock:
                if job.status != ChapterJobStatus.CANCELLED:
                    job.status = ChapterJobStatus.SUCCEEDED
                    job.result_chapter_id = result

        thread = Thread(target=run_worker, name=f"mynovel-chapter-{chapter_id}", daemon=True)
        job.thread = thread
        thread.start()
        return job

    def get(self, job_id: str) -> ChapterProductionJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if job.status in {ChapterJobStatus.PENDING, ChapterJobStatus.RUNNING}:
                job.status = ChapterJobStatus.CANCELLED
