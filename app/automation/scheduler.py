from collections.abc import Callable

from app.automation.jobs import AutomationJob, JobStatus


class JobRunner:
    """Small synchronous runner; replaceable by a queue worker later."""

    def __init__(self, handlers: dict[str, Callable[[dict], object]]) -> None:
        self.handlers = handlers

    def run(self, job: AutomationJob) -> AutomationJob:
        handler = self.handlers.get(job.job_type)
        if handler is None:
            return job.model_copy(
                update={"status": JobStatus.FAILED, "error": f"Unknown job type: {job.job_type}"}
            )
        try:
            handler(job.payload)
            return job.model_copy(
                update={"status": JobStatus.SUCCEEDED, "attempts": job.attempts + 1}
            )
        except Exception as exc:
            return job.model_copy(
                update={
                    "status": JobStatus.FAILED,
                    "attempts": job.attempts + 1,
                    "error": str(exc),
                }
            )
