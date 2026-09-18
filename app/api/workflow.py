"""Dashboard workflow APIs with explicit lifecycle boundaries."""

from datetime import datetime, timezone
import json
from uuid import uuid4

from app.automation.scheduler import run_queued_jobs
from app.automation.handlers import HANDLERS

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.analytics.models import VideoMetrics
from app.api.common import execute, one, prepare_database, require_api_token, rows
from app.config.settings import get_settings
from app.database.connection import get_connection, using_postgres
from app.learning.engine import LearningEngine
from app.llm.factory import get_llm_provider
from app.scripts.generator import ScriptGenerator
from pathlib import Path
from app.integrations.artifacts import materialize_artifact
from app.integrations.youtube import YouTubeProvider
from app.integrations.youtube_oauth import load_server_credentials

router = APIRouter(prefix="/api/dashboard", dependencies=[Depends(require_api_token)])

class ScriptDraftRequest(BaseModel): idea_id: str
class ProductionRequest(BaseModel):
    script_id: str
    asset_uris: list[str] = Field(default_factory=list, max_length=50)
class ProductionArtifactRequest(BaseModel): artifact_uri: str = Field(min_length=1, max_length=2000)
class PublishRequestIn(BaseModel):
    production_id: str; title: str = Field(min_length=1, max_length=200); description: str = ""; tags: list[str] = Field(default_factory=list); scheduled_at: datetime | None = None
class PublishStatusRequest(BaseModel):
    status: str; external_id: str | None = Field(default=None, min_length=1, max_length=200)
class YouTubePublishRequest(BaseModel):
    privacy_status: str = Field(default="private", pattern="^(private|unlisted|public)$")
    category_id: str = Field(default="22", min_length=1, max_length=10)
class StatusRequest(BaseModel): status: str
class MetricsIn(BaseModel):
    external_video_id: str = Field(min_length=1, max_length=100); captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc)); views: int = Field(default=0, ge=0); watch_time_minutes: float = Field(default=0, ge=0); average_view_duration_seconds: float = Field(default=0, ge=0); impressions: int = Field(default=0, ge=0); click_through_rate: float = Field(default=0, ge=0, le=100); likes: int = Field(default=0, ge=0); comments: int = Field(default=0, ge=0); subscribers_gained: int = Field(default=0, ge=0); revenue: float = Field(default=0, ge=0)
class LearningIn(BaseModel):
    source_video_id: str | None = None; signal_type: str = Field(min_length=1, max_length=50); observation: str = Field(min_length=1, max_length=2000); confidence: float = Field(default=.5, ge=0, le=1)
class AutomationIn(BaseModel): job_type: str = Field(min_length=1, max_length=100); payload: dict = Field(default_factory=dict)


def _insert(c, sql, p): execute(c, sql, p); c.commit()
def _json_rows(c, sql, p=None): return [dict(r) for r in rows(c, sql, p)]
def _require(c, sql, p, message):
    r = one(c, sql, p)
    if not r: raise HTTPException(404, message)
    return r


def _validate_status_transition(current_status, status, allowed):
    if status not in allowed:
        raise HTTPException(422, "Invalid status")
    if status == current_status:
        return
    transitions = {"DRAFT":{"SCHEDULED","FAILED"},"SCHEDULED":{"PUBLISHED","FAILED","DRAFT"},"PUBLISHED":set(),"FAILED":{"DRAFT","QUEUED"},"QUEUED":{"ASSETS","FAILED"},"ASSETS":{"RENDERING","FAILED"},"RENDERING":{"READY","FAILED"},"READY":set(),"RUNNING":{"SUCCEEDED","FAILED"},"SUCCEEDED":set()}
    if status not in transitions.get(current_status, set()):
        raise HTTPException(409, f"Invalid transition: {current_status} -> {status}")


def _set_status(c, table, key, keycol, status, allowed):
    current = _require(c, f"SELECT status FROM {table} WHERE {keycol}=:id", {"id": key}, f"{table} record not found")
    current_status = current["status"]
    _validate_status_transition(current_status, status, allowed)
    if status == current_status:
        return current_status
    _insert(c, f"UPDATE {table} SET status=:status WHERE {keycol}=:id", {"status": status, "id": key})
    return status

@router.post("/admin/reset-demo")
def reset_demo_data():
    """Clear all ContentOS V0 data so a new end-to-end demo starts clean."""
    c = get_connection()
    try:
        prepare_database(c)
        tables = ("learning_signals", "video_metrics", "publish_requests", "production_jobs", "content_scripts", "content_ideas", "research_items", "automation_jobs")
        for table in tables:
            execute(c, f"DELETE FROM {table}")
        c.commit()
        return {"status": "reset", "tables_cleared": list(tables)}
    finally:
        c.close()

