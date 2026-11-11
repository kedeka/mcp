---
name: track-work
description: Record which Kedeka task a coding session works on and for how long. Use for implementation in a repository or when the user asks to track an agent task. Tracking never blocks work.
---

# Track coding work

Tracking records a task and its time. It is never a condition for reading, editing, running commands or ending a turn. Tool prefixes vary by harness; use the connected Kedeka server for the intended workspace. `get_help` at `projects/tracking` has the live contract.

1. Take the Git origin and branch, and remove credentials from the remote URL. Call `get_report` with `report: current_work` and `params: {session_key, repo, branch}`. Use the host's stable session identity; otherwise create one identifier once for this session.
2. Start the timer with `create_record`, `entity: agent_run`, a fresh `idempotency_key`, and `data: {session_key, repo, branch}` plus either `task_id` for a task that matches the request, or `task_title` so the server reuses the open task with that title in the repository's project or creates it. An authorized coding request includes finding or creating its task; do not ask again merely for tracking and never pick an unrelated suggestion.
3. Continue an existing run only when its task, repository and branch match, and tell the user when resuming. Do not take over another session unless asked. When switching away from unfinished work, pass `previous_task_status: keep`.
4. When the work stops, call `update_record`, `entity: agent_run`, with the run ID and a short `summary`, plus `commits` or `pull_request_url` when they exist. `task_status` is `review` by default; use `done` when the user accepts the work and `keep` to pause. Never claim tests that were not run.

`task_description`, `briefs_read` and `verification` are optional notes. A run left open is closed by the server's idle lease, so ending a turn needs no call. If the Kedeka server is unavailable, say so once and carry on with the request. An orchestrator records a separate run for each child agent with that child's own session identity.
