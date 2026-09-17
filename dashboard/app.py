"""Dashboard application entry point placeholder.

The dashboard UI framework is intentionally isolated from domain logic. The
first implementation can use this entry point and call application services;
the same contracts can later be exposed through FastAPI and a richer frontend.
"""


def dashboard_metadata() -> dict[str, object]:
    """Return navigation metadata for the operator dashboard."""
    return {
        "name": "ContentOS",
        "sections": [
            "overview",
            "research",
            "ideas",
            "review",
            "scripts",
            "production",
            "publishing",
            "analytics",
            "learning",
            "automation",
            "ai",
            "settings",
        ],
    }
