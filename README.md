# ContentOS

ContentOS is the internal content operating system for Business #1: a faceless, AI-assisted media business.

The product is designed around a measurable feedback loop rather than a simple AI content generator:

`Research → Ideas → Scoring → Human Review → Script → Production → Publish → Analytics → Learning → Ideas`

## What exists now

The repository contains the software foundation for:

- resilient YouTube research ingestion (YouTube Data API → yt-dlp → RSS fallback)
- real RSS/Atom research ingestion
- provider-independent LLM contracts
- OpenAI structured generation adapter
- idea generation and transparent scoring
- human review workflow contracts
- real script generation service
- OpenAI text-to-speech adapter
- FFmpeg video renderer
- YouTube OAuth helper
- YouTube resumable upload adapter
- YouTube Analytics adapter
- analytics/learning models
- automation jobs
- SQLite local development
- PostgreSQL production persistence boundary
- FastAPI API
- live dashboard API integration
- GitHub Actions tests
- GitHub Pages dashboard
- Vercel deployment configuration
- production database migration

The dashboard is intentionally no longer allowed to pretend that demo numbers are live. If the API is unavailable, it shows an API-offline state.

## Quick start

### 1. Clone

```bash
git clone https://github.com/sreevishnubn/content-os.git
cd content-os
```

### 2. Create a Python environment

```bash
python -m venv .venv
```

Activate it using your operating system's normal virtual-environment command.

### 3. Install

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configure

Copy `.env.example` to `.env`.

For local development leave `DATABASE_URL` empty. ContentOS then uses SQLite at `data/content.db`.

### 5. Test

```bash
python -m pytest -q
```

### 6. Start the API

```bash
python -m uvicorn app.api.app:app --reload --port 8000
```

Open:

- API: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

## Real integrations

Read **[docs/REAL_INTEGRATIONS_GUIDE.md](docs/REAL_INTEGRATIONS_GUIDE.md)** for the complete setup of research, OpenAI, TTS, FFmpeg, YouTube OAuth, publishing, analytics and learning.

## Production readiness

The production path is split into two runtimes:

- **Vercel:** FastAPI API, authentication, database access and lightweight queue orchestration.
- **Worker:** TTS + FFmpeg rendering and artifact upload to S3-compatible object storage.

A production render job requires approved asset URIs. The worker creates narration, renders MP4, uploads it to `CONTENTOS_ARTIFACT_BUCKET`, and marks the production job `READY`. The API then materializes the artifact only when YouTube needs to upload it.

Required worker variables:

```text
OPENAI_API_KEY=<secret>
CONTENTOS_TTS_MODEL=gpt-4o-mini-tts
CONTENTOS_TTS_VOICE=alloy
CONTENTOS_ARTIFACT_BUCKET=<private-bucket>
CONTENTOS_ARTIFACT_PREFIX=contentos/renders
AWS_ACCESS_KEY_ID=<secret>
AWS_SECRET_ACCESS_KEY=<secret>
AWS_DEFAULT_REGION=<region>
```

For local development, omit the bucket and ContentOS writes renders to `data/output`. Hosted production should use object storage.

## Production architecture

```text
GitHub
  │
  ├── CI/tests
  └── source
       │
       ├──────────────→ GitHub Pages → Dashboard
       │                              │
       │                              │ HTTPS
       │                              ▼
       └──────────────→ Vercel → FastAPI API
                                      │
                                      ▼
                                PostgreSQL

Worker/compute
  ├── research ingestion
  ├── TTS
  ├── FFmpeg rendering
  ├── YouTube publishing
  └── analytics ingestion
```

SQLite is for local development. Production persistence must use a hosted PostgreSQL database through `DATABASE_URL`. Video rendering should run on worker/compute infrastructure rather than inside a Vercel request. The worker should register the resulting MP4 as an HTTPS or s3:// artifact URI; the publishing API materializes that artifact temporarily for YouTube upload.

## Production database

Set:

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
```

Then apply the migration:

```bash
python scripts/migrate.py
```

Never commit database credentials.

## Production environment variables

At minimum:

```text
CONTENTOS_ENVIRONMENT=production
DATABASE_URL=<managed-postgresql-url>
CONTENTOS_API_TOKEN=<long-random-secret>
CONTENTOS_CORS_ORIGINS=https://sreevishnubn.github.io,https://dashboard.youtube.analysis.com
CONTENTOS_LLM_PROVIDER=openrouter
CONTENTOS_LLM_MODEL=openrouter/free
OPENROUTER_API_KEY=<secret>
CONTENTOS_RESEARCH_FEEDS=<comma-separated-feeds>
YOUTUBE_API_KEY=<optional-official-youtube-data-api-key>
CONTENTOS_TTS_PROVIDER=openai
CONTENTOS_TTS_MODEL=gpt-4o-mini-tts
CONTENTOS_TTS_VOICE=alloy
```

YouTube OAuth credentials must remain server-side/private. See the integration guide.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service/database health |
| GET | `/api/dashboard/overview` | Live workflow counts |
| GET | `/api/dashboard/ideas` | Ranked ideas |
| POST | `/api/admin/bootstrap` | Initialize configured database |

## Production gate

The recommended publication state machine is:

`DISCOVERED → SHORTLISTED → APPROVED → SCRIPTING → PRODUCTION → REVIEW → READY_TO_PUBLISH → SCHEDULED → PUBLISHED`

Only `READY_TO_PUBLISH` content should be eligible for automatic publishing.

## Documentation

- **[Complete Product Guide](docs/CONTENTOS_COMPLETE_GUIDE.md)** — architecture, local setup, production operations and troubleshooting.
- **[Real Integrations Guide](docs/REAL_INTEGRATIONS_GUIDE.md)** — research, LLM, script, TTS, rendering, YouTube OAuth, publishing, analytics and learning.

## Important boundary

The integration code is real, but external accounts and credentials still have to be configured by the operator. The application cannot safely invent an OpenAI API key, Google OAuth client, YouTube authorization, PostgreSQL database, or research-feed configuration.

## Engineering principles

1. Business first, software second.
2. AI recommends; a human approves important decisions.
3. Store decisions and outcomes as data.
4. Keep provider integrations behind interfaces.
5. Keep data traceable from published output back to research evidence.
6. Never fabricate live data.
7. Measure before changing the scoring system.
8. Add infrastructure only when the business needs it.

<!-- Vercel deployment trigger: 2026-09-18 -->
