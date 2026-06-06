# TODO

- [ ] Refactor `POST /api/pipeline/run` to run pipeline work in a background thread (via `run_in_thread`) and return immediately with `run_id`.
- [ ] Ensure background thread writes `PipelineActivity` updates to DB incrementally and updates `PipelineRun` counters/status at the end.
- [ ] Verify SSE endpoint (`/api/pipeline/{run_id}/events`) streams progress and UI shows the confirmation panel on completion.
- [ ] Quick sanity test: run the server and start a pipeline; confirm drafts get created and can be sent via `/api/pipeline/confirm-send`.

