"""Production HTTP API for the ContentOS operator dashboard."""

import json

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config.settings import get_settings
from app.database.connection import get_connection, using_postgres
from app.database.models import ContentIdea, IdeaStatus
from app.database.schema import initialize_postgres_schema, initialize_schema
from app.ideas.from_research import research_items_to_ideas
from app.ideas.scorer import score_idea
from app.research.engine import normalize_items
from app.research.providers.youtube_rss import YouTubeRSSProvider
from app.research.providers.youtube_resolver import resolve_channel_ids
from app.research.repository import ResearchRepository

app = FastAPI(title="ContentOS API", version="1.0.0")
settings = get_settings()
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_origin_regex=r"https://([a-zA-Z0-9-]+\.)?github\.io$|https://dashboard\.youtube\.analysis\.com$", allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["*"])
app.frontend("/", directory="dashboard")

class YouTubeResearchRequest(BaseModel):
    channel_ids: list[str] = Field(min_length=1, max_length=20)
    query: str = ""
    limit: int = Field(default=20, ge=1, le=100)
    generate_ideas: bool = True

class IdeaStatusUpdate(BaseModel):
    status: IdeaStatus

def require_api_token(authorization: str | None = Header(default=None)) -> None:
    if settings.api_token and authorization != f"Bearer {settings.api_token}":
        raise HTTPException(status_code=401, detail="Invalid or missing API token")

def _prepare(connection, *, bootstrap: bool = False) -> None:
    if using_postgres(): initialize_postgres_schema(connection)
    else: initialize_schema(connection)

def _fetch_one(connection, sql: str):
    if using_postgres(): return connection.execute(text(sql)).mappings().one()
    return connection.execute(sql).fetchone()

