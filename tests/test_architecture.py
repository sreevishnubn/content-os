from datetime import datetime, timezone

from pydantic import BaseModel

from app.analytics.models import VideoMetrics
from app.automation.jobs import AutomationJob, JobStatus
from app.automation.scheduler import JobRunner
from app.llm.interface import LLMProvider
from app.llm.models import LLMRequest, LLMResponse
from app.llm.router import LLMRouter
from app.learning.engine import LearningEngine
from app.production.models import ProductionJob, ProductionStatus
from app.publishing.models import PublishRequest
from app.scripts.models import ContentScript, ScriptSection


class FakeLLM(LLMProvider):
    name = "fake"

    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(text='{"value":"ok"}', provider=self.name, model="fake-1")


class Output(BaseModel):
    value: str


def test_llm_router_and_structured_output():
    router = LLMRouter({"fake": FakeLLM()}, "fake")
    result = router.get().generate_structured(
        LLMRequest(user_prompt="test"), Output
    )
    assert result.data.value == "ok"
    assert result.provider == "fake"


def test_cross_engine_domain_models():
    script = ContentScript(
        idea_id="idea-1",
        title="Test",
        hook="Hook",
        sections=[ScriptSection(heading="Intro", narration="Hello")],
    )
    production = ProductionJob(script_id=script.script_id)
    publish = PublishRequest(production_id=production.production_id, title="Test")
    assert production.status == ProductionStatus.QUEUED
    assert publish.production_id == production.production_id


def test_learning_engine_creates_signals():
    metrics = VideoMetrics(
        external_video_id="video-1",
        captured_at=datetime.now(timezone.utc),
        views=100,
        click_through_rate=5.2,
        average_view_duration_seconds=42,
    )
    signals = LearningEngine().analyze(metrics)
    assert {signal.signal_type for signal in signals} == {"CTR", "RETENTION"}


def test_job_runner_success_and_failure():
    runner = JobRunner({"ok": lambda payload: payload})
    assert runner.run(AutomationJob(job_type="ok")).status == JobStatus.SUCCEEDED
    assert runner.run(AutomationJob(job_type="missing")).status == JobStatus.FAILED
