#!/usr/bin/env python3
"""Claude hook receipts; lifecycle RPCs use Claude's native MCP connection."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import urllib.request
import urllib.error
from urllib.parse import urlsplit
import kedeka as common


def session_key(payload):
    return "claude-code:" + common.session_key(payload).split(":", 1)[1]


def response_data(value, depth=0):
    if depth > 8:
        return None
    if isinstance(value, dict):
        if "error" in value or value.get("isError"):
            return None
        if "run" in value or "this_session" in value:
            return value
        for key in ("structuredContent", "content", "text"):
            result = response_data(value.get(key), depth + 1)
            if result is not None:
                return result
    elif isinstance(value, list):
        for item in value:
            result = response_data(item, depth + 1)
            if result is not None:
                return result
    elif isinstance(value, str) and len(value) < 100000:
        try:
            return response_data(json.loads(value), depth + 1)
        except (ValueError, TypeError):
            pass
    return None


def send_close(pending):
    url = pending["url"]
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "kedeka.com" or not parsed.path.startswith("/ai/agent-runs/") or not parsed.path.endswith("/session-end"):
        raise ValueError("Invalid lifecycle callback")
    request = urllib.request.Request(url, data=json.dumps({"occurred_at": pending["occurred_at"]}).encode(), headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Kedeka-Claude-Hook/1"}, method="POST")
    with urllib.request.urlopen(request, timeout=3) as response:
        if response.status != 200 or not isinstance(json.loads(response.read(4096)).get("closed"), bool):
            raise OSError("Lifecycle callback failed")


def lifecycle(payload, state, now=None):
    now = time.time() if now is None else now
    event = payload["hook_event_name"]
    key = session_key(payload)
    if event == "SessionStart":
        repo = common.git_context(payload["cwd"])
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext":
            f"Kedeka native Claude Code hooks active. session_key={key}; repo={repo['repo']}; branch={repo['branch']}; worktree={payload['cwd']}. "
            "Use project server kedeka (mcp__kedeka__* tools) for tracking so its native responses refresh this guard. Before coding, follow get_help projects/tracking/prepare, read relevant briefs, find or create the matching task and prepare agent_run with this identity, worktree and lifecycle_hooks=true. "
            "Finish with honest summary, verification and done after acceptance criteria pass, review for outstanding review, pause incomplete work. "
            "Refresh get_report current_work with this session_key when the local edit guard asks. " + common.TRACKING_SCOPE}}
    if event == "PostToolUse":
        name = payload.get("tool_name", "")
        args = payload.get("tool_input") or {}
        if not name.startswith("mcp__kedeka__"):
            return {}
        report = name.endswith("__get_report") and args.get("report") == "current_work" and (args.get("params") or {}).get("session_key") == key
        create = name.endswith("__create_record") and args.get("entity") == "agent_run" and (args.get("data") or {}).get("session_key") == key
        update = name.endswith("__update_record") and args.get("entity") == "agent_run" and args.get("id") == state.get("run_id")
        if not (report or create or update):
            return {}
        data = response_data(payload.get("tool_response"))
        if data is None:
            return {}
        run = data.get("this_session") if report else data.get("run")
        if not run or not run.get("is_active"):
            state.clear()
            return {}
        context = run.get("context") or {}
        repo = common.git_context(payload["cwd"])
        state.update(run_id=run["id"], checked_at=now,
            ready=bool(context.get("work_protocol")) and bool(context.get("worktree")) and context.get("repo") == repo["repo"]
                and (not context.get("branch") or context["branch"] == repo["branch"])
                and os.path.realpath(context.get("worktree", "")) == os.path.realpath(payload["cwd"]),
            cwd=os.path.realpath(payload["cwd"]))
        if run.get("lifecycle_close_url"):
            state["close_url"] = run["lifecycle_close_url"]
    elif event in {"SessionEnd", "StopFailure"}:
        close_url = state.get("close_url")
        state.clear()
        if close_url:
            state["pending_close"] = {"url": close_url, "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))}
    elif event == "PreToolUse":
        if not common.requires_work(payload):
            return common.tracking_notice(payload)
        if not (state.get("ready") and state.get("cwd") == os.path.realpath(payload["cwd"]) and now - state.get("checked_at", 0) < 60):
            return common.deny_work(f"Read/prepare Kedeka task and briefs before editing. Refresh mcp__kedeka__get_report current_work with session_key={key}. If no matching task exists, create automatically per projects/tracking/prepare; include worktree={payload['cwd']} and lifecycle_hooks=true.")
    elif event in {"Stop", "SubagentStop"} and state.get("run_id"):
        return {"decision": "block", "reason": "Save agent_run results through MCP before stopping: summary, verification and done after acceptance; review for external review or event=pause for unfinished work."}
    return {}


def flush_pending(directory, current_path):
    attempts = 0
    for path in sorted(directory.glob("*.json")):
        if path == current_path:
            continue
        with path.with_suffix(".lock").open("a+") as lock:
            os.chmod(lock.name, 0o600)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                state = json.loads(path.read_text())
                if not state.get("pending_close"):
                    continue
                attempts += 1
                try:
                    send_close(state["pending_close"])
                except urllib.error.HTTPError as error:
                    if error.code not in {403, 404, 410}:
                        raise
                state.pop("pending_close", None)
                with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as saved:
                    json.dump(state, saved)
                os.replace(saved.name, path)
            except (BlockingIOError, OSError, ValueError):
                pass
        if attempts >= 2:
            break


def main():
    payload = json.load(sys.stdin)
    directory = Path.home() / ".local/state/kedeka/claude-hooks"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    identity = hashlib.sha256(session_key(payload).encode()).hexdigest()
    path = directory / (identity + ".json")
    with (directory / (identity + ".lock")).open("a+") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text()) if path.exists() else {}
        result = lifecycle(payload, state)
        def save_state():
            with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as saved:
                json.dump(state, saved)
                saved.flush()
                os.fsync(saved.fileno())
            os.replace(saved.name, path)
        save_state()
        if state.get("pending_close"):
            try:
                send_close(state["pending_close"])
                state.pop("pending_close")
                save_state()
            except Exception:
                pass
    if payload["hook_event_name"] == "SessionStart":
        flush_pending(directory, path)
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Kedeka hook failed; repair local receipt state before editing.", file=sys.stderr)
        sys.exit(2)