@router.get("/scripts")
def scripts():
    c = get_connection()
    try:
        prepare_database(c); out=[]
        for r in rows(c,"SELECT script_id,idea_id,title,hook,sections_json,closing,fact_check_json,version,created_at FROM content_scripts ORDER BY created_at DESC"):
            d=dict(r); d["sections"]=json.loads(d.pop("sections_json") or "[]"); d["fact_check_required"]=json.loads(d.pop("fact_check_json") or "[]"); out.append(d)
        return out
    finally: c.close()

@router.post("/scripts/draft")
def create_script(request: ScriptDraftRequest):
    c = get_connection()
    try:
        prepare_database(c)
        idea = dict(_require(c,"SELECT * FROM content_ideas WHERE idea_id=:id",{"id":request.idea_id},"Idea not found"))
        if idea["status"] != "APPROVED": raise HTTPException(409,f"Only APPROVED ideas can enter scripting; current status is {idea['status']}")
        existing = one(c,"SELECT script_id,version FROM content_scripts WHERE idea_id=:id ORDER BY version DESC LIMIT 1",{"id":request.idea_id}); version=existing["version"]+1 if existing else 1
        evidence=[{"title":idea["title"],"summary":idea.get("metadata_json") or "","source":idea.get("source"),"why_now":idea.get("why_now"),"research_url":None}]
        try:
            settings=get_settings()
            if not settings.llm_provider: raise RuntimeError("LLM provider is not configured. Set CONTENTOS_LLM_PROVIDER, CONTENTOS_LLM_MODEL and the provider API key.")
            generated=ScriptGenerator(get_llm_provider()).generate(idea=idea,evidence=evidence); generated.version=version
        except HTTPException: raise
        except Exception as exc: raise HTTPException(502,f"Script generation failed: {type(exc).__name__}: {exc}") from exc
        now=datetime.now(timezone.utc).isoformat(); sid=str(uuid4())
        _insert(c,"INSERT INTO content_scripts(script_id,idea_id,title,hook,sections_json,closing,fact_check_json,version,created_at) VALUES (:id,:idea,:title,:hook,:sections,:closing,:facts,:version,:created)",{"id":sid,"idea":request.idea_id,"title":generated.title,"hook":generated.hook,"sections":json.dumps([s.model_dump() for s in generated.sections]),"closing":generated.closing,"facts":json.dumps(generated.fact_check_required),"version":version,"created":now})
        _insert(c,"UPDATE content_ideas SET status='SCRIPTING' WHERE idea_id=:id",{"id":request.idea_id})
        return {"script_id":sid,"idea_id":request.idea_id,"title":generated.title,"hook":generated.hook,"sections":[s.model_dump() for s in generated.sections],"closing":generated.closing,"fact_check_required":generated.fact_check_required,"version":version}
    finally: c.close()

@router.get("/production")
def production():
    c=get_connection()
    try: prepare_database(c); return _json_rows(c,"SELECT * FROM production_jobs ORDER BY created_at DESC")
    finally: c.close()

@router.post("/production")
def create_production(request: ProductionRequest):
    c=get_connection()
    try:
        prepare_database(c); s=_require(c,"SELECT script_id FROM content_scripts WHERE script_id=:id",{"id":request.script_id},"Script not found"); pid=str(uuid4()); now=datetime.now(timezone.utc).isoformat()
        _insert(c,"INSERT INTO production_jobs(production_id,script_id,status,asset_paths_json,output_path,error,created_at) VALUES (:id,:script,'QUEUED',:assets,NULL,NULL,:created)",{"id":pid,"script":s["script_id"],"assets":json.dumps(request.asset_uris),"created":now}); return {"production_id":pid,"script_id":s["script_id"],"status":"QUEUED","assets":request.asset_uris}
    finally: c.close()

@router.post("/production/{production_id}/artifact")
def register_production_artifact(production_id: str, request: ProductionArtifactRequest):
    c=get_connection()
    try:
        prepare_database(c); job=_require(c,"SELECT status FROM production_jobs WHERE production_id=:id",{"id":production_id},"production_jobs record not found")
        if job["status"] != "RENDERING": raise HTTPException(409,"Production artifacts can only be registered while rendering")
        _insert(c,"UPDATE production_jobs SET output_path=:artifact,error=NULL WHERE production_id=:id",{"artifact":request.artifact_uri,"id":production_id})
        return {"production_id":production_id,"artifact_uri":request.artifact_uri,"status":"artifact_registered"}
    finally: c.close()

