from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AutomationJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    job_type: str
    payload: dict = Field(default_factory=dict)
    status: JobStatus = JobStatus.QUEUED
    attempts: int = Field(default=0, ge=0)
    error: str | None = None
