"""LLM-backed script generation service."""

from app.llm.models import LLMRequest
from app.scripts.models import ContentScript, GeneratedScript


class ScriptGenerator:
    def __init__(self, llm_provider) -> None:
        self.llm_provider = llm_provider

    def generate(self, *, idea: dict, evidence: list[dict], version: int = 1) -> ContentScript:
        request = LLMRequest(
            system_prompt=(
                "You are the ContentOS script engine. Create an engaging, factual faceless-video script. "
                "Use only supplied evidence. Never invent facts, sources, numbers, quotes, or events. "
                "Put uncertain or unsupported claims in fact_check_required. "
                "Return only the requested structured schema."
            ),
            user_prompt=(
                "Approved content idea:\n"
                f"{idea}\n\n"
                "Research evidence:\n"
                f"{evidence}\n\n"
                "Create a strong hook, logical sections, visual notes, closing and fact-check list."
            ),
            model=None,
            temperature=0.4,
        )
        generated = self.llm_provider.generate_structured(request, GeneratedScript).data
        return ContentScript(
            idea_id=str(idea["idea_id"]),
            title=generated.title,
            hook=generated.hook,
            sections=generated.sections,
            closing=generated.closing,
            fact_check_required=generated.fact_check_required,
            version=version,
        )
