"""Execution primitives for ContentOS automation jobs."""

from collections.abc import Callable
from datetime import datetime, timezone
import json

from app.automation.jobs import AutomationJob, JobStatus
from app.api.common import execute, prepare_database, one
from app.database.connection import get_connection


class JobRunner:
    """Run a job through an explicit handler registry."""

    def __init__(self, handlers: dict[str, Callable[[dict], object]]) -> None:
        self.handlers = handlers

    def run(self, job: AutomationJob) -> AutomationJob:
        handler = self.handlers.get(job.job_type)
        if handler is None:
            return job.model_copy(
                update={
                    "status": JobStatus.FAILED,
                    "attempts": job.attempts + 1,
                    "error": f"Unknown job type: {job.job_type}",
                }
            )
        try:
            handler(job.payload)
            return job.model_copy(
                update={"status": JobStatus.SUCCEEDED, "attempts": job.attempts + 1, "error": None}
            )
        except Exception as exc:
            return job.model_copy(
                update={
                    "status": JobStatus.FAILED,
                    "attempts": job.attempts + 1,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )


def _claim_job(connection, job_id: str) -> bool:
    """Atomically move one queued job to RUNNING."""
    result = execute(
        connection,
        """UPDATE automation_jobs
           SET status='RUNNING', attempts=attempts+1, error=NULL,
               created_at=:started
           WHERE job_id=:id AND status='QUEUED'""",
        {"id": job_id, "started": datetime.now(timezone.utc).isoformat()},
    )
    connection.commit()
    return bool(result.rowcount)


def _recover_stale_jobs(connection, timeout_minutes: int = 10) -> int:
    """Return abandoned RUNNING jobs to QUEUED after a worker crash."""
    cutoff = datetime.now(timezone.utc).timestamp() - timeout_minutes * 60
    recovered = 0
    for row in connection.execute(
        "SELECT job_id, created_at FROM automation_jobs WHERE status='RUNNING'"
        if not hasattr(connection, "execute") or connection.__class__.__module__.startswith("sqlite")
        else "SELECT job_id, created_at FROM automation_jobs WHERE status='RUNNING'"
    ).fetchall():
        raw = row[1] if not isinstance(row, dict) else row["created_at"]
        try:
            stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            continue
        if stamp < cutoff:
            job_id = row[0] if not isinstance(row, dict) else row["job_id"]
            result = execute(
                connection,
                "UPDATE automation_jobs SET status='QUEUED', error=:error WHERE job_id=:id AND status='RUNNING'",
                {"id": job_id, "error": "Recovered after worker timeout; retrying."},
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
        _recover_stale_jobs(connection)
        rows = connection.execute(
            "SELECT job_id,job_type,payload_json,status,attempts,error,created_at "
            "FROM automation_jobs WHERE status='QUEUED' ORDER BY created_at ASC LIMIT :limit"
            if connection.__class__.__module__.startswith("sqlite")
            else "SELECT job_id,job_type,payload_json,status,attempts,error,created_at "
                 "FROM automation_jobs WHERE status='QUEUED' ORDER BY created_at ASC LIMIT :limit",
            {"limit": limit},
        ).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            job_id = data["job_id"]
            if not _claim_job(connection, job_id):
                continue
            try:
                payload = json.loads(data["payload_json"] or "{}")
                job = AutomationJob(
                    job_id=job_id,
                    job_type=data["job_type"],
                    payload=payload,
                    status=JobStatus.RUNNING,
                    attempts=data["attempts"] + 1,
                    error=None,
                )
                result = JobRunner(handlers).run(job)
                execute(
                    connection,
                    "UPDATE automation_jobs SET status=:status,error=:error WHERE job_id=:id",
                    {"status": result.status.value, "error": result.error},
                )
                connection.commit()
                results.append(result.model_dump(mode="json"))
            except Exception as exc:
                execute(
                    connection,
                    "UPDATE automation_jobs SET status='FAILED',error=:error WHERE job_id=:id",
                    {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}", "id": job_id},
                )
                connection.commit()
                results.append({"job_id": job_id, "status": "FAILED", "error": str(exc)})
        return {"processed": len(results), "jobs": results}
    finally:
        connection.close()
