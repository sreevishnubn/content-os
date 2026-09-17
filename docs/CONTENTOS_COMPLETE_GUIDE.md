# ContentOS — Complete Product & Operations Guide

**Version:** 1.0
**Purpose:** Explain what ContentOS is, how the system works, how to run it locally, how to deploy it, how to operate it, and what is required before calling the system production-ready for real content operations.

---

## 1. What ContentOS is

ContentOS is the internal operating system for the content business. It is not just an AI script generator.

Its core loop is:

```text
Research
   ↓
Evidence / Signals
   ↓
Idea Generation
   ↓
Scoring
   ↓
Human Review
   ↓
Script
   ↓
Production
   ↓
Publishing
   ↓
Analytics
   ↓
Learning
   └──────────────→ back to Ideas
```

The goal is to build a repeatable system where every published piece of content creates information that improves the next content decision.

### The most important principle

**Business logic must not depend on one AI provider, one database, or one deployment platform.**

That is why the repository contains interfaces around research, LLMs, analytics, publishing, and automation.

---

# 2. Product architecture

```text
                         CONTENTOS
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   RESEARCH ENGINE       LLM ENGINE         ANALYTICS ENGINE
        │                    │                    │
        └──────────────┬─────┴────────────────────┘
                       ▼
                IDEA INTELLIGENCE
             Generate → Score → Rank
                       │
                       ▼
                 HUMAN REVIEW
                       │
                    APPROVE
                       │
                       ▼
                  SCRIPT ENGINE
                       │
                       ▼
                PRODUCTION ENGINE
                       │
                       ▼
                 PUBLISHING ENGINE
                       │
                       ▼
                    YOUTUBE
                       │
                       ▼
                PERFORMANCE DATA
                       │
                       ▼
                 LEARNING ENGINE
                       │
                       └────────────→ IDEA INTELLIGENCE
```

## Production infrastructure

```text
GitHub
  │
  ├── source code
  ├── tests
  └── GitHub Pages workflow
          │
          ▼
   Dashboard (static)
          │ HTTPS
          ▼
   Vercel / FastAPI
          │
          ▼
   Hosted PostgreSQL
          │
          ├── ideas
          ├── research
          ├── scripts
          ├── production
          ├── publishing
          └── analytics
```

---

# 3. Repository structure

```text
content-os/
├── api/
│   └── index.py                 # Vercel FastAPI entrypoint
│
├── app/
│   ├── api/                     # HTTP API
│   ├── automation/              # Job contracts and runner
│   ├── analytics/               # Metrics contracts
│   ├── config/                  # Runtime configuration
│   ├── database/                # Database connection/schema/repositories
│   ├── ideas/                   # Idea generation/scoring/review
│   ├── learning/                # Performance feedback
│   ├── llm/                    # Provider-independent AI layer
│   ├── production/              # Production job contracts
│   ├── publishing/              # Publishing contracts
│   ├── research/                # Research normalization/contracts
│   ├── scripts/                 # Script contracts
│   └── main.py                  # Existing application entrypoint
│
├── dashboard/
│   ├── index.html               # Operator dashboard
│   ├── app.py                   # Dashboard metadata
│   └── README.md
│
├── migrations/
│   └── 001_initial.sql          # PostgreSQL production schema
│
├── scripts/
│   └── migrate.py               # Production migration runner
│
├── tests/                       # Automated tests
├── .env.example                 # Configuration template
├── requirements.txt             # Runtime dependencies
└── vercel.json                  # Vercel configuration
```

---

# 4. Core concepts

## Research

Research produces normalized evidence objects. A research item contains a title, summary, optional URL, source, publication time, discovery time, and tags.

The research layer intentionally does not decide what the business should publish.

## Ideas

An idea contains:

- title
- topic
- target audience
- hook
- source/provenance
- why it is timely
- monetization angle
- opportunity scores
- workflow status

## Idea scoring

Current V0 scoring is transparent:

| Factor | Weight |
|---|---:|
| Demand | 30% |
| Curiosity | 25% |
| Competition opportunity | 15% |
| Monetization | 20% |
| Production ease | 10% |

Scores are 0–10. Higher is better.

Competition means **opportunity after considering competitive pressure**, and production means **ease of producing the content**.

