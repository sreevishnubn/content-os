"""Dashboard workflow APIs with explicit lifecycle boundaries."""

from datetime import datetime, timezone
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.analytics.models import VideoMetrics
from app.api.common import execute, one, prepare_database, require_api_token, rows
from app.config.settings import get_settings
from app.database.connection import get_connection, using_postgres
from app.learning.engine import LearningEngine
from app.llm.factory import get_llm_provider
from app.scripts.generator import ScriptGenerator

router = APIRouter(prefix="/api/dashboard", dependencies=[Depends(require_api_token)])


class ScriptDraftRequest(BaseModel):
    idea_id: str


class ProductionRequest(BaseModel):
    script_id: str


class ProductionArtifactRequest(BaseModel):
    artifact_uri: str = Field(min_length=1, max_length=2000)


class PublishRequestIn(BaseModel):
    production_id: str
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    scheduled_at: datetime | None = None


class PublishStatusRequest(BaseModel):
    status: str
    external_id: str | None = Field(default=None, min_length=1, max_length=200)


class StatusRequest(BaseModel):
    status: str


class MetricsIn(BaseModel):
    external_video_id: str = Field(min_length=1, max_length=100)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    views: int = Field(default=0, ge=0)
    watch_time_minutes: float = Field(default=0, ge=0)
    average_view_duration_seconds: float = Field(default=0, ge=0)
    impressions: int = Field(default=0, ge=0)
    click_through_rate: float = Field(default=0, ge=0, le=100)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    subscribers_gained: int = Field(default=0, ge=0)
    revenue: float = Field(default=0, ge=0)


class LearningIn(BaseModel):
    source_video_id: str | None = None
    signal_type: str = Field(min_length=1, max_length=50)
    observation: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(default=0.5, ge=0, le=1)


class AutomationIn(BaseModel):
    job_type: str = Field(min_length=1, max_length=100)
    payload: dict = Field(default_factory=dict)


def _insert(connection, sql: str, params: dict) -> None:
    execute(connection, sql, params)
    connection.commit()


def _json_rows(connection, sql: str, params: dict | None = None) -> list[dict]:
    output = []
    for row in rows(connection, sql, params):
        item = dict(row)
        for key in ("tags_json", "payload_json", "asset_paths_json"):
            if key in item:
                try:
                    item[key[:-5]] = json.loads(item.pop(key) or "[]")
                except json.JSONDecodeError:
                    item[key[:-5]] = []
        output.append(item)
    return output


def _require(connection, sql: str, params: dict, message: str):
    result = one(connection, sql, params)
    if not result:
        raise HTTPException(404, message)
    return result


def _set_status(connection, table: str, key: str, keycol: str, status: str, allowed: set[str]) -> str:
    if status not in allowed:
        raise HTTPException(422, "Invalid status")
    current = _require(
        connection,
        f"SELECT status FROM {table} WHERE {keycol}=:id",
        {"id": key},
        f"{table} record not found",
    )
    current_status = current["status"]
    if status == current_status:
        return current_status
    transitions = {
        "DRAFT": {"SCHEDULED", "FAILED"},
        "SCHEDULED": {"PUBLISHED", "FAILED", "DRAFT"},
        "PUBLISHED": set(),
        "FAILED": {"DRAFT"},
        "QUEUED": {"ASSETS", "FAILED"},
        "ASSETS": {"RENDERING", "FAILED"},
        "RENDERING": {"READY", "FAILED"},
        "READY": set(),
        "RUNNING": {"SUCCEEDED", "FAILED"},
        "SUCCEEDED": set(),
    }
    if status not in transitions.get(current_status, set()):
        raise HTTPException(409, f"Invalid transition: {current_status} -> {status}")
    _insert(
        connection,
        f"UPDATE {table} SET status=:status WHERE {keycol}=:id",
        {"status": status, "id": key},
    )
    return status


