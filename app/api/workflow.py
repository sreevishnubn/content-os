"""Dashboard workflow APIs with enforced lifecycle and record integrity."""
from datetime import datetime, timezone
import json
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from app.api.common import require_api_token, prepare_database, rows, one, execute
from app.database.connection import get_connection, using_postgres
from app.learning.engine import LearningEngine
from app.analytics.models import VideoMetrics

router=APIRouter(prefix="/api/dashboard",dependencies=[Depends(require_api_token)])
class ScriptDraftRequest(BaseModel): idea_id:str
class ProductionRequest(BaseModel): script_id:str
class PublishRequestIn(BaseModel):
    production_id:str; title:str=Field(min_length=1,max_length=200); description:str=""; tags:list[str]=Field(default_factory=list); scheduled_at:datetime|None=None
class StatusRequest(BaseModel): status:str
class MetricsIn(BaseModel):
    external_video_id:str=Field(min_length=1,max_length=100); captured_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc)); views:int=Field(default=0,ge=0); watch_time_minutes:float=Field(default=0,ge=0); average_view_duration_seconds:float=Field(default=0,ge=0); impressions:int=Field(default=0,ge=0); click_through_rate:float=Field(default=0,ge=0,le=100); likes:int=Field(default=0,ge=0); comments:int=Field(default=0,ge=0); subscribers_gained:int=Field(default=0,ge=0); revenue:float=Field(default=0,ge=0)
class LearningIn(BaseModel): source_video_id:str|None=None; signal_type:str=Field(min_length=1,max_length=50); observation:str=Field(min_length=1,max_length=2000); confidence:float=Field(default=.5,ge=0,le=1)
class AutomationIn(BaseModel): job_type:str=Field(min_length=1,max_length=100); payload:dict=Field(default_factory=dict)

def _insert(c,sql,p): execute(c,sql,p); c.commit()
def _json_rows(c,sql,p=None): return [dict(r) for r in rows(c,sql,p)]
def _require(c,sql,p,message):
    r=one(c,sql,p)
    if not r: raise HTTPException(404,message)
    return r

def _set_status(c,table,key,keycol,status,allowed):
    if status not in allowed: raise HTTPException(422,"Invalid status")
    current=_require(c,f"SELECT status FROM {table} WHERE {keycol}=:id",{"id":key},f"{table} record not found")
    if status==current["status"]: return
    transitions={"DRAFT":{"SCHEDULED","FAILED"},"SCHEDULED":{"PUBLISHED","FAILED","DRAFT"},"PUBLISHED":set(),"FAILED":{"DRAFT"},"QUEUED":{"ASSETS","FAILED"},"ASSETS":{"RENDERING","FAILED"},"RENDERING":{"READY","FAILED"},"READY":set(),"RUNNING":{"SUCCEEDED","FAILED"},"SUCCEEDED":set()}
    if status not in transitions.get(current["status"],set()): raise HTTPException(409,f"Invalid transition: {current['status']} -> {status}")
    _insert(c,f"UPDATE {table} SET status=:status WHERE {keycol}=:id",{"status":status,"id":key})

@router.get("/scripts")
def scripts():
    c=get_connection()
    try:
        prepare_database(c); out=[]
        for r in rows(c,"SELECT script_id,idea_id,title,hook,sections_json,closing,fact_check_json,version,created_at FROM content_scripts ORDER BY created_at DESC"):
            d=dict(r); d["sections"]=json.loads(d.pop("sections_json")); d["fact_check_required"]=json.loads(d.pop("fact_check_json")); out.append(d)
        return out
    finally:c.close()