## Human review

AI-generated opportunities should not automatically become published content. The review stage is the control point where a human can approve, reject, or request changes.

## Scripts

Scripts are structured objects rather than plain text blobs. A script has a hook, sections, narration, visual notes, closing, fact-check flags, and version number.

## Production

Production jobs track status:

```text
QUEUED → ASSETS → RENDERING → READY
                    └──────→ FAILED
```

## Publishing

Publishing tracks:

```text
DRAFT → SCHEDULED → PUBLISHED
           └──────→ FAILED
```

## Analytics

The analytics model supports:

- views
- watch time
- average view duration
- impressions
- click-through rate
- likes
- comments
- subscribers gained
- revenue

## Learning

The learning engine converts performance into explicit learning signals. Current examples include CTR and retention observations.

The long-term objective is to use those signals to improve idea generation and scoring.

## Automation

Automation jobs have explicit states:

```text
QUEUED → RUNNING → SUCCEEDED
              └──→ FAILED
```

The V0 runner is synchronous and intentionally replaceable by a queue/worker system later.

---

# 5. Local development

## Prerequisites

Install:

- Python 3.12+
- Git
- a GitHub account if you want CI/CD

Optional later:

- PostgreSQL
- a supported LLM API key
- YouTube API credentials

## Clone

```bash
git clone https://github.com/sreevishnubn/content-os.git
cd content-os
```

## Create a virtual environment

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

## Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configure environment

Copy `.env.example` to `.env`.

For the first local run, keep `DATABASE_URL` empty. ContentOS will use SQLite at:

```text
data/content.db
```

Do not commit `.env`.

---

# 6. Run the API locally

Start FastAPI with Uvicorn:

```bash
python -m uvicorn app.api.app:app --reload --port 8000
```

API:

```text
http://localhost:8000
```

Health check:

```text
GET /health
```

Swagger/OpenAPI:

```text
http://localhost:8000/docs
```

Dashboard overview:

```text
GET /api/dashboard/overview
```

Ideas:

```text
GET /api/dashboard/ideas?limit=20
```

---

# 7. Run tests

```bash
python -m pytest -q
```

Every pull request should pass the test suite before production deployment.

GitHub Actions already runs the test workflow on pushes and pull requests to `master`.

---

# 8. Local database

SQLite is intentionally the local-development database.

Advantages:

- zero setup
- easy testing
- portable
- fast for V0

Do **not** use the local SQLite file as the production source of truth on Vercel.

Production uses PostgreSQL through `DATABASE_URL`.

---

# 9. Production database

A hosted PostgreSQL database is required for persistent production data.

Suitable managed PostgreSQL providers include any service that provides a standard PostgreSQL connection string.

The connection string is configured as:

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
```

Never commit this value to GitHub.

## Create the schema

With the production `DATABASE_URL` available locally:

```bash
python scripts/migrate.py
```

The initial migration creates `content_ideas` and its indexes.

---

# 10. Why PostgreSQL in production?

The dashboard is static and GitHub Pages cannot provide a persistent application database.

Vercel provides application compute, not a durable local filesystem database for this architecture.

Therefore:

```text
GitHub Pages = frontend
Vercel       = API/compute
PostgreSQL   = persistent data
```

This separation is deliberate.

---

# 11. Vercel deployment

The repository contains:

```text
api/index.py
```

which exposes the FastAPI application to Vercel.

It also contains `vercel.json` for function configuration.

## Recommended deployment model

Connect the GitHub repository to Vercel so every approved deployment can be built from Git.

Project root:

```text
.
```

Framework/runtime:

```text
FastAPI / Python
```

## Required production environment variables

Set these in the Vercel project:

```text
CONTENTOS_ENVIRONMENT=production
DATABASE_URL=<managed-postgresql-url>
CONTENTOS_API_TOKEN=<long-random-secret>
CONTENTOS_CORS_ORIGINS=https://sreevishnubn.github.io,https://dashboard.youtube.analysis.com
```

Add LLM variables only when the corresponding provider is actually enabled.

Never put provider secrets into the dashboard JavaScript.

---

# 12. API security

The dashboard's read-only endpoints are intentionally simple so the public dashboard can read them.

Administrative/mutating endpoints should require:

```text
Authorization: Bearer <CONTENTOS_API_TOKEN>
```

The production API token must only exist on the server side.

### Important rule

Do not put `CONTENTOS_API_TOKEN` in GitHub Pages HTML/JavaScript. Anything shipped to a browser is public.

For a future multi-user version, replace the simple service token with proper user authentication and role-based authorization.

---

# 13. GitHub Pages dashboard

The dashboard is deployed by:

```text
.github/workflows/dashboard-pages.yml
```

GitHub Pages source should be:

```text
GitHub Actions
```

Current base URL:

```text
https://sreevishnubn.github.io/content-os/
```

The dashboard now requests live values from:

```text
/api/dashboard/overview
/api/dashboard/ideas
```

instead of displaying the original hard-coded demo metrics.

The dashboard refreshes the overview every 60 seconds.

---

# 14. Custom dashboard domain

If the intended domain is:

```text
dashboard.youtube.analysis.com
```

configure the DNS CNAME for `dashboard` to the GitHub Pages hostname supplied by GitHub.

Then add the custom domain in GitHub Pages settings and wait for certificate provisioning.

The API can remain on a Vercel hostname initially. A dedicated API domain can be added later, for example:

```text
api.youtube.analysis.com
```

---

# 15. Live dashboard flow

When the dashboard opens:

```text
Browser
  ↓
