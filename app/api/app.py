"""Production HTTP API for the ContentOS operator dashboard."""
import json
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text
from app.config.settings import get_settings
from app.database.connection import get_connection, using_postgres
from app.database.models import IdeaStatus
from app.api.common import require_api_token, prepare_database, one
from app.ideas.from_research import research_items_to_ideas
from app.ideas.scorer import score_idea
from app.research.engine import normalize_items
from app.research.providers.youtube_rss import YouTubeRSSProvider
from app.research.providers.youtube_resolver import resolve_channel_ids
from app.research.repository import ResearchRepository

app = FastAPI(title="ContentOS API", version="1.1.0")
settings = get_settings()
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_origin_regex=r"https://([a-zA-Z0-9-]+\\.)?github\\.io$|https://dashboard\\.youtube\\.analysis\\.com$", allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["*"])
app.frontend("/", directory="dashboard")

class YouTubeResearchRequest(BaseModel):
    channel_ids: list[str] = Field(min_length=1, max_length=20)
    query: str = ""
    limit: int = Field(default=20, ge=1, le=100)
    generate_ideas: bool = True

class IdeaStatusUpdate(BaseModel):
    status: IdeaStatus

def _save_ideas(connection, ideas):
    columns = """idea_id,title,topic,audience,hook,source,why_now,monetization_angle,
        demand,curiosity,competition,monetization,production,overall_score,status,
        metadata_json,created_at"""
    if using_postgres():
        sql = f"""INSERT INTO content_ideas ({columns})
            VALUES (:id,:title,:topic,:audience,:hook,:source,:why_now,:monetization,
                    :demand,:curiosity,:competition,:monetization_score,:production,
                    :overall,:status,:metadata,:created)"""
        for i in ideas:
            connection.execute(text(sql), {
                "id": i.idea_id,
                "title": i.title,
                "topic": i.topic,
                "audience": i.audience,
                "hook": i.hook,
                "source": i.source,
                "why_now": i.why_now,
                "monetization": i.monetization_angle,
                "demand": i.scores.demand,
                "curiosity": i.scores.curiosity,
                "competition": i.scores.competition,
                "monetization_score": i.scores.monetization,
                "production": i.scores.production,
                "overall": i.overall_score,
                "status": i.status.value,
                "metadata": json.dumps(i.metadata, sort_keys=True),
                "created": i.created_at,
            })
    else:
        sql = f"""INSERT INTO content_ideas ({columns.replace(chr(10), ' ')})
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
        for i in ideas:
            connection.execute(sql, (
                i.idea_id,
                i.title,
                i.topic,
                i.audience,
                i.hook,
                i.source,
                i.why_now,
                i.monetization_angle,
                i.scores.demand,
                i.scores.curiosity,
                i.scores.competition,
                i.scores.monetization,
                i.scores.production,
                i.overall_score,
                i.status.value,
                json.dumps(i.metadata, sort_keys=True),
                i.created_at,
            ))
    connection.commit()

def _idea_from_row(row):
    item=dict(row); raw=item.pop("metadata_json","{}") or "{}"
    try: item["metadata"]=json.loads(raw)
    except (TypeError,json.JSONDecodeError): item["metadata"]={}
    return item

@app.get("/health")
def health():
    c=None
    try:
        c=get_connection(); prepare_database(c); c.execute(text("SELECT 1")) if using_postgres() else c.execute("SELECT 1")
        return {"status":"ok","service":"contentos-api","database":"postgres" if using_postgres() else "sqlite"}
    except Exception as exc: raise HTTPException(503,f"Database health check failed: {type(exc).__name__}: {exc}") from exc
    finally:
        if c: c.close()

@app.post("/api/research/youtube/resolve", dependencies=[Depends(require_api_token)])
def resolve_youtube_channels(request:YouTubeResearchRequest):
    resolved=[]; failed=[]
    for source in request.channel_ids:
        try: resolved.append({"input":source,"channel_id":resolve_channel_ids([source])[0]})
        except Exception as exc: failed.append({"input":source,"error":f"{type(exc).__name__}: {exc}"})
    return {"resolved":resolved,"failed":failed}

@app.post("/api/research/youtube", dependencies=[Depends(require_api_token)])
def research_youtube(request:YouTubeResearchRequest):
    try: ids=resolve_channel_ids(request.channel_ids)
    except Exception as exc: raise HTTPException(422,f"Could not resolve channels: {exc}") from exc
    provider=YouTubeRSSProvider(ids)
    try: items=normalize_items(provider.search(request.query,limit=request.limit))
    except Exception as exc: raise HTTPException(502,f"YouTube research failed: {exc}") from exc
    c=get_connection()
    try:
        prepare_database(c); ResearchRepository(c,postgres=using_postgres()).save_many(items)
        ideas=[score_idea(x) for x in research_items_to_ideas(items)] if request.generate_ideas and items else []
        if ideas: _save_ideas(c,ideas)
        return {"provider":provider.name,"channel_ids":ids,"research_items_found":len(items),"ideas_created":len(ideas),"research":[x.model_dump(mode="json") for x in items],"ideas":[x.model_dump(mode="json") for x in ideas]}
    finally: c.close()

@app.get("/api/dashboard/overview")
def dashboard_overview():
    c=get_connection()
    try:
        prepare_database(c); r=one(c,"SELECT (SELECT COUNT(*) FROM research_items) research_items,(SELECT COUNT(*) FROM content_ideas) ideas,(SELECT COUNT(*) FROM content_ideas WHERE status='APPROVED') approved,(SELECT COUNT(*) FROM content_ideas WHERE status IN ('SHORTLISTED','REVIEW')) review,(SELECT COUNT(*) FROM content_scripts) scripts,(SELECT COUNT(*) FROM production_jobs WHERE status!='FAILED') production,(SELECT COUNT(*) FROM publish_requests WHERE status='PUBLISHED') published,(SELECT COUNT(*) FROM video_metrics) analytics,(SELECT COUNT(*) FROM learning_signals) learning,(SELECT COUNT(*) FROM automation_jobs WHERE status IN ('QUEUED','RUNNING')) automation")
        return {k:r[k] or 0 for k in r.keys()}
    finally: c.close()

@app.get("/api/dashboard/ideas")
def dashboard_ideas(limit:int=20,status:IdeaStatus|None=None):
    c=get_connection()
    try:
        prepare_database(c); limit=max(1,min(limit,100)); where=" WHERE status=:status" if status else ""; sql="SELECT idea_id,title,topic,audience,hook,source,why_now,monetization_angle,demand,curiosity,competition,monetization,production,overall_score,status,metadata_json,created_at FROM content_ideas"+where+" ORDER BY overall_score DESC,created_at ASC LIMIT :limit"; p={"limit":limit}; p.update({"status":status.value} if status else {})
        if using_postgres(): rows=c.execute(text(sql),p).mappings().all()
        elif status: rows=c.execute(sql.replace(":status","?").replace(":limit","?"),(status.value,limit)).fetchall()
        else: rows=c.execute(sql.replace(":limit","?"),(limit,)).fetchall()
        return [_idea_from_row(x) for x in rows]
    finally: c.close()

@app.patch("/api/dashboard/ideas/{idea_id}/status",dependencies=[Depends(require_api_token)])
def update_idea_status(idea_id:str,request:IdeaStatusUpdate):
    transitions={"DISCOVERED":{"SHORTLISTED","REJECTED"},"SHORTLISTED":{"REVIEW","REJECTED"},"REVIEW":{"APPROVED","REJECTED","SHORTLISTED"},"APPROVED":{"SCRIPTING","REJECTED"},"SCRIPTING":{"PRODUCTION","APPROVED"},"PRODUCTION":{"REVIEW","PUBLISHED"},"PUBLISHED":{"ANALYZING"},"ANALYZING":set(),"REJECTED":{"DISCOVERED"}}
    c=get_connection()
    try:
        prepare_database(c); current=one(c,"SELECT status FROM content_ideas WHERE idea_id=:id",{"id":idea_id})
        if not current: raise HTTPException(404,"Idea not found")
        new=request.status.value
        if new!=current["status"] and new not in transitions.get(current["status"],set()): raise HTTPException(409,f"Invalid idea transition: {current['status']} -> {new}")
        if using_postgres(): c.execute(text("UPDATE content_ideas SET status=:status WHERE idea_id=:id"),{"status":new,"id":idea_id})
        else: c.execute("UPDATE content_ideas SET status=? WHERE idea_id=?",(new,idea_id))
        c.commit(); return {"idea_id":idea_id,"status":new}
    finally: c.close()

@app.post("/api/admin/bootstrap",dependencies=[Depends(require_api_token)])
def bootstrap_database():
    c=get_connection()
    try: prepare_database(c); return {"status":"initialized"}
    finally: c.close()

from app.api.workflow import router as workflow_router
app.include_router(workflow_router)