@router.get("/scripts")
def scripts():
    connection = get_connection()
    try:
        prepare_database(connection)
        output = []
        for row in rows(
            connection,
            "SELECT script_id,idea_id,title,hook,sections_json,closing,fact_check_json,version,created_at FROM content_scripts ORDER BY created_at DESC",
        ):
            item = dict(row)
            item["sections"] = json.loads(item.pop("sections_json") or "[]")
            item["fact_check_required"] = json.loads(item.pop("fact_check_json") or "[]")
            output.append(item)
        return output
    finally:
        connection.close()


@router.post("/scripts/draft")
def create_script(request: ScriptDraftRequest):
    connection = get_connection()
    try:
        prepare_database(connection)
        idea = dict(
            _require(
                connection,
                "SELECT * FROM content_ideas WHERE idea_id=:id",
                {"id": request.idea_id},
                "Idea not found",
            )
        )
        if idea["status"] != "APPROVED":
            raise HTTPException(
                409,
                f"Only APPROVED ideas can enter scripting; current status is {idea['status']}",
            )

        existing = one(
            connection,
            "SELECT script_id,version FROM content_scripts WHERE idea_id=:id ORDER BY version DESC LIMIT 1",
            {"id": request.idea_id},
        )
        version = existing["version"] + 1 if existing else 1

        evidence = [
            {
                "title": idea["title"],
                "summary": idea.get("metadata_json") or "",
                "source": idea.get("source"),
                "why_now": idea.get("why_now"),
                "research_url": None,
            }
        ]
        try:
            settings = get_settings()
            if not settings.llm_provider:
                raise RuntimeError(
                    "LLM provider is not configured. Set CONTENTOS_LLM_PROVIDER, CONTENTOS_LLM_MODEL and the provider API key."
                )
            generated = ScriptGenerator(get_llm_provider()).generate(
                idea=idea,
                evidence=evidence,
            )
            generated.version = version
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                502,
                f"Script generation failed: {type(exc).__name__}: {exc}",
            ) from exc

        now = datetime.now(timezone.utc).isoformat()
        script_id = str(uuid4())
        _insert(
            connection,
            """INSERT INTO content_scripts
            (script_id,idea_id,title,hook,sections_json,closing,fact_check_json,version,created_at)
            VALUES (:id,:idea,:title,:hook,:sections,:closing,:facts,:version,:created)""",
            {
                "id": script_id,
                "idea": request.idea_id,
                "title": generated.title,
                "hook": generated.hook,
                "sections": json.dumps([section.model_dump() for section in generated.sections]),
                "closing": generated.closing,
                "facts": json.dumps(generated.fact_check_required),
                "version": version,
                "created": now,
            },
        )
        _insert(
            connection,
            "UPDATE content_ideas SET status='SCRIPTING' WHERE idea_id=:id",
            {"id": request.idea_id},
        )
        return {
            "script_id": script_id,
            "idea_id": request.idea_id,
            "title": generated.title,
            "hook": generated.hook,
            "sections": [section.model_dump() for section in generated.sections],
            "closing": generated.closing,
            "fact_check_required": generated.fact_check_required,
            "version": version,
        }
    finally:
        connection.close()


@router.get("/production")
def production():
    connection = get_connection()
    try:
        prepare_database(connection)
        return _json_rows(connection, "SELECT * FROM production_jobs ORDER BY created_at DESC")
    finally:
        connection.close()


@router.post("/production")
def create_production(request: ProductionRequest):
    connection = get_connection()
    try:
        prepare_database(connection)
        script = _require(
            connection,
            "SELECT script_id FROM content_scripts WHERE script_id=:id",
            {"id": request.script_id},
            "Script not found",
        )
        production_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        _insert(
            connection,
            """INSERT INTO production_jobs
            (production_id,script_id,status,asset_paths_json,output_path,error,created_at)
            VALUES (:id,:script,'QUEUED',:assets,NULL,NULL,:created)""",
            {"id": production_id, "script": script["script_id"], "assets": json.dumps([]), "created": now},
        )
        return {"production_id": production_id, "script_id": script["script_id"], "status": "QUEUED"}
    finally:
        connection.close()


