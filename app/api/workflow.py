"""Dashboard workflow APIs for scripts, production, publishing, analytics, learning and jobs."""
from datetime import datetime, timezone
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.app import require_api_token, _prepare
from app.database.connection import get_connection, using_postgres
from app.learning.engine import LearningEngine
from app.analytics.models import VideoMetrics

router = APIRouter(prefix="/api/dashboard", dependencies=[Depends(require_api_token)])


def _rows(connection, sql: str, params: dict | None = None):
    params = params or {}
    if using_postgres():
        return connection.execute(text(sql), params).mappings().all()
    converted = sql
    ordered = []
    for key in (params.keys()):
        converted = converted.replace(f":{key}", "?")
        ordered.append(params[key])
    return connection.execute(converted, tuple(ordered)).fetchall()


def _insert(connection, sql: str, params: dict):
    if using_postgres():
        connection.execute(text(sql), params)
    else:
        converted = sql
        ordered = []
        for key, value in params.items():
            converted = converted.replace(f":{key}", "?")
            ordered.append(value)
        connection.execute(converted, tuple(ordered))
    connection.commit()


class ScriptDraftRequest(BaseModel):
    idea_id: str


class ProductionRequest(BaseModel):
    script_id: str


class PublishRequestIn(BaseModel):
    production_id: str
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    scheduled_at: datetime | None = None


class StatusRequest(BaseModel):
    status: str


class MetricsIn(BaseModel):
    external_video_id: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    views: int = 0
    watch_time_minutes: float = 0
    average_view_duration_seconds: float = 0
    impressions: int = 0
    click_through_rate: float = 0
    likes: int = 0
    comments: int = 0
    subscribers_gained: int = 0
    revenue: float = 0


class LearningIn(BaseModel):
    source_video_id: str | None = None
    signal_type: str
    observation: str
    confidence: float = Field(default=.5, ge=0, le=1)


class AutomationIn(BaseModel):
    job_type: str
    payload: dict = Field(default_factory=dict)


@router.get("/scripts")
def scripts():
    c=get_connection()
    try:
        _prepare(c)
        rows=_rows(c,"SELECT script_id,idea_id,title,hook,sections_json,closing,fact_check_json,version,created_at FROM content_scripts ORDER BY created_at DESC")
        return [dict(r) | {"sections":json.loads(r["sections_json"]),"fact_check_required":json.loads(r["fact_check_json"])} for r in rows]
    finally:c.close()


@router.post("/scripts/draft")
def create_script(request: ScriptDraftRequest):
    c=get_connection()
    try:
        _prepare(c)
        idea_rows=_rows(c,"SELECT * FROM content_ideas WHERE idea_id = :id",{"id":request.idea_id})
        if not idea_rows: raise HTTPException(404,"Idea not found")
        idea=dict(idea_rows[0]); sid=str(uuid4()); now=datetime.now(timezone.utc).isoformat()
        sections=[
            {"heading":"The setup","narration":f"Today we are breaking down {idea['topic']} and why it matters.","visual_notes":"Relevant source clips, screenshots or b-roll."},
            {"heading":"What is happening","narration":idea["hook"],"visual_notes":"Show the evidence from the research source."},
            {"heading":"The important details","narration":idea.get("why_now") or "Walk through the key facts and context.","visual_notes":"Use simple diagrams, captions and supporting visuals."},
            {"heading":"What to watch next","narration":idea.get("monetization_angle") or "Close with the practical implication for the viewer.","visual_notes":"End card and next-video prompt."},
        ]
        fact=["Verify every factual claim against the source evidence before publishing."]
        _insert(c,"""INSERT INTO content_scripts(script_id,idea_id,title,hook,sections_json,closing,fact_check_json,version,created_at) VALUES (:sid,:idea,:title,:hook,:sections,:closing,:facts,:version,:created)""",{"sid":sid,"idea":request.idea_id,"title":idea["title"],"hook":idea["hook"],"sections":json.dumps(sections),"closing":"If this was useful, subscribe for the next breakdown.","facts":json.dumps(fact),"version":1,"created":now})
        _insert(c,"UPDATE content_ideas SET status = :status WHERE idea_id = :id",{"status":"SCRIPTING","id":request.idea_id})
        return {"script_id":sid,"idea_id":request.idea_id,"title":idea["title"],"hook":idea["hook"],"sections":sections,"closing":"If this was useful, subscribe for the next breakdown.","fact_check_required":fact,"version":1}
    finally:c.close()


