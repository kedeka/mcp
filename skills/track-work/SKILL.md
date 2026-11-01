---
name: track-work
description: Track a coding agent's work against a Kedeka task across a session. Use when the user asks an agent to work on Kedeka tasks or wants its task time tracked automatically.
---

# Track work on a Kedeka task

Use one stable, unique `session_key` per agent session; use the harness session ID if available, otherwise generate an 8–100 character identifier using letters, digits, dots, underscores, colons, or hyphens. Reuse it within that session. Parallel subagents each need a different key; the orchestrator manages their runs.

1. At the start of relevant coding work, call `get_report` with `report: current_work` and `params` containing the session key. If available, also provide the Git remote as `repo` and the current `branch`; remove any credentials from the URL before sending it.
2. Continue `this_session` if it exists. If a previous task matches both the same repository and branch, resume it and tell the user in one line. Otherwise, use the returned task suggestions and ask which task to work on when their request does not already identify one. Never guess.
3. Start with `create_record`, `entity: agent_run`, a new `idempotency_key`, and `data` containing `task_id` and `session_key`, plus the known `host`, `repo`, `branch`, and `worktree`. This starts tracking and moves the task to in progress. Remember the returned run ID. Use `take_over: true` only when the user explicitly requests taking over another active session.
4. When switching to an authorized next task, create its run with the same session key and include `previous_summary`, and any `previous_pull_request_url` or `previous_commits` in `data`. The server closes the previous run.
5. When work finishes, call `update_record` with `entity: agent_run`, the run ID as `id`, and `data` containing a brief `summary` and any `pull_request_url` or `commits`. The default task status is `review`; set `task_status: done` only if the user asked for done, or `keep` for a pause.

Respect host confirmation prompts. If tracking is disabled or the connection lacks permission, tell the user and continue the actual work; never claim time was recorded without a successful response. A skill cannot guarantee a call after an abrupt session close: the server's idle lease closes forgotten runs. Optional local hooks are a separate opt-in integration.
