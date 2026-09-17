from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class ProductionStatus(StrEnum):
    QUEUED = "QUEUED"
    ASSETS = "ASSETS"
    RENDERING = "RENDERING"
    READY = "READY"
    FAILED = "FAILED"


class ProductionJob(BaseModel):
    production_id: str = Field(default_factory=lambda: str(uuid4()))
    script_id: str
    status: ProductionStatus = ProductionStatus.QUEUED
    asset_paths: list[str] = Field(default_factory=list)
    output_path: str | None = None
    error: str | None = None
