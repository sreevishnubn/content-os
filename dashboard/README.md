# ContentOS Dashboard

The dashboard is the operator control center for the ContentOS pipeline.

## Planned views

- Overview: pipeline health, content counts, performance and alerts
- Research: evidence, sources, freshness and research runs
- Ideas: candidate ideas, scoring, ranking and provenance
- Review: approve, reject and shortlist actions
- Scripts: outlines, scripts, versions and fact-check status
- Production: jobs, assets, rendering and failures
- Publishing: drafts, schedules, published videos and provider status
- Analytics: channel and video performance
- Learning: performance signals and reusable insights
- Automation: queued/running/failed jobs and retries
- AI: provider/model configuration, prompt versions and usage
- Settings: channel, workflow and system configuration

The UI will call a stable API/service boundary rather than importing domain
internals directly. This keeps the dashboard replaceable as the backend grows.