def _save_ideas(connection, ideas: list[ContentIdea]) -> None:
    if using_postgres():
        statement = text("""INSERT INTO content_ideas (idea_id,title,topic,audience,hook,source,why_now,monetization_angle,demand,curiosity,competition,monetization,production,overall_score,status,metadata_json,created_at) VALUES (:id,:title,:topic,:audience,:hook,:source,:why_now,:monetization,:demand,:curiosity,:competition,:monetization_score,:production,:overall,:status,:metadata,:created)""")
        for idea in ideas: connection.execute(statement, {"id":idea.idea_id,"title":idea.title,"topic":idea.topic,"audience":idea.audience,"hook":idea.hook,"source":idea.source,"why_now":idea.why_now,"monetization":idea.monetization_angle,"demand":idea.scores.demand,"curiosity":idea.scores.curiosity,"competition":idea.scores.competition,"monetization_score":idea.scores.monetization,"production":idea.scores.production,"overall":idea.overall_score,"status":idea.status.value,"metadata":json.dumps(idea.metadata,sort_keys=True),"created":idea.created_at})
    else:
        for idea in ideas: connection.execute("INSERT OR REPLACE INTO content_ideas (idea_id,title,topic,audience,hook,source,why_now,monetization_angle,demand,curiosity,competition,monetization,production,overall_score,status,metadata_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (idea.idea_id,idea.title,idea.topic,idea.audience,idea.hook,idea.source,idea.why_now,idea.monetization_angle,idea.scores.demand,idea.scores.curiosity,idea.scores.competition,idea.scores.monetization,idea.scores.production,idea.overall_score,idea.status.value,json.dumps(idea.metadata,sort_keys=True),idea.created_at.isoformat()))
    connection.commit()

def _idea_from_row(row) -> dict[str, object]:
    item=dict(row); raw=item.pop("metadata_json","{}") or "{}"
    try:item["metadata"]=json.loads(raw)
    except (TypeError,json.JSONDecodeError):item["metadata"]={}
    return item

@app.get("/health")
def health() -> dict[str, object]:
    connection=None
    try:
        connection=get_connection()
        if using_postgres(): connection.execute(text("SELECT 1"))
        else: _prepare(connection);connection.execute("SELECT 1")
        return {"status":"ok","service":"contentos-api","database":"postgres" if using_postgres() else "sqlite"}
    except Exception as exc: raise HTTPException(status_code=503,detail=f"Database health check failed: {type(exc).__name__}: {exc}") from exc
    finally:
        if connection is not None: connection.close()

@app.post("/api/research/youtube/resolve")
def resolve_youtube_channels(request: YouTubeResearchRequest) -> dict[str, object]:
    resolved=[]
    for source in request.channel_ids:
        try: resolved.append({"input":source,"channel_id":resolve_channel_ids([source])[0]})
        except Exception as exc: resolved.append({"input":source,"error":f"{type(exc).__name__}: {exc}"})
    return {"resolved":[x for x in resolved if "channel_id" in x],"failed":[x for x in resolved if "error" in x]}

@app.post("/api/research/youtube", dependencies=[Depends(require_api_token)])
def research_youtube(request: YouTubeResearchRequest) -> dict[str, object]:
    try: resolved_ids=resolve_channel_ids(request.channel_ids)
    except Exception as exc: raise HTTPException(422,f"Could not resolve one or more YouTube channels: {type(exc).__name__}: {exc}") from exc
    provider=YouTubeRSSProvider(resolved_ids)
    try: items=normalize_items(provider.search(request.query,limit=request.limit))
    except Exception as exc: raise HTTPException(502,f"YouTube research failed: {type(exc).__name__}: {exc}") from exc
    connection=get_connection()
    try:
        _prepare(connection);ResearchRepository(connection,postgres=using_postgres()).save_many(items)
        ideas=[score_idea(x) for x in research_items_to_ideas(items)] if request.generate_ideas and items else []
        if ideas:_save_ideas(connection,ideas)
        return {"provider":provider.name,"channel_ids":resolved_ids,"research_items_found":len(items),"ideas_created":len(ideas),"research":[x.model_dump(mode="json") for x in items],"ideas":[x.model_dump(mode="json") for x in ideas]}
    finally:connection.close()

@app.get("/api/dashboard/overview")
def dashboard_overview() -> dict[str, object]:
    connection=get_connection()
    try:
        _prepare(connection);counts=_fetch_one(connection,"""SELECT (SELECT COUNT(*) FROM research_items) AS research_items,(SELECT COUNT(*) FROM content_ideas) AS ideas,(SELECT COUNT(*) FROM content_ideas WHERE status='APPROVED') AS approved,(SELECT COUNT(*) FROM content_ideas WHERE status IN ('SHORTLISTED','REVIEW')) AS review,(SELECT COUNT(*) FROM content_scripts) AS scripts,(SELECT COUNT(*) FROM production_jobs WHERE status!='FAILED') AS production,(SELECT COUNT(*) FROM publish_requests WHERE status='PUBLISHED') AS published,(SELECT COUNT(*) FROM video_metrics) AS analytics,(SELECT COUNT(*) FROM learning_signals) AS learning,(SELECT COUNT(*) FROM automation_jobs WHERE status IN ('QUEUED','RUNNING')) AS automation""")
        return {key:counts[key] or 0 for key in counts.keys()}
    finally:connection.close()

@app.get("/api/dashboard/ideas")
def dashboard_ideas(limit:int=20,status:IdeaStatus|None=None):
    limit=max(1,min(limit,100));connection=get_connection()
    try:
        _prepare(connection);where="";params={"limit":limit}
        if status:where=" WHERE status = :status";params["status"]=status.value
        sql="SELECT idea_id,title,topic,audience,hook,source,why_now,monetization_angle,demand,curiosity,competition,monetization,production,overall_score,status,metadata_json,created_at FROM content_ideas"+where+" ORDER BY overall_score DESC,created_at ASC LIMIT :limit"
        if using_postgres():rows=connection.execute(text(sql),params).mappings().all()
        elif status:rows=connection.execute(sql.replace(":status","?").replace(":limit","?"),(status.value,limit)).fetchall()
        else:rows=connection.execute(sql.replace(":limit","?"),(limit,)).fetchall()
        return [_idea_from_row(x) for x in rows]
    finally:connection.close()

@app.patch("/api/dashboard/ideas/{idea_id}/status", dependencies=[Depends(require_api_token)])
def update_idea_status(idea_id:str,request:IdeaStatusUpdate):
    connection=get_connection()
    try:
        _prepare(connection)
        if using_postgres():result=connection.execute(text("UPDATE content_ideas SET status=:status WHERE idea_id=:id"),{"status":request.status.value,"id":idea_id})
        else:result=connection.execute("UPDATE content_ideas SET status=? WHERE idea_id=?",(request.status.value,idea_id))
        if result.rowcount==0:raise HTTPException(404,"Idea not found")
        connection.commit();return {"idea_id":idea_id,"status":request.status.value}
    finally:connection.close()

@app.post("/api/admin/bootstrap",dependencies=[Depends(require_api_token)])
def bootstrap_database():
    connection=get_connection()
    try:_prepare(connection,bootstrap=True);return {"status":"initialized"}
    finally:connection.close()

from app.api.workflow import router as workflow_router
app.include_router(workflow_router)
