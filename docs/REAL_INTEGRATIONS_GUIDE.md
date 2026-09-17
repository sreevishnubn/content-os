# ContentOS — Real Integrations Guide

This document explains how to turn the ContentOS software foundation into a real operating system for a faceless YouTube/media business.

## 1. The production loop

```text
RSS / research feeds
      ↓
Research normalization + dedupe
      ↓
LLM idea generation / scoring
      ↓
Human approval
      ↓
LLM script generation
      ↓
TTS narration
      ↓
Image/video assets
      ↓
FFmpeg render
      ↓
Human final review
      ↓
YouTube OAuth upload
      ↓
YouTube Analytics
      ↓
Learning signals
      ↓
Future ideas
```

The system deliberately keeps a human gate before public publishing. Automatic publishing should only be enabled after the content format and failure paths have been validated.

## 2. Research provider

The first real provider is RSS/Atom. It requires no search API key and gives an auditable URL as the evidence source.

Set:

```text
CONTENTOS_RESEARCH_FEEDS=https://example.com/feed.xml,https://example.org/rss.xml
```

Run:

```bash
python scripts/contentos_pipeline.py --feeds "$CONTENTOS_RESEARCH_FEEDS" --limit 20
```

For Windows PowerShell:

```powershell
python scripts/contentos_pipeline.py --feeds $env:CONTENTOS_RESEARCH_FEEDS --limit 20
```

The research provider normalizes title, summary, source URL and publication date. The research engine deduplicates evidence before it reaches idea generation.

### Expanding research later

Add adapters behind `ResearchProvider` for Google News/RSS, YouTube Data API search, Reddit, news APIs, or domain-specific sources. Do not put provider calls directly into idea/scoring logic.

## 3. LLM provider

The first production adapter is OpenAI. Configure:

```text
CONTENTOS_LLM_PROVIDER=openai
CONTENTOS_LLM_MODEL=gpt-5-mini
OPENAI_API_KEY=...
```

The adapter uses the Responses API and structured output parsing so generated scripts are validated against the Pydantic `ContentScript` schema.

Test idea/script generation:

```bash
python scripts/contentos_pipeline.py --feeds "$CONTENTOS_RESEARCH_FEEDS" --limit 10 --generate-script
```

Keep API keys server-side. Never put an LLM key into GitHub Pages JavaScript.

## 4. Real script generation

`app/scripts/generator.py` sends an approved idea and evidence to the configured LLM provider.

The result must contain:

- hook
- sections
- narration
- visual notes
- closing
- fact-check-required items

Before production, reject a script if `fact_check_required` contains unresolved material claims.

## 5. Text-to-speech

ContentOS includes an OpenAI TTS adapter using the speech API.

Configure:

```text
CONTENTOS_TTS_PROVIDER=openai
CONTENTOS_TTS_MODEL=gpt-4o-mini-tts
CONTENTOS_TTS_VOICE=alloy
OPENAI_API_KEY=...
```

The current adapter enforces the provider's 4096-character input limit. Longer scripts should be chunked into narration segments and concatenated before rendering.

## 6. Video production

The first renderer is FFmpeg.

Install FFmpeg on the production worker and verify:

```bash
ffmpeg -version
```

Create a JSON file containing a generated `ContentScript`, then render:

```bash
python scripts/render_video.py data/scripts/script.json --images data/assets/shot1.jpg data/assets/shot2.jpg --output data/output/video.mp4
```

The renderer:

1. Builds narration from hook + sections + closing.
2. Generates MP3 narration.
3. Creates a 1920×1080 H.264/AAC MP4.
4. Uses supplied image assets as the visual sequence.

### Production hardening

For higher quality, add:

- scene-level durations
- subtitles/captions
- transitions
- B-roll selection
- music ducking
- loudness normalization
- thumbnail generation
- intro/outro templates
- asset licensing metadata
- render retries
- object storage

The renderer should eventually run on a dedicated worker, not inside the Vercel request lifecycle.

## 7. YouTube OAuth

Create a Google Cloud project and enable:

- YouTube Data API v3
- YouTube Analytics API

Create OAuth credentials for the YouTube channel owner. Download the client JSON to the local machine. Never commit it.

Run the one-time local consent flow using a small Python entrypoint or notebook that calls:

```python
from app.integrations.youtube_oauth import run_local_oauth
run_local_oauth("client_secret.json")
```

This creates:

```text
data/youtube_token.json
```

Keep that file private. Add it to `.gitignore` if it is not already covered by your data rules.

## 8. YouTube upload

Once a rendered video has passed human review:

```bash
python scripts/publish_youtube.py data/output/video.mp4 \
  --title "Your approved title" \
  --description "Approved description" \
  --tags "topic,keyword,channel" \
  --privacy private
```

Use `private` first. Verify the upload, title, description, audio, thumbnail and metadata. Only then move to scheduled/public publishing.

The adapter uses YouTube's resumable upload mechanism through Google's Python client.

## 9. Automatic publishing

Automatic publishing is a workflow policy, not just an API call.

Recommended state machine:

```text
DISCOVERED
   ↓
SHORTLISTED
   ↓
APPROVED
   ↓
SCRIPTING
   ↓
PRODUCTION
   ↓
REVIEW
   ↓
READY_TO_PUBLISH
   ↓
SCHEDULED
   ↓
PUBLISHED
```

Only `READY_TO_PUBLISH` should be eligible for an automated publishing worker.

Do not let a generic scheduled job publish every generated file.

## 10. YouTube Analytics

Pull daily analytics with:

```bash
python scripts/youtube_analytics.py 2026-09-16 2026-09-17
```

The adapter requests:

- views
- estimated minutes watched
- average view duration
- likes
- comments
- subscribers gained
- impressions
- impressions click-through rate

Persist each snapshot against the ContentOS publication/video ID. Do not overwrite historical snapshots; analytics is time-series data.

## 11. Learning feedback loop

The existing `LearningEngine` converts metrics into explicit signals such as:

```text
CTR
RETENTION
```

The next production version should expand this into signals such as:

- hook performance
- topic cluster performance
- title pattern
- thumbnail pattern
- first-30-second retention
- average percentage viewed
- traffic source
- subscriber conversion
- revenue per thousand views
- production cost
- time-to-publish

Do not automatically change scoring weights from one video. Use a statistically meaningful sample and retain the old model/version for comparison.

## 12. Automation architecture

Vercel is suitable for API requests and lightweight orchestration. Video rendering is compute-heavy and should run on a worker/compute environment.

Recommended eventual architecture:

```text
Vercel FastAPI
     ↓
PostgreSQL
     ↓
Queue
     ↓
Worker
 ┌───┼───────────────┐
 ↓   ↓               ↓
TTS FFmpeg        YouTube
```

The current synchronous job runner is intentionally small and can later be replaced by Redis/Celery or another queue without changing domain contracts.

## 13. Secrets

Never commit:

- OpenAI keys
- Google OAuth client secrets
- YouTube refresh tokens
- database passwords
- Vercel tokens
- storage credentials

Use Vercel environment variables for server-side API secrets and a secure secret store for worker credentials.

## 14. Go-live sequence

### Stage A — private validation

1. Configure PostgreSQL.
2. Configure OpenAI.
3. Configure RSS feeds.
4. Generate 10–20 research-derived ideas.
5. Manually review them.
6. Generate scripts.
7. Generate narration.
8. Render 3–5 videos.
9. Upload to YouTube as private.
10. Review quality.

### Stage B — controlled publishing

1. Publish a small batch.
2. Pull analytics daily.
3. Store snapshots.
4. Generate learning signals.
5. Compare performance across topics/hooks/titles.
6. Adjust prompts and scoring deliberately.

### Stage C — automation

Only after Stage B is stable:

1. Add scheduled research ingestion.
2. Add scheduled idea generation.
3. Add human review dashboard actions.
4. Add automated script generation after approval.
5. Add worker rendering.
6. Add scheduled YouTube publishing for `READY_TO_PUBLISH` only.
7. Add daily analytics ingestion.
8. Add weekly learning reports.

## 15. What is genuinely real now

Implemented in the repository:

- real RSS/Atom research ingestion
- real OpenAI LLM adapter
- structured script generation contract
- real OpenAI TTS adapter
- real FFmpeg rendering
- real YouTube OAuth helper
- real YouTube resumable upload adapter
- real YouTube Analytics adapter
- learning engine contracts
- production-oriented database boundary

Still requiring your external account configuration:

- OpenAI API key
- Google Cloud/YouTube OAuth application
- YouTube channel authorization
- production PostgreSQL instance
- FFmpeg worker environment
- real research feed list

Those credentials cannot be safely invented or embedded by the application.

## 16. Official references

- OpenAI API: https://developers.openai.com/api/docs/quickstart
- OpenAI audio/speech API: https://developers.openai.com/api/reference/cli/resources/audio/subresources/speech/methods/create
- YouTube Data API: https://developers.google.com/youtube/v3
- YouTube Analytics API: https://developers.google.com/youtube/analytics