@router.post("/scripts/draft")
def create_script(request:ScriptDraftRequest):
    c=get_connection()
    try:
        prepare_database(c); idea=_require(c,"SELECT * FROM content_ideas WHERE idea_id=:id",{"id":request.idea_id},"Idea not found")
        if idea["status"]!="APPROVED": raise HTTPException(409,f"Only APPROVED ideas can enter scripting; current status is {idea['status']}")
        existing=one(c,"SELECT script_id,version FROM content_scripts WHERE idea_id=:id ORDER BY version DESC LIMIT 1",{"id":request.idea_id}); version=(existing["version"]+1 if existing else 1); sid=str(uuid4()); now=datetime.now(timezone.utc).isoformat()
        sections=[{"heading":"The setup","narration":f"Today we are breaking down {idea['topic']} and why it matters.","visual_notes":"Relevant source clips, screenshots or b-roll."},{"heading":"What is happening","narration":idea["hook"],"visual_notes":"Show evidence from the research source."},{"heading":"The important details","narration":idea.get("why_now") or "Walk through the key facts and context.","visual_notes":"Use diagrams, captions and supporting visuals."},{"heading":"What to watch next","narration":idea.get("monetization_angle") or "Close with the practical implication for the viewer.","visual_notes":"End card and next-video prompt."}]
        _insert(c,"INSERT INTO content_scripts(script_id,idea_id,title,hook,sections_json,closing,fact_check_json,version,created_at) VALUES (:sid,:idea,:title,:hook,:sections,:closing,:facts,:version,:created)",{"sid":sid,"idea":request.idea_id,"title":idea["title"],"hook":idea["hook"],"sections":json.dumps(sections),"closing":"If this was useful, subscribe for the next breakdown.","facts":json.dumps(["Verify every factual claim against source evidence before publishing."]),"version":version,"created":now})
        execute(c,"UPDATE content_ideas SET status='SCRIPTING' WHERE idea_id=:id",{"id":request.idea_id}); c.commit()
        return {"script_id":sid,"idea_id":request.idea_id,"title":idea["title"],"hook":idea["hook"],"sections":sections,"closing":"If this was useful, subscribe for the next breakdown.","fact_check_required":["Verify every factual claim against source evidence before publishing."],"version":version}
    finally:c.close()

@router.get("/production")
def production():
    c=get_connection()
    try: prepare_database(c); return _json_rows(c,"SELECT * FROM production_jobs ORDER BY created_at DESC")
    finally:c.close()
@router.post("/production")
def create_production(request:ProductionRequest):
    c=get_connection()
    try:
        prepare_database(c); s=_require(c,"SELECT script_id FROM content_scripts WHERE script_id=:id",{"id":request.script_id},"Script not found"); pid=str(uuid4()); now=datetime.now(timezone.utc).isoformat(); _insert(c,"INSERT INTO production_jobs(production_id,script_id,status,asset_paths_json,output_path,error,created_at) VALUES (:id,:script,'QUEUED',:assets,NULL,NULL,:created)",{"id":pid,"script":s["script_id"],"assets":json.dumps([]),"created":now}); return {"production_id":pid,"script_id":s["script_id"],"status":"QUEUED"}
    finally:c.close()
@router.patch("/production/{production_id}/status")
def production_status(production_id:str,request:StatusRequest):
    c=get_connection()
    try: prepare_database(c); _set_status(c,"production_jobs",production_id,"production_id",request.status,{"QUEUED","ASSETS","RENDERING","READY","FAILED"}); return {"production_id":production_id,"status":request.status}
    finally:c.close()

@router.get("/publishing")
def publishing():
    c=get_connection()
    try: prepare_database(c); return _json_rows(c,"SELECT * FROM publish_requests ORDER BY created_at DESC")
    finally:c.close()
@router.post("/publishing")
def create_publish(request:PublishRequestIn):
    c=get_connection()
    try:
        prepare_database(c); p=_require(c,"SELECT production_id,status,output_path FROM production_jobs WHERE production_id=:id",{"id":request.production_id},"Production job not found")
        if p["status"]!="READY": raise HTTPException(409,f"Only READY production jobs can be published; current status is {p['status']}")
        pid=str(uuid4()); now=datetime.now(timezone.utc).isoformat(); _insert(c,"INSERT INTO publish_requests(publish_id,production_id,title,description,tags_json,scheduled_at,status,external_id,created_at) VALUES (:id,:production,:title,:description,:tags,:scheduled,'DRAFT',NULL,:created)",{"id":pid,"production":request.production_id,"title":request.title.strip(),"description":request.description,"tags":json.dumps(request.tags),"scheduled":request.scheduled_at,"created":now}); return {"publish_id":pid,"status":"DRAFT"}
    finally:c.close()
@router.patch("/publishing/{publish_id}/status")
def publish_status(publish_id:str,request:StatusRequest):
    c=get_connection()
    try: prepare_database(c); _set_status(c,"publish_requests",publish_id,"publish_id",request.status,{"DRAFT","SCHEDULED","PUBLISHED","FAILED"}); return {"publish_id":publish_id,"status":request.status}
    finally:c.close()

