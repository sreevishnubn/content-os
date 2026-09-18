"""Execution primitives for ContentOS automation jobs."""

from collections.abc import Callable
from datetime import datetime, timezone, timedelta
import json

from app.automation.jobs import AutomationJob, JobStatus
from app.api.common import execute, prepare_database, rows
from app.database.connection import get_connection


class JobRunner:
    """Run a job through an explicit handler registry."""

    def __init__(self, handlers: dict[str, Callable[[dict], object]]) -> None:
        self.handlers = handlers

    def run(self, job: AutomationJob) -> AutomationJob:
        handler = self.handlers.get(job.job_type)
        if handler is None:
            return job.model_copy(update={
                "status": JobStatus.FAILED,
                "attempts": job.attempts + 1,
                "error": f"Unknown job type: {job.job_type}",
            })
        try:
            handler(job.payload)
            return job.model_copy(update={
                "status": JobStatus.SUCCEEDED,
                "attempts": job.attempts,
                "error": None,
            })
        except Exception as exc:
            return job.model_copy(update={
                "status": JobStatus.FAILED,
                "attempts": job.attempts,
                "error": f"{type(exc).__name__}: {exc}",
            })


def _claim_job(connection, job_id: str) -> bool:
    result = execute(
        connection,
        """UPDATE automation_jobs
           SET status='RUNNING', error=NULL, attempts=attempts+1
           WHERE job_id=:id AND status='QUEUED'""",
        {"id": job_id},
    )
    connection.commit()
    return bool(result.rowcount)


def _recover_stale_jobs(connection, timeout_minutes: int = 10) -> int:
    """Requeue jobs left RUNNING by a crashed serverless invocation."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    recovered = 0
    for row in rows(connection, "SELECT job_id, created_at FROM automation_jobs WHERE status='RUNNING'"):
        try:
            stamp = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        if stamp < cutoff:
            result = execute(
                connection,
                """UPDATE automation_jobs
                   SET status='QUEUED', error=:error
                   WHERE job_id=:id AND status='RUNNING'""",
                {"id": row["job_id"], "error": "Recovered after worker timeout; retrying."},
            )
            recovered += result.rowcount or 0
    connection.commit()
    return recovered


def run_queued_jobs(handlers: dict[str, Callable[[dict], object]], limit: int = 5) -> dict:
    """Claim and execute a bounded batch of queued jobs."""
    limit = max(1, min(limit, 10))
    connection = get_connection()
    try:
        prepare_database(connection)
        recovered = _recover_stale_jobs(connection)
        queued = rows(
            connection,
            """SELECT job_id,job_type,payload_json,status,attempts,error,created_at
               FROM automation_jobs
               WHERE status='QUEUED'
               ORDER BY created_at ASC
               LIMIT :limit""",
            {"limit": limit},
        )
        results = []
        for row in queued:
            job_id = row["job_id"]
            if not _claim_job(connection, job_id):
                continue
            try:
                payload = json.loads(row["payload_json"] or "{}")
                if not isinstance(payload, dict):
                    raise ValueError("Automation payload must be a JSON object")
                job = AutomationJob(
                    job_id=job_id,
                    job_type=row["job_type"],
                    payload=payload,
                    status=JobStatus.RUNNING,
                    attempts=int(row["attempts"])+1,
                )
                result = JobRunner(handlers).run(job)
                execute(
                    connection,
                    """UPDATE automation_jobs
                       SET status=:status,error=:error
                       WHERE job_id=:id""",
                    {"status": result.status.value, "error": result.error, "id": job_id},
                )
                connection.commit()
                results.append(result.model_dump(mode="json"))
            except Exception as exc:
                execute(
                    connection,
                    """UPDATE automation_jobs
                       SET status='FAILED',error=:error
                       WHERE job_id=:id""",
                    {"error": f"{type(exc).__name__}: {exc}", "id": job_id},
                )
                connection.commit()
                results.append({"job_id": job_id, "status": "FAILED", "error": str(exc)})
        return {"processed": len(results), "recovered": recovered, "jobs": results}
    finally:
        connection.close()
