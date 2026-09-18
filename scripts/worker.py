"""Long-running ContentOS worker for TTS/FFmpeg production jobs.

Run this on compute infrastructure with PostgreSQL, OpenAI and S3 credentials.
Vercel remains the API/orchestration layer; this process owns compute-heavy jobs.
"""
from __future__ import annotations

import os
import time

from app.automation.handlers import HANDLERS
from app.automation.scheduler import run_queued_jobs


def main() -> None:
    interval = max(5, int(os.getenv("CONTENTOS_WORKER_INTERVAL_SECONDS", "15")))
    batch = max(1, min(10, int(os.getenv("CONTENTOS_WORKER_BATCH_SIZE", "2"))))
    handlers = {"production_render": HANDLERS["production_render"]}

    print(f"ContentOS worker started: interval={interval}s batch={batch}")
    while True:
        try:
            result = run_queued_jobs(handlers, limit=batch)
            if result["processed"] or result["recovered"]:
                print(result, flush=True)
        except Exception as exc:
            print(f"Worker iteration failed: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
