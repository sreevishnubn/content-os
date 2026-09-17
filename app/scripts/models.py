from uuid import uuid4

from pydantic import BaseModel, Field


class ScriptSection(BaseModel):
    heading: str
    narration: str
    visual_notes: str = ""


class GeneratedScript(BaseModel):
    """LLM-owned script content; persistence metadata is assigned by ContentOS."""

    title: str = Field(min_length=1)
    hook: str = Field(min_length=1)
    sections: list[ScriptSection] = Field(min_length=1)
    closing: str = ""
    fact_check_required: list[str] = Field(default_factory=list)


class ContentScript(BaseModel):
    script_id: str = Field(default_factory=lambda: str(uuid4()))
    idea_id: str
    title: str
    hook: str
    sections: list[ScriptSection] = Field(default_factory=list)
    closing: str = ""
    fact_check_required: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