GET /api/dashboard/overview
  ↓
FastAPI
  ↓
PostgreSQL
  ↓
Current counts
  ↓
Dashboard cards
```

For ideas:

```text
Browser
  ↓
GET /api/dashboard/ideas
  ↓
FastAPI
  ↓
PostgreSQL
  ↓
Ranked ideas
  ↓
Top Opportunities table
```

If the API cannot be reached, the dashboard deliberately displays `API Offline` instead of pretending that stale demo values are live.

---

# 16. Current API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service/database health |
| GET | `/api/dashboard/overview` | Live workflow counts |
| GET | `/api/dashboard/ideas` | Ranked ideas |
| POST | `/api/admin/bootstrap` | Initialize configured database |

The API is intentionally small at this stage. More endpoints should be added around stable domain services rather than exposing raw database tables.

---

# 17. LLM architecture

ContentOS does not directly hard-code the business logic to one LLM vendor.

The abstraction is:

```text
ContentOS
   ↓
LLMRouter
   ↓
LLMProvider interface
   ├── OpenAI adapter
   ├── Anthropic adapter
   └── Gemini adapter
```

The provider adapter should return the normalized `LLMResponse` model.

This means the business layer can ask for:

```text
Generate structured ideas
```

without caring whether the underlying model is OpenAI, Anthropic, Gemini, or a future provider.

---

# 18. AI safety and factuality

ContentOS prompts explicitly instruct AI components not to invent research facts.

The production workflow should follow:

```text
Research evidence
      ↓
AI generation
      ↓
Structured output
      ↓
Validation
      ↓
Fact-check flags
      ↓
Human review
```

AI output should never be treated as automatically verified simply because it came from a language model.

---

# 19. Research engine

The research interface is provider-independent:

```python
class ResearchProvider:
    def search(query, limit=10):
        ...
```

Adapters can later connect to:

- web/news research
- RSS feeds
- YouTube search
- Google Trends-like sources
- social signals
- niche-specific data providers

All provider results should be normalized into `ResearchItem` objects before entering ContentOS.

---

# 20. Idea intelligence

The idea intelligence layer should eventually perform:

```text
Research
   ↓
Candidate extraction
   ↓
Duplicate detection
   ↓
Idea generation
   ↓
Scoring
   ↓
Clustering
   ↓
Ranking
   ↓
Human review
```

The scoring model is transparent so we can change weights based on real performance data.

---

# 21. Script engine

The script engine should consume only:

1. an approved idea
2. the evidence attached to that idea
3. the approved script configuration

It should produce:

- hook
- sections
- narration
- visual notes
- closing
- fact-check flags
- version number

Every script should remain traceable to its source idea.

---

# 22. Production engine

The production layer should eventually automate:

```text
Script
 ↓
Asset plan
 ↓
Voice generation
 ↓
Visual acquisition/generation
 ↓
Timeline assembly
 ↓
Rendering
 ↓