@router.get("/analytics")
def analytics():
    c=get_connection()
    try: prepare_database(c); return _json_rows(c,"SELECT * FROM video_metrics ORDER BY captured_at DESC LIMIT 200")
    finally:c.close()
@router.post("/analytics")
def add_metrics(request:MetricsIn):
    c=get_connection()
    try: prepare_database(c); mid=str(uuid4()); p=request.model_dump(); p.update({"id":mid,"captured":request.captured_at}); _insert(c,"INSERT INTO video_metrics(metric_id,external_video_id,captured_at,views,watch_time_minutes,average_view_duration_seconds,impressions,click_through_rate,likes,comments,subscribers_gained,revenue) VALUES (:id,:external_video_id,:captured,:views,:watch_time_minutes,:average_view_duration_seconds,:impressions,:click_through_rate,:likes,:comments,:subscribers_gained,:revenue)",p); return {"metric_id":mid,"status":"recorded"}
    finally:c.close()
@router.post("/analytics/analyze/{metric_id}")
def analyze_metrics(metric_id:str):
    c=get_connection()
    try:
        prepare_database(c); r=_require(c,"SELECT * FROM video_metrics WHERE metric_id=:id",{"id":metric_id},"Metric not found"); m=VideoMetrics(**dict(r)); signals=LearningEngine().analyze(m)
        for s in signals: _insert(c,"INSERT INTO learning_signals(signal_id,source_video_id,signal_type,observation,confidence,created_at) VALUES (:id,:video,:type,:obs,:confidence,:created)",{"id":s.signal_id,"video":s.source_video_id,"type":s.signal_type,"obs":s.observation,"confidence":s.confidence,"created":s.created_at})
        return {"signals":[s.model_dump(mode="json") for s in signals]}
    finally:c.close()

@router.get("/learning")
def learning():
    c=get_connection()
    try: prepare_database(c); return _json_rows(c,"SELECT * FROM learning_signals ORDER BY created_at DESC LIMIT 200")
    finally:c.close()
@router.post("/learning")
def add_learning(request:LearningIn):
    c=get_connection()
    try: prepare_database(c); sid=str(uuid4()); _insert(c,"INSERT INTO learning_signals(signal_id,source_video_id,signal_type,observation,confidence,created_at) VALUES (:id,:video,:type,:obs,:confidence,:created)",{"id":sid,"video":request.source_video_id,"type":request.signal_type,"obs":request.observation,"confidence":request.confidence,"created":datetime.now(timezone.utc).isoformat()}); return {"signal_id":sid,"status":"recorded"}
    finally:c.close()

@router.get("/automation")
def automation():
    c=get_connection()
    try: prepare_database(c); return _json_rows(c,"SELECT * FROM automation_jobs ORDER BY created_at DESC LIMIT 200")
    finally:c.close()
@router.post("/automation")
def add_automation(request:AutomationIn):
    c=get_connection()
    try: prepare_database(c); jid=str(uuid4()); _insert(c,"INSERT INTO automation_jobs(job_id,job_type,payload_json,status,attempts,error,created_at) VALUES (:id,:type,:payload,'QUEUED',0,NULL,:created)",{"id":jid,"type":request.job_type,"payload":json.dumps(request.payload),"created":datetime.now(timezone.utc).isoformat()}); return {"job_id":jid,"status":"QUEUED"}
    finally:c.close()
@router.patch("/automation/{job_id}/status")
def automation_status(job_id:str,request:StatusRequest):
    c=get_connection()
    try: prepare_database(c); _set_status(c,"automation_jobs",job_id,"job_id",request.status,{"QUEUED","RUNNING","SUCCEEDED","FAILED"}); return {"job_id":job_id,"status":request.status}
    finally:c.close()

@router.get("/settings")
def dashboard_settings():
    s=__import__("app.config.settings",fromlist=["get_settings"]).get_settings(); return {"environment":s.environment,"database":"postgres" if using_postgres() else "sqlite","database_path":s.database_path if not using_postgres() else None,"llm_provider":s.llm_provider,"llm_model":s.llm_model,"api_token_configured":bool(s.api_token)}
