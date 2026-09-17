# ContentOS

ContentOS is the internal content operating system for Business #1: a faceless, AI-assisted media business.

## V0 objective

Turn research into structured, reviewable content opportunities. V0 deliberately stops before automatic publishing so we can validate the content strategy before scaling the machinery.

## Core loop

`Research → Ideas → Scoring → Human Review → Script → Production → Publish → Analytics → Learning → Ideas`

The long-term advantage is the feedback loop: real channel performance should improve future content selection instead of treating every video as an isolated generation task.

## V0 principles

- Business first, software second.
- Keep the content model niche-independent.
- AI recommends; a human approves.
- Store decisions and outcomes as data.
- Keep business logic portable so infrastructure can evolve later.
- Research adapters provide evidence; the Research Engine does not invent facts.

## V0 stack

- Python
- SQLite
- Pydantic
- Provider-agnostic research and LLM boundaries
- Pytest

## Current pipeline

1. **Research Engine** accepts normalized research items from any source adapter.
2. It normalizes text and URLs and removes duplicate items.
3. **Idea Engine** turns structured opportunities into `ContentIdea` objects.
4. **Scorer** produces a transparent opportunity score.
5. Human review remains the approval gate.

V0 intentionally does not call external APIs directly. This lets us validate the data model and business rules before choosing providers.

## Planned evolution

V0 starts locally and can later move toward:

`SQLite → PostgreSQL`

`Local workers → Redis/Celery`

`Local storage → S3`

`Python CLI → FastAPI`

`Local runtime → AWS`

The domain models and business logic should remain stable during that migration.