@router.post("/production/{production_id}/artifact")
def register_production_artifact(production_id: str, request: ProductionArtifactRequest):
    connection = get_connection()
    try:
        prepare_database(connection)
        job = _require(
            connection,
            "SELECT status FROM production_jobs WHERE production_id=:id",
            {"id": production_id},
            "production_jobs record not found",
        )
        if job["status"] != "RENDERING":
            raise HTTPException(409, "Production artifacts can only be registered while rendering")
        _insert(
            connection,
            "UPDATE production_jobs SET output_path=:artifact,error=NULL WHERE production_id=:id",
            {"artifact": request.artifact_uri, "id": production_id},
        )
        return {"production_id": production_id, "artifact_uri": request.artifact_uri, "status": "artifact_registered"}
    finally:
        connection.close()


@router.patch("/production/{production_id}/status")
def production_status(production_id: str, request: StatusRequest):
    connection = get_connection()
    try:
        prepare_database(connection)
        if request.status == "READY":
            job = _require(
                connection,
                "SELECT status,output_path FROM production_jobs WHERE production_id=:id",
                {"id": production_id},
                "production_jobs record not found",
            )
            if not job["output_path"]:
                raise HTTPException(409, "Production cannot become READY until an artifact is registered")
        status = _set_status(
            connection,
            "production_jobs",
            production_id,
            "production_id",
            request.status,
            {"QUEUED", "ASSETS", "RENDERING", "READY", "FAILED"},
        )
        return {"production_id": production_id, "status": status}
    finally:
        connection.close()


@router.get("/publishing")
def publishing():
    connection = get_connection()
    try:
        prepare_database(connection)
        return _json_rows(connection, "SELECT * FROM publish_requests ORDER BY created_at DESC")
    finally:
        connection.close()


@router.post("/publishing")
def create_publish(request: PublishRequestIn):
    connection = get_connection()
    try:
        prepare_database(connection)
        production = _require(
            connection,
            "SELECT production_id,status,output_path FROM production_jobs WHERE production_id=:id",
            {"id": request.production_id},
            "Production job not found",
        )
        if production["status"] != "READY" or not production["output_path"]:
            raise HTTPException(409, "Only READY production jobs with an artifact can be published")
        publish_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        _insert(
            connection,
            """INSERT INTO publish_requests
            (publish_id,production_id,title,description,tags_json,scheduled_at,status,external_id,created_at)
            VALUES (:id,:production,:title,:description,:tags,:scheduled,'DRAFT',NULL,:created)""",
            {
                "id": publish_id,
                "production": request.production_id,
                "title": request.title.strip(),
                "description": request.description,
                "tags": json.dumps(request.tags),
                "scheduled": request.scheduled_at,
                "created": now,
            },
        )
        return {"publish_id": publish_id, "status": "DRAFT"}
    finally:
        connection.close()


@router.patch("/publishing/{publish_id}/status")
def publish_status(publish_id: str, request: PublishStatusRequest):
    connection = get_connection()
    try:
        prepare_database(connection)
        if request.status == "PUBLISHED":
            if not request.external_id:
                raise HTTPException(409, "PUBLISHED requires the external YouTube video ID returned by the publishing adapter")
            _insert(
                connection,
                "UPDATE publish_requests SET external_id=:external_id WHERE publish_id=:id",
                {"external_id": request.external_id, "id": publish_id},
            )
        status = _set_status(
            connection,
            "publish_requests",
            publish_id,
            "publish_id",
            request.status,
            {"DRAFT", "SCHEDULED", "PUBLISHED", "FAILED"},
        )
        return {"publish_id": publish_id, "status": status, "external_id": request.external_id}
    finally:
        connection.close()


@router.get("/analytics")
def analytics():
    connection = get_connection()
    try:
        prepare_database(connection)
        return _json_rows(connection, "SELECT * FROM video_metrics ORDER BY captured_at DESC LIMIT 200")
    finally:
        connection.close()