@router.patch("/production/{production_id}/status")
def production_status(production_id: str, request: StatusRequest):
    c=get_connection()
    try:
        prepare_database(c)
        job=_require(c,"SELECT status,output_path FROM production_jobs WHERE production_id=:id",{"id":production_id},"production_jobs record not found")
        # Validate the lifecycle transition before checking status-specific
        # prerequisites, without mutating the row until all prerequisites pass.
        _validate_status_transition(job["status"], request.status, {"QUEUED","ASSETS","RENDERING","READY","FAILED"})
        if request.status == "READY" and not job["output_path"]:
            raise HTTPException(409,"Production cannot become READY until an artifact is registered")
        status=_set_status(c,"production_jobs",production_id,"production_id",request.status,{"QUEUED","ASSETS","RENDERING","READY","FAILED"})
        return {"production_id":production_id,"status":status}
    finally: c.close()

@router.get("/publishing")
def publishing():
    c=get_connection()
    try: prepare_database(c); return _json_rows(c,"SELECT * FROM publish_requests ORDER BY created_at DESC")
    finally: c.close()

@router.post("/publishing")
def create_publish(request: PublishRequestIn):
    c=get_connection()
    try:
        prepare_database(c); p=_require(c,"SELECT production_id,status,output_path FROM production_jobs WHERE production_id=:id",{"id":request.production_id},"Production job not found")
        if p["status"]!="READY" or not p["output_path"]: raise HTTPException(409,"Only READY production jobs with an artifact can be published")
        pid=str(uuid4()); now=datetime.now(timezone.utc).isoformat()
        _insert(c,"INSERT INTO publish_requests(publish_id,production_id,title,description,tags_json,scheduled_at,status,external_id,created_at) VALUES (:id,:production,:title,:description,:tags,:scheduled,'DRAFT',NULL,:created)",{"id":pid,"production":request.production_id,"title":request.title.strip(),"description":request.description,"tags":json.dumps(request.tags),"scheduled":request.scheduled_at,"created":now}); return {"publish_id":pid,"status":"DRAFT"}
    finally: c.close()

@router.post("/publishing/{publish_id}/youtube")
def publish_to_youtube(publish_id: str, request: YouTubePublishRequest):
    """Upload a READY production artifact to YouTube and persist its video ID."""
    credentials = load_server_credentials()
    if credentials is None:
        raise HTTPException(503, "YouTube publishing is not configured. Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN on the server.")
    c = get_connection()
    try:
        prepare_database(c)
        record = _require(c,
            "SELECT p.publish_id,p.production_id,p.title,p.description,p.tags_json,p.status,p.external_id,j.output_path FROM publish_requests p JOIN production_jobs j ON j.production_id=p.production_id WHERE p.publish_id=:id",
            {"id": publish_id}, "publish_requests record not found")
        if record["status"] == "PUBLISHED":
            return {
                "publish_id": publish_id, "status": "PUBLISHED", "external_id": record["external_id"],
                "youtube_url": "https://www.youtube.com/watch?v=" + str(record["external_id"])
            }
        if record["status"] != "DRAFT":
            raise HTTPException(409, "Only DRAFT publish records can be uploaded to YouTube")
        if not record["output_path"]:
            raise HTTPException(409, "Production artifact is missing")
        artifact = str(record["output_path"])
        local_artifact = None
        temporary_artifact = False
        try:
            local_artifact, temporary_artifact = materialize_artifact(artifact)
            tags = json.loads(record["tags_json"] or "[]")
            if not isinstance(tags, list):
                tags = []
            response = YouTubeProvider(credentials).upload_video(
                local_artifact,
                title=record["title"],
                description=record["description"] or "",
                tags=[str(tag) for tag in tags],
                privacy_status=request.privacy_status,
                category_id=request.category_id,
            )
            video_id = response.get("id")
            if not video_id:
                raise RuntimeError("YouTube upload completed without returning a video ID")
        except FileNotFoundError as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502, f"YouTube upload failed: {type(exc).__name__}: {exc}") from exc
        finally:
            if temporary_artifact and local_artifact:
                Path(local_artifact).unlink(missing_ok=True)
        _insert(c, "UPDATE publish_requests SET external_id=:external_id,status='PUBLISHED' WHERE publish_id=:id", {"external_id": video_id, "id": publish_id})
        return {
            "publish_id": publish_id, "status": "PUBLISHED", "external_id": video_id,
            "youtube_url": "https://www.youtube.com/watch?v=" + str(video_id)
        }
    finally:
        c.close()
@router.patch("/publishing/{publish_id}/status")
def publish_status(publish_id: str, request: PublishStatusRequest):
    c=get_connection()
    try:
        prepare_database(c)
        current=_require(c,"SELECT status,external_id FROM publish_requests WHERE publish_id=:id",{"id":publish_id},"publish_requests record not found")
        if request.status == "PUBLISHED" and not request.external_id:
            raise HTTPException(409,"PUBLISHED requires the external YouTube video ID returned by the publishing adapter")
        if request.status == "PUBLISHED":
            _insert(c,"UPDATE publish_requests SET external_id=:external_id WHERE publish_id=:id",{"external_id":request.external_id,"id":publish_id})
        status=_set_status(c,"publish_requests",publish_id,"publish_id",request.status,{"DRAFT","SCHEDULED","PUBLISHED","FAILED"})
        return {"publish_id":publish_id,"status":status,"external_id":request.external_id or current["external_id"]}
    finally: c.close()