@router.get("/production")
def production():
    c=get_connection()
    try:
        _prepare(c); rows=_rows(c,"SELECT * FROM production_jobs ORDER BY created_at DESC")
        return [dict(r)|{"asset_paths":json.loads(r["asset_paths_json"])} for r in rows]
    finally:c.close()


@router.post("/production")
def create_production(request: ProductionRequest):
    c=get_connection()
    try:
        _prepare(c); sid=request.script_id
        if not _rows(c,"SELECT script_id FROM content_scripts WHERE script_id = :id",{"id":sid}): raise HTTPException(404,"Script not found")
        pid=str(uuid4());now=datetime.now(timezone.utc).isoformat()
        _insert(c,"""INSERT INTO production_jobs(production_id,script_id,status,asset_paths_json,output_path,error,created_at) VALUES (:id,:script,'QUEUED',:assets,NULL,NULL,:created)""",{"id":pid,"script":sid,"assets":json.dumps([]),"created":now})
        return {"production_id":pid,"script_id":sid,"status":"QUEUED"}
    finally:c.close()


@router.patch("/production/{production_id}/status")
def production_status(production_id:str,request:StatusRequest):
    allowed={"QUEUED","ASSETS","RENDERING","READY","FAILED"}
    if request.status not in allowed: raise HTTPException(422,"Invalid production status")
    c=get_connection()
    try:
        _prepare(c); _insert(c,"UPDATE production_jobs SET status=:status WHERE production_id=:id",{"status":request.status,"id":production_id}); return {"production_id":production_id,"status":request.status}
    finally:c.close()


@router.get("/publishing")
def publishing():
    c=get_connection()
    try:
        _prepare(c);rows=_rows(c,"SELECT * FROM publish_requests ORDER BY created_at DESC")
        return [dict(r)|{"tags":json.loads(r["tags_json"])} for r in rows]
    finally:c.close()


@router.post("/publishing")
def create_publish(request:PublishRequestIn):
    c=get_connection()
    try:
        _prepare(c);pid=str(uuid4());now=datetime.now(timezone.utc).isoformat()
        _insert(c,"""INSERT INTO publish_requests(publish_id,production_id,title,description,tags_json,scheduled_at,status,external_id,created_at) VALUES (:id,:production,:title,:description,:tags,:scheduled,'DRAFT',NULL,:created)""",{"id":pid,"production":request.production_id,"title":request.title,"description":request.description,"tags":json.dumps(request.tags),"scheduled":request.scheduled_at,"created":now})
        return {"publish_id":pid,"status":"DRAFT"}
    finally:c.close()


@router.patch("/publishing/{publish_id}/status")
def publish_status(publish_id:str,request:StatusRequest):
    if request.status not in {"DRAFT","SCHEDULED","PUBLISHED","FAILED"}: raise HTTPException(422,"Invalid publishing status")
    c=get_connection()
    try:
        _prepare(c);_insert(c,"UPDATE publish_requests SET status=:status WHERE publish_id=:id",{"status":request.status,"id":publish_id});return {"publish_id":publish_id,"status":request.status}
    finally:c.close()


@router.get("/analytics")
def analytics():
    c=get_connection()
    try:
        _prepare(c);rows=_rows(c,"SELECT * FROM video_metrics ORDER BY captured_at DESC LIMIT 200");return [dict(r) for r in rows]
    finally:c.close()


