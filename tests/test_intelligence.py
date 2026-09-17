from app.intelligence.channel_benchmarks import channel_median_views, performance_multiple, rank_outliers
from app.intelligence.hooks import analyze_hook, rank_hooks
from app.intelligence.packaging import _terms, lint_package
from app.intelligence.retention import find_cliffs
from app.intelligence.shorts import find_candidates


def test_hook_analysis_is_heuristic_and_rankable():
    result = analyze_hook("97% of channels quit before video 30. Here is what changes that.")
    assert result.formula == "statistic"
    assert 0 <= result.score <= 10
    assert rank_hooks(["How do you fix this?", result.hook])[0].score >= 0


def test_package_terms_normalize_and_overlap():
    title_terms = _terms("The Best AI Workflow")
    thumbnail_terms = _terms("BEST AI")
    assert title_terms == {"best", "ai", "workflow"}
    assert thumbnail_terms == {"best", "ai"}
    assert title_terms & thumbnail_terms == {"best", "ai"}


def test_package_lint_detects_repetition():
    report = lint_package("The Best AI Workflow", "BEST AI")
    assert report.duplicate_terms == ("ai", "best")
    assert report.score < 10


def test_channel_baseline_multiple():
    assert channel_median_views([10, 20, 30]) == 20
    assert performance_multiple(60, 20) == 3
    ranked = rank_outliers([{"channel": "A", "views": 60, "channel_views": [10, 20, 30]}], 2)
    assert ranked[0]["performance_multiple"] == 3


def test_retention_cliff():
    cliffs = find_cliffs([
        {"timestamp_seconds": 0, "retention": 1.0},
        {"timestamp_seconds": 15, "retention": 0.88},
    ])
    assert cliffs[0].label == "hook"


def test_short_candidates():
    candidates = find_candidates([{
        "start_seconds": 10,
        "end_seconds": 45,
        "text": "This is a sufficiently long self-contained beat that can be reviewed as a short-form candidate.",
    }])
    assert len(candidates) == 1