@router.get("/analytics")
def analytics():
    c=get_connection()
    try: prepare_database(c); return _json_rows(c,"SELECT * FROM video_metrics ORDER BY captured_at DESC LIMIT 200")
    finally: c.close()
@router.post("/analytics")
def add_metrics(request: MetricsIn):
    c=get_connection()
    try:
        prepare_database(c); mid=str(uuid4()); p=request.model_dump(); p.update({"id":mid,"captured":request.captured_at}); _insert(c,"INSERT INTO video_metrics(metric_id,external_video_id,captured_at,views,watch_time_minutes,average_view_duration_seconds,impressions,click_through_rate,likes,comments,subscribers_gained,revenue) VALUES (:id,:external_video_id,:captured,:views,:watch_time_minutes,:average_view_duration_seconds,:impressions,:click_through_rate,:likes,:comments,:subscribers_gained,:revenue)",p); return {"metric_id":mid,"status":"recorded"}
    finally: c.close()
@router.post("/analytics/analyze/{metric_id}")
def analyze_metrics(metric_id: str):
    c=get_connection()
    try:
        prepare_database(c); r=_require(c,"SELECT * FROM video_metrics WHERE metric_id=:id",{"id":metric_id},"Metric not found"); m=VideoMetrics(**dict(r)); signals=LearningEngine().analyze(m)
        for s in signals: _insert(c,"INSERT INTO learning_signals(signal_id,source_video_id,signal_type,observation,confidence,created_at) VALUES (:id,:video,:type,:obs,:confidence,:created)",{"id":s.signal_id,"video":s.source_video_id,"type":s.signal_type,"obs":s.observation,"confidence":s.confidence,"created":s.created_at})
        return {"signals":[s.model_dump(mode="json") for s in signals]}
    finally: c.close()
@router.get("/learning")
def learning():
    c=get_connection()
    try: prepare_database(c); return _json_rows(c,"SELECT * FROM learning_signals ORDER BY created_at DESC LIMIT 200")
    finally: c.close()
@router.post("/learning")
def add_learning(request: LearningIn):
    c=get_connection()
    try:
        prepare_database(c); sid=str(uuid4()); _insert(c,"INSERT INTO learning_signals(signal_id,source_video_id,signal_type,observation,confidence,created_at) VALUES (:id,:video,:type,:obs,:confidence,:created)",{"id":sid,"video":request.source_video_id,"type":request.signal_type,"obs":request.observation,"confidence":request.confidence,"created":datetime.now(timezone.utc).isoformat()}); return {"signal_id":sid,"status":"recorded"}
    finally: c.close()
@router.post("/automation/run")
def run_automation():
    """Execute queued automation jobs synchronously within this invocation."""
    if not get_settings().api_token:
        raise HTTPException(503, "Automation execution requires CONTENTOS_API_TOKEN")
    return run_queued_jobs(HANDLERS)


@router.get("/automation")
def automation():
    c=get_connection()
    try: prepare_database(c); return _json_rows(c,"SELECT * FROM automation_jobs ORDER BY created_at DESC LIMIT 200")
    finally: c.close()
@router.post("/automation")
def add_automation(request: AutomationIn):
    c=get_connection()
    try:
        prepare_database(c); jid=str(uuid4()); _insert(c,"INSERT INTO automation_jobs(job_id,job_type,payload_json,status,attempts,error,created_at) VALUES (:id,:type,:payload,'QUEUED',0,NULL,:created)",{"id":jid,"type":request.job_type,"payload":json.dumps(request.payload),"created":datetime.now(timezone.utc).isoformat()}); return {"job_id":jid,"status":"QUEUED"}
    finally: c.close()
@router.patch("/automation/{job_id}/status")
def automation_status(job_id:str,request:StatusRequest):
    c=get_connection()
    try:
        prepare_database(c); status=_set_status(c,"automation_jobs",job_id,"job_id",request.status,{"QUEUED","RUNNING","SUCCEEDED","FAILED"}); return {"job_id":job_id,"status":status}
    finally: c.close()
@router.get("/settings")
def dashboard_settings():
    s=get_settings(); return {"environment":s.environment,"database":"postgres" if using_postgres() else "sqlite","database_path":s.database_path if not using_postgres() else None,"llm_provider":s.llm_provider,"llm_model":s.llm_model,"api_token_configured":bool(s.api_token)}
