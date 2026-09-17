import pytest


@pytest.fixture(autouse=True)
def fake_llm_for_workflow_tests(monkeypatch):
    """Keep workflow tests deterministic without external LLM credentials."""
    from app.config.settings import get_settings
    from app.scripts.models import ContentScript, ScriptSection

    monkeypatch.setenv("CONTENTOS_LLM_PROVIDER", "openai")
    monkeypatch.setenv("CONTENTOS_LLM_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    import app.api.workflow as workflow_module

    class FakeScriptGenerator:
        def __init__(self, provider):
            self.provider = provider

        def generate(self, *, idea, evidence):
            return ContentScript(
                idea_id=idea["idea_id"],
                title=idea["title"],
                hook="A tested hook for this workflow.",
                sections=[
                    ScriptSection(heading="Setup", narration="Set up the story.", visual_notes="B-roll"),
                    ScriptSection(heading="Evidence", narration="Explain the evidence.", visual_notes="Source"),
                    ScriptSection(heading="Context", narration="Add context.", visual_notes="Diagram"),
                    ScriptSection(heading="Next", narration="Explain what to watch next.", visual_notes="End card"),
                ],
                closing="Subscribe for the next breakdown.",
                fact_check_required=[],
                version=1,
            )

    monkeypatch.setattr(workflow_module, "ScriptGenerator", FakeScriptGenerator)
    monkeypatch.setattr(workflow_module, "get_llm_provider", lambda: object())
    yield
    get_settings.cache_clear()