Quality checks
 ↓
Final video
```

Do not couple this layer to a single video-generation vendor.

The `ProductionJob` model is intentionally provider-independent.

---

# 23. Publishing engine

The publishing layer should eventually support:

- title
- description
- tags
- thumbnail
- scheduling
- privacy state
- external video ID
- publish status

For YouTube, OAuth credentials must remain server-side.

The browser should never receive a YouTube client secret or refresh token.

---

# 24. Analytics engine

The analytics engine should periodically collect platform metrics and normalize them into `VideoMetrics`.

Example loop:

```text
Published video
      ↓
Analytics provider
      ↓
Metrics snapshot
      ↓
Learning engine
      ↓
Learning signals
      ↓
Idea intelligence
```

The important point is that analytics should become input to future decisions rather than merely a dashboard chart.

---

# 25. Learning engine

Example learning signals:

```text
CTR signal
Retention signal
Topic signal
Hook signal
Title signal
Thumbnail signal
Length signal
Revenue signal
Audience signal
```

Later, these should become structured reusable knowledge rather than free-text notes.

---

# 26. Automation roadmap

V0:

```text
Synchronous JobRunner
```

Production evolution:

```text
FastAPI
  ↓
Queue
  ↓
Worker
  ↓
Job
  ↓
Provider
```

A likely later stack is:

```text
Redis
Celery/RQ or equivalent worker system
```

Do not introduce the queue until the business workflow actually needs it.

---

# 27. Recommended production evolution

### Stage 1 — Foundation

- PostgreSQL
- FastAPI
- GitHub
- GitHub Actions
- Vercel
- GitHub Pages
- environment secrets
- API monitoring

### Stage 2 — Content intelligence

- real research providers
- LLM provider adapters
- idea generation
- idea clustering
- human review UI

### Stage 3 — Script automation

- script generation
- fact-check workflow
- script versioning
- review/approval

### Stage 4 — Production

- asset management
- voice generation
- video assembly
- rendering workers
- quality checks

### Stage 5 — Publishing

- YouTube OAuth
- scheduled publishing
- thumbnail workflow
- publishing status

### Stage 6 — Learning

- YouTube Analytics integration
- performance snapshots
- learning signals
- score-weight adaptation

### Stage 7 — Full automation

```text
Research → Ideas → Review → Script → Production → Publish → Analytics → Learn
```

with human intervention concentrated at the high-value approval points.

---

# 28. Production checklist

Before calling the system production-ready for real business traffic:

### Infrastructure

- [ ] PostgreSQL database provisioned
- [ ] Database backups enabled
- [ ] Vercel production project configured
- [ ] GitHub Pages configured
- [ ] Custom domains verified if used
- [ ] HTTPS verified

### Security

- [ ] No secrets committed to GitHub
- [ ] Production API token configured
- [ ] CORS restricted to real dashboard origins
- [ ] Database credentials stored as Vercel secrets
- [ ] LLM credentials stored as Vercel secrets
- [ ] YouTube OAuth secrets stored server-side

### Software

- [ ] Test suite green
- [ ] Database migrations applied
- [ ] API health check working
- [ ] Dashboard reads API successfully
- [ ] Error states visible
- [ ] Logging configured
- [ ] Monitoring configured

### Business workflow

- [ ] Real research provider connected
- [ ] Real LLM provider connected
- [ ] Human review workflow implemented
- [ ] Script generation implemented
- [ ] Production provider implemented
- [ ] YouTube publishing implemented
- [ ] YouTube analytics implemented
- [ ] Learning loop implemented

### Operational

- [ ] Backup/restore tested
- [ ] Failed jobs can be retried
- [ ] Provider failures do not destroy workflow state
- [ ] Every generated asset has provenance
- [ ] Every published video can be traced back to its idea

---

# 29. Troubleshooting

## API returns 500

Check:

1. Vercel runtime logs.
2. `DATABASE_URL`.
3. PostgreSQL network/access settings.
4. Migration state.
5. Python dependency installation.

## Dashboard says API Offline

Check:

1. API URL in `dashboard/index.html`.
2. Open the API `/health` endpoint.
3. Check browser CORS errors.
4. Check Vercel runtime logs.
5. Verify the dashboard domain is present in `CONTENTOS_CORS_ORIGINS`.

## Database connection fails

Check the exact PostgreSQL URL and whether SSL is required by the provider.

## Ideas are empty

This is expected until ideas are inserted into the configured database. The dashboard must not fabricate content.

## LLM fails

Check:

- provider name
- model name
- provider API key
- provider quota
- structured-output validity

## YouTube publishing fails

Check:

- OAuth authorization
- refresh token
- API quota
- channel permissions
- video metadata

---

# 30. Backup strategy

Production data should be backed up by the PostgreSQL provider.

At minimum:

```text
Daily automated backup
+
Periodic restore test
```

A backup that has never been restored is not a verified recovery plan.

---

# 31. Observability

Production monitoring should cover:

### API

- request count
- latency
- 4xx/5xx rate
- health status

### Database

- connection failures
- query latency
- storage
- backup status

### Automation

- queued jobs
- failed jobs
- retry count
- execution duration

### AI

- provider errors
- token usage
- cost
- structured-output failures

### Content

- ideas generated
- ideas approved
- scripts generated
- videos rendered
- videos published
- analytics ingestion status

---

# 32. Cost control

The most expensive part of the eventual system is likely to be content production and AI/API usage rather than the basic dashboard.

Track:

```text
Cost per research batch
Cost per idea
Cost per script
Cost per video
Cost per published video
Revenue per published video
```

The goal is to make unit economics visible before scaling volume.

---

# 33. Engineering principles

### 1. Do not overbuild before validation

A small system that produces real learning is more valuable than a giant unused platform.

### 2. Keep business logic provider-independent

Providers can change. The workflow should not.

### 3. Keep data traceable

Every output should be traceable backward:

```text
Video
 ↓
