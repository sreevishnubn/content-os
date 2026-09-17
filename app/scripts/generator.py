"""LLM-backed script generation service."""

from app.llm.models import LLMRequest
from app.scripts.models import ContentScript


class ScriptGenerator:
    def __init__(self, llm_provider) -> None:
        self.llm_provider = llm_provider

    def generate(self, *, idea: dict, evidence: list[dict]) -> ContentScript:
        request = LLMRequest(
            system_prompt=(
                "You are the ContentOS script engine. Create an engaging, factual faceless-video script. "
                "Use only supplied evidence. Put uncertain or unsupported claims in fact_check_required. "
                "Return the requested structured schema."
            ),
            user_prompt=(
                "Approved content idea:\n"
                f"{idea}\n\nEvidence:\n{evidence}\n\n"
                "Create a strong hook, logical sections, visual notes, closing and fact-check list."
            ),
            temperature=0.4,
        )
        return self.llm_provider.generate_structured(request, ContentScript).data