@router.post("/analytics")
def add_metrics(request: MetricsIn):
    connection = get_connection()
    try:
        prepare_database(connection)
        metric_id = str(uuid4())
        params = request.model_dump()
        params.update({"id": metric_id, "captured": request.captured_at})
        _insert(
            connection,
            """INSERT INTO video_metrics
            (metric_id,external_video_id,captured_at,views,watch_time_minutes,average_view_duration_seconds,impressions,click_through_rate,likes,comments,subscribers_gained,revenue)
            VALUES (:id,:external_video_id,:captured,:views,:watch_time_minutes,:average_view_duration_seconds,:impressions,:click_through_rate,:likes,:comments,:subscribers_gained,:revenue)""",
            params,
        )
        return {"metric_id": metric_id, "status": "recorded"}
    finally:
        connection.close()


@router.post("/analytics/analyze/{metric_id}")
def analyze_metrics(metric_id: str):
    connection = get_connection()
    try:
        prepare_database(connection)
        row = _require(
            connection,
            "SELECT * FROM video_metrics WHERE metric_id=:id",
            {"id": metric_id},
            "Metric not found",
        )
        metrics = VideoMetrics(**dict(row))
        signals = LearningEngine().analyze(metrics)
        for signal in signals:
            _insert(
                connection,
                """INSERT INTO learning_signals
                (signal_id,source_video_id,signal_type,observation,confidence,created_at)
                VALUES (:id,:video,:type,:obs,:confidence,:created)""",
                {
                    "id": signal.signal_id,
                    "video": signal.source_video_id,
                    "type": signal.signal_type,
                    "obs": signal.observation,
                    "confidence": signal.confidence,
                    "created": signal.created_at,
                },
            )
        return {"signals": [signal.model_dump(mode="json") for signal in signals]}
    finally:
        connection.close()


@router.get("/learning")
def learning():
    connection = get_connection()
    try:
        prepare_database(connection)
        return _json_rows(connection, "SELECT * FROM learning_signals ORDER BY created_at DESC LIMIT 200")
    finally:
        connection.close()


@router.post("/learning")
def add_learning(request: LearningIn):
    connection = get_connection()
    try:
        prepare_database(connection)
        signal_id = str(uuid4())
        _insert(
            connection,
            """INSERT INTO learning_signals
            (signal_id,source_video_id,signal_type,observation,confidence,created_at)
            VALUES (:id,:video,:type,:obs,:confidence,:created)""",
            {
                "id": signal_id,
                "video": request.source_video_id,
                "type": request.signal_type,
                "obs": request.observation,
                "confidence": request.confidence,
                "created": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"signal_id": signal_id, "status": "recorded"}
    finally:
        connection.close()


@router.get("/automation")
def automation():
    connection = get_connection()
    try:
        prepare_database(connection)
        return _json_rows(connection, "SELECT * FROM automation_jobs ORDER BY created_at DESC LIMIT 200")
    finally:
        connection.close()


@router.post("/automation")
def add_automation(request: AutomationIn):
    connection = get_connection()
    try:
        prepare_database(connection)
        job_id = str(uuid4())
        _insert(
            connection,
            """INSERT INTO automation_jobs
            (job_id,job_type,payload_json,status,attempts,error,created_at)
            VALUES (:id,:type,:payload,'QUEUED',0,NULL,:created)""",
            {
                "id": job_id,
                "type": request.job_type,
                "payload": json.dumps(request.payload),
                "created": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"job_id": job_id, "status": "QUEUED"}
    finally:
        connection.close()


@router.patch("/automation/{job_id}/status")
def automation_status(job_id: str, request: StatusRequest):
    connection = get_connection()
    try:
        prepare_database(connection)
        status = _set_status(
            connection,
            "automation_jobs",
            job_id,
            "job_id",
            request.status,
            {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED"},
        )
        return {"job_id": job_id, "status": status}
    finally:
        connection.close()


@router.get("/settings")
def dashboard_settings():
    settings = get_settings()
    return {
        "environment": settings.environment,
        "database": "postgres" if using_postgres() else "sqlite",
        "database_path": settings.database_path if not using_postgres() else None,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "api_token_configured": bool(settings.api_token),
    }
