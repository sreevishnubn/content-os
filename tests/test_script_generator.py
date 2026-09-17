from app.llm.models import LLMRequest
from app.scripts.generator import ScriptGenerator
from app.scripts.models import GeneratedScript


class FakeProvider:
    def __init__(self):
        self.request = None

    def generate_structured(self, request: LLMRequest, response_model):
        self.request = request
        assert response_model is GeneratedScript
        return type(
            "StructuredResponse",
            (),
            {
                "data": GeneratedScript(
                    title="Generated title",
                    hook="Generated hook",
                    sections=[
                        {
                            "heading": "Introduction",
                            "narration": "Evidence-backed narration.",
                            "visual_notes": "Relevant footage",
                        }
                    ],
                    closing="Generated closing",
                    fact_check_required=["Verify source date"],
                )
            },
        )()


def test_script_generator_builds_persistable_script():
    provider = FakeProvider()
    idea = {
        "idea_id": "idea-123",
        "title": "Approved idea",
        "source": "Test Source",
        "why_now": "Recent evidence",
        "metadata_json": "{\"summary\": \"Evidence\"}",
    }

    script = ScriptGenerator(provider).generate(
        idea=idea,
        evidence=[{"title": "Evidence", "summary": "A verified fact"}],
        version=3,
    )

    assert script.idea_id == "idea-123"
    assert script.version == 3
    assert script.title == "Generated title"
    assert len(script.sections) == 1
    assert script.fact_check_required == ["Verify source date"]
    assert provider.request.temperature == 0.4
    assert "Approved content idea:" in provider.request.user_prompt
    assert "Research evidence:" in provider.request.user_prompt
