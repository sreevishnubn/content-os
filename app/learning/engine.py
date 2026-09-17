from app.analytics.models import VideoMetrics
from app.learning.models import LearningSignal


class LearningEngine:
    """Turn observed performance into explicit, reviewable learning signals."""

    def analyze(self, metrics: VideoMetrics) -> list[LearningSignal]:
        signals: list[LearningSignal] = []
        if metrics.views > 0 and metrics.click_through_rate > 0:
            signals.append(
                LearningSignal(
                    source_video_id=metrics.external_video_id,
                    signal_type="CTR",
                    observation=f"Observed CTR of {metrics.click_through_rate:.2f}%.",
                    confidence=0.7,
                )
            )
        if metrics.average_view_duration_seconds > 0:
            signals.append(
                LearningSignal(
                    source_video_id=metrics.external_video_id,
                    signal_type="RETENTION",
                    observation=(
                        "Average view duration was "
                        f"{metrics.average_view_duration_seconds:.1f} seconds."
                    ),
                    confidence=0.7,
                )
            )
        return signals
