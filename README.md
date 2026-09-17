# ContentOS

ContentOS is the internal content operating system for Business #1: a faceless, AI-assisted media business.

## V0.1 objective

Turn research into structured, reviewable and persisted content opportunities. V0.1 deliberately stops before automatic publishing so we can validate the content strategy and human decision workflow before scaling the machinery.

## Core loop

`Research → Ideas → Scoring → Persistence → Human Review → Script → Production → Publish → Analytics → Learning → Ideas`

The long-term advantage is the feedback loop: real channel performance should improve future content selection instead of treating every video as an isolated generation task.

## V0.1 principles

- Business first, software second.
- Keep the content model niche-independent.
- AI recommends; a human approves.
- Store decisions and outcomes as data.
- Research adapters provide evidence; the Research Engine does not invent facts.
- Keep business logic portable so infrastructure can evolve later.
- Do not fabricate intelligence: V0.1 scoring inputs remain explicit until a scoring provider is added.

## Current pipeline

1. **Research Engine** accepts normalized research items from any source adapter.
2. It normalizes text and URLs and removes duplicate items.
3. **Idea Engine** converts each research item into deterministic editorial candidates.
4. **Scorer** calculates a transparent weighted opportunity score.
5. **Idea Repository** persists candidates and their evidence in SQLite.
6. **Human Review Service** moves ideas through `DISCOVERED → SHORTLISTED → APPROVED` or `REJECTED` using explicit workflow rules.

Research-derived V0.1 candidates use neutral zero-valued scoring inputs until a real scoring/intelligence provider is introduced. This keeps the system honest and provider-agnostic.

## V0.1 tested path

`Research → Normalize/Dedupe → Generate 3 Angles → Score → SQLite → Retrieve → Human Review`

The test suite covers normalization, duplicate removal, idea generation, scoring, persistence round-trips, status filtering, valid review transitions, invalid transitions, and the complete integration path.

## Current boundaries

V0.1 intentionally does not call external APIs directly and does not implement automatic publishing, script generation, production, analytics, or learning. Those are downstream stages and will be added only after the idea-management foundation is validated.

## V0.1 stack

- Python
- SQLite
- Pydantic
- Provider-agnostic research and LLM boundaries
- Pytest

## Planned evolution

V0.1 starts locally and can later move toward:

`SQLite → PostgreSQL`

`Local workers → Redis/Celery`

`Local storage → S3`

`Python CLI → FastAPI`

`Local runtime → AWS`

The domain models and business logic should remain stable during that migration.
