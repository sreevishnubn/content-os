# ContentOS

ContentOS is the internal content operating system for Business #1: a faceless, AI-assisted media business.

The product is designed around a measurable feedback loop rather than a simple AI content generator:

`Research → Ideas → Scoring → Human Review → Script → Production → Publish → Analytics → Learning → Ideas`

## What exists now

The repository contains the software foundation for:

- research normalization
- provider-independent LLM contracts
- idea generation and transparent scoring
- human review workflow contracts
- script/production/publishing models
- analytics and learning models
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
```

SQLite is for local development. Production persistence must use a hosted PostgreSQL database through `DATABASE_URL`.

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
```

LLM and YouTube credentials should be added only when their integrations are enabled and must remain server-side.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service/database health |
| GET | `/api/dashboard/overview` | Live workflow counts |
| GET | `/api/dashboard/ideas` | Ranked ideas |
| POST | `/api/admin/bootstrap` | Initialize configured database |

## Documentation

The complete product, architecture, local setup, production deployment, database, security, dashboard, API, automation, troubleshooting, backup, observability and roadmap guide is here:

**[docs/CONTENTOS_COMPLETE_GUIDE.md](docs/CONTENTOS_COMPLETE_GUIDE.md)**

Read that document before deploying production.

## Important boundary

The software foundation is production-oriented, but the complete business automation is not claimed to be finished until real external integrations are configured and tested:

```text
Research provider
      ↓
LLM provider
      ↓
Script generation
      ↓
Production/rendering provider
      ↓
YouTube OAuth/publishing
      ↓
YouTube Analytics
      ↓
Learning loop
```

This distinction prevents demo data, missing credentials, or unimplemented providers from being mistaken for a working production business system.

## Engineering principles

1. Business first, software second.
2. AI recommends; a human approves important decisions.
3. Store decisions and outcomes as data.
4. Keep provider integrations behind interfaces.
5. Keep data traceable from published output back to research evidence.
6. Never fabricate live data.
7. Measure before changing the scoring system.
8. Add infrastructure only when the business needs it.