Publish record
 ↓
Production job
 ↓
Script
 ↓
Idea
 ↓
Research evidence
```

### 4. Humans own important decisions

Automation should reduce repetitive work, not remove control from the operator.

### 5. Never fake live data

If the database/API is unavailable, show an error state.

### 6. Measure before optimizing

Performance data should drive later scoring changes.

---

# 34. What is implemented today

The current repository already contains the architectural foundation for:

- research models and normalization
- provider-independent LLM contracts
- idea generation
- transparent idea scoring
- human review contracts
- script models
- production job models
- publishing models
- analytics models
- learning signals
- automation jobs
- SQLite development persistence
- PostgreSQL production boundary
- FastAPI API
- live dashboard API integration
- GitHub Actions testing
- GitHub Pages dashboard deployment
- Vercel configuration
- production PostgreSQL migration
- production migration runner

The repository should **not** be described as having fully automated YouTube production yet. Real external provider integrations still need credentials and implementation.

---

# 35. The complete operating model

Once all integrations are enabled, the intended operating model is:

```text
                    ┌──────────────┐
                    │    RESEARCH  │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │     IDEAS    │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │    SCORING   │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │ HUMAN REVIEW │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │    SCRIPT    │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │  PRODUCTION  │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   PUBLISH    │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   ANALYTICS  │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   LEARNING   │
                    └──────┬───────┘
                           │
                           └──────────────→ IDEAS
```

The dashboard is the operator's control center for this loop.

---

# 36. One-command mental model

For local development:

```text
clone
 ↓
venv
 ↓
pip install
 ↓
.env
 ↓
pytest
 ↓
uvicorn
 ↓
open dashboard
```

For production:

```text
GitHub
 ↓
GitHub Actions tests
 ↓
Vercel deployment
 ↓
PostgreSQL
 ↓
FastAPI
 ↓
GitHub Pages dashboard
```

---

# 37. Final distinction: product-ready vs business-ready

A production-ready software foundation means the system has:

- clear architecture
- persistent production storage
- deployment configuration
- tests
- secrets management
- health checks
- documented operations
- observable failure states

A business-ready ContentOS additionally requires the real external integrations:

```text
Research providers
LLM provider
YouTube OAuth/API
Video production stack
Analytics API
Publishing automation
```

Those integrations require real accounts, credentials, quotas, provider-specific decisions, and operational testing. They should be enabled one at a time and validated end-to-end.

**This distinction is intentional. It prevents ContentOS from looking complete while silently depending on demo data or unconfigured external services.**