@router.post("/analytics")
def add_metrics(request:MetricsIn):
    c=get_connection()
    try:
        _prepare(c);mid=str(uuid4());_insert(c,"""INSERT INTO video_metrics(metric_id,external_video_id,captured_at,views,watch_time_minutes,average_view_duration_seconds,impressions,click_through_rate,likes,comments,subscribers_gained,revenue) VALUES (:id,:video,:captured,:views,:watch,:avd,:impressions,:ctr,:likes,:comments,:subs,:revenue)""",request.model_dump()|{"id":mid,"captured":request.captured_at});return {"metric_id":mid,"status":"recorded"}
    finally:c.close()


@router.post("/analytics/analyze/{metric_id}")
def analyze_metrics(metric_id:str):
    c=get_connection()
    try:
        _prepare(c);rows=_rows(c,"SELECT * FROM video_metrics WHERE metric_id=:id",{"id":metric_id})
        if not rows: raise HTTPException(404,"Metric not found")
        m=VideoMetrics(**dict(rows[0]));signals=LearningEngine().analyze(m)
        for s in signals:
            _insert(c,"""INSERT INTO learning_signals(signal_id,source_video_id,signal_type,observation,confidence,created_at) VALUES (:id,:video,:type,:obs,:confidence,:created)""",{"id":s.signal_id,"video":s.source_video_id,"type":s.signal_type,"obs":s.observation,"confidence":s.confidence,"created":s.created_at})
        return {"signals":[s.model_dump(mode="json") for s in signals]}
    finally:c.close()


@router.get("/learning")
def learning():
    c=get_connection()
    try:
        _prepare(c);rows=_rows(c,"SELECT * FROM learning_signals ORDER BY created_at DESC LIMIT 200");return [dict(r) for r in rows]
    finally:c.close()


@router.post("/learning")
def add_learning(request:LearningIn):
    c=get_connection()
    try:
        _prepare(c);sid=str(uuid4());now=datetime.now(timezone.utc).isoformat();_insert(c,"""INSERT INTO learning_signals(signal_id,source_video_id,signal_type,observation,confidence,created_at) VALUES (:id,:video,:type,:obs,:confidence,:created)""",{"id":sid,"video":request.source_video_id,"type":request.signal_type,"obs":request.observation,"confidence":request.confidence,"created":now});return {"signal_id":sid,"status":"recorded"}
    finally:c.close()


@router.get("/automation")
def automation():
    c=get_connection()
    try:
        _prepare(c);rows=_rows(c,"SELECT * FROM automation_jobs ORDER BY created_at DESC LIMIT 200");return [dict(r)|{"payload":json.loads(r["payload_json"])} for r in rows]
    finally:c.close()


@router.post("/automation")
def add_automation(request:AutomationIn):
    c=get_connection()
    try:
        _prepare(c);jid=str(uuid4());now=datetime.now(timezone.utc).isoformat();_insert(c,"""INSERT INTO automation_jobs(job_id,job_type,payload_json,status,attempts,error,created_at) VALUES (:id,:type,:payload,'QUEUED',0,NULL,:created)""",{"id":jid,"type":request.job_type,"payload":json.dumps(request.payload),"created":now});return {"job_id":jid,"status":"QUEUED"}
    finally:c.close()


@router.patch("/automation/{job_id}/status")
def automation_status(job_id:str,request:StatusRequest):
    if request.status not in {"QUEUED","RUNNING","SUCCEEDED","FAILED"}: raise HTTPException(422,"Invalid job status")
    c=get_connection()
    try:
        _prepare(c);_insert(c,"UPDATE automation_jobs SET status=:status WHERE job_id=:id",{"status":request.status,"id":job_id});return {"job_id":job_id,"status":request.status}
    finally:c.close()


@router.get("/settings")
def dashboard_settings():
    from app.config.settings import get_settings
    s=get_settings();return {"environment":s.environment,"database":"postgres" if using_postgres() else "sqlite","database_path":s.database_path if not using_postgres() else None,"llm_provider":s.llm_provider,"llm_model":s.llm_model,"api_token_configured":bool(s.api_token)}
