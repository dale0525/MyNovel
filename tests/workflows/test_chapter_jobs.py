from mynovel.workflows.chapter_jobs import ChapterJobStatus, ChapterProductionJobs


def test_chapter_job_store_tracks_progress_and_completion() -> None:
    jobs = ChapterProductionJobs()

    job = jobs.start(chapter_id=7, worker=lambda: 123)
    job.thread.join(timeout=2)

    finished = jobs.get(job.id)
    assert finished is not None
    assert finished.status == ChapterJobStatus.SUCCEEDED
    assert finished.chapter_id == 7
    assert finished.result_chapter_id == 123


def test_chapter_job_store_can_mark_pending_job_cancelled() -> None:
    jobs = ChapterProductionJobs()
    job = jobs.create_pending(chapter_id=8)

    jobs.cancel(job.id)

    cancelled = jobs.get(job.id)
    assert cancelled is not None
    assert cancelled.status == ChapterJobStatus.CANCELLED
