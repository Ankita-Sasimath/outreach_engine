from __future__ import annotations

import json
import time
from typing import Generator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.database import SessionLocal
from app.models import PipelineActivity, PipelineRun

router = APIRouter()


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


@router.get("/api/pipeline/{run_id}/events")
def pipeline_events(run_id: int) -> StreamingResponse:
    # Simple polling-based SSE stream: reads latest activity + counters.
    def _gen() -> Generator[str, None, None]:
        last_activity_id = 0

        while True:
            with SessionLocal() as db:
                run = (
                    db.query(PipelineRun)
                    .filter(PipelineRun.id == run_id)
                    .one_or_none()
                )
                if run is None:
                    yield _sse({"type": "error", "message": "run not found"})
                    return

                activities = (
                    db.query(PipelineActivity)
                    .filter(PipelineActivity.run_id == run_id)
                    .filter(PipelineActivity.id > last_activity_id)
                    .order_by(PipelineActivity.id.asc())
                    .limit(50)
                    .all()
                )

                for a in activities:
                    last_activity_id = max(last_activity_id, a.id)

                payload = {
                    "type": "snapshot",
                    "run_id": run.id,
                    "status": run.status,
                    "domain": run.domain,
                    "companies_found": run.companies_found,
                    "contacts_found": run.contacts_found,
                    "emails_resolved": run.emails_resolved,
                    "emails_ready": run.emails_ready,
                    "new_activity": [
                        {
                            "stage": a.stage,
                            "message": a.message,
                            "progress": a.progress,
                            "total": a.total,
                        }
                        for a in activities
                    ],
                }

                yield _sse(payload)

                if run.status in {"completed", "failed"}:
                    return

            time.sleep(1.0)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

    return StreamingResponse(_gen(), media_type="text/event-stream", headers=headers)

