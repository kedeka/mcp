import importlib.util
import json
import tempfile
import hashlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".agents/hooks"))
import kedeka_claude as hooks


class ClaudeHooksTest(unittest.TestCase):
    def payload(self, event, **extra):
        return {"hook_event_name": event, "session_id": "parent", "cwd": "/repo", **extra}

    def apply(self, payload, state, now=1000):
        with patch.object(hooks.common, "git_context", return_value={"repo": "github.com/example/coding", "branch": "main"}):
            return hooks.lifecycle(payload, state, now=now)

    def prepared(self, state):
        run = {"id": "run-1", "is_active": True, "context": {"repo": "github.com/example/coding", "branch": "main", "worktree": "/repo", "work_protocol": {"version": 1}}}
        payload = self.payload("PostToolUse", tool_name="mcp__kedeka__create_record", tool_input={"entity": "agent_run", "data": {"session_key": "claude-code:parent"}}, tool_response={"content": [{"type": "text", "text": json.dumps({"run": run})}]})
        self.apply(payload, state)

    def test_claude_identity_cannot_collide_with_codex_or_children(self):
        self.assertEqual(hooks.session_key(self.payload("SessionStart")), "claude-code:parent")
        self.assertEqual(hooks.session_key(self.payload("SubagentStop", agent_id="child")), "claude-code:child")
        self.assertNotEqual(hooks.session_key(self.payload("SessionStart")), hooks.common.session_key(self.payload("SessionStart")))

    def test_start_context_uses_native_auth_and_supplies_git_context(self):
        result = self.apply(self.payload("SessionStart"), {})
        text = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn("session_key=claude-code:parent", text)
        self.assertIn("repo=github.com/example/coding", text)
        self.assertIn("worktree=/repo", text)
        self.assertIn("workflow selection belong to the user and host", text)
        self.assertIn("No skill-specific registration is required", text)
        for policy in ["council", "delegation permission", "No delegation", "Do not delegate", "Native-orchestration", "Jev"]:
            self.assertNotIn(policy, text)

    def test_edit_is_denied_until_native_mcp_returns_a_prepared_run(self):
        payload = self.payload("PreToolUse", tool_name="Edit")
        state = {}
        self.assertEqual(self.apply(payload, state)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.prepared(state)
        self.assertTrue(state["ready"])
        self.assertEqual(self.apply(payload, state, 1059), {})
        self.assertEqual(self.apply(payload, state, 1060)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(set(state), {"run_id", "checked_at", "ready", "cwd"})

    def test_read_only_discovery_does_not_require_a_task(self):
        for command in ["git status", "rtk --version", "git branch --show-current", "sed -n '1,20p' file"]:
            with self.subTest(command=command):
                self.assertEqual(self.apply(self.payload("PreToolUse", tool_name="Bash", tool_input={"command": command}), {}), {})

    def test_shared_classifier_allows_reads_and_artifacts_and_warns_on_unknown(self):
        for command in ["rg 'a|b' file | head", "git status && nl -ba file",
                        "rsvg-convert favicon.svg -o /tmp/favicon.png"]:
            with self.subTest(command=command):
                self.assertEqual(self.apply(self.payload("PreToolUse", tool_name="Bash", tool_input={"command": command}), {}), {})
        warning = self.apply(self.payload("PreToolUse", tool_name="Bash", tool_input={"command": "custom-tool"}), {})
        self.assertIn("systemMessage", warning)
        denied = self.apply(self.payload("PreToolUse", tool_name="Bash", tool_input={"command": "cat file > app.py"}), {})
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_another_server_or_session_cannot_forge_preparation(self):
        for name, key in [("mcp__other__create_record", "claude-code:parent"), ("mcp__kedeka__create_record", "claude-code:other")]:
            state = {}
            self.apply(self.payload("PostToolUse", tool_name=name, tool_input={"entity": "agent_run", "data": {"session_key": key}}, tool_response={"run": {"id": "fake", "is_active": True}}), state)
            self.assertEqual(state, {})

    def test_finish_clears_receipt_and_stop_requires_explicit_completion(self):
        state = {}
        self.prepared(state)
        self.assertEqual(self.apply(self.payload("Stop"), state)["decision"], "block")
        self.apply(self.payload("PostToolUse", tool_name="mcp__kedeka__update_record", tool_input={"entity": "agent_run", "id": "run-1"}, tool_response={"run": {"id": "run-1", "is_active": False}}), state)
        self.assertEqual(state, {})
        self.assertEqual(self.apply(self.payload("Stop"), state), {})

    def test_get_report_refreshes_receipt_without_starting_another_run(self):
        state = {}
        self.prepared(state)
        run = {"id": "run-1", "is_active": True, "context": {"repo": "github.com/example/coding", "branch": "main", "worktree": "/repo", "work_protocol": {"version": 1}}}
        self.apply(self.payload("PostToolUse", tool_name="mcp__kedeka__get_report", tool_input={"report": "current_work", "params": {"session_key": "claude-code:parent"}}, tool_response={"this_session": run}), state, 1200)
        self.assertEqual(self.apply(self.payload("PreToolUse", tool_name="Write"), state, 1201), {})

    def test_session_end_queues_only_the_scoped_close_capability_and_original_time(self):
        state = {"run_id": "run-1", "ready": True, "close_url": "https://kedeka.com/ai/agent-runs/run-1/session-end?signature=test"}
        self.apply(self.payload("SessionEnd"), state, 1000)
        self.assertEqual(state, {"pending_close": {"url": "https://kedeka.com/ai/agent-runs/run-1/session-end?signature=test", "occurred_at": "1970-01-01T00:16:40Z"}})
        self.assertEqual(self.apply(self.payload("PreToolUse", tool_name="Write"), state)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_close_is_durable_before_network_and_retries_next_session(self):
        with tempfile.TemporaryDirectory() as home:
            directory = Path(home) / ".local/state/kedeka/claude-hooks"
            directory.mkdir(parents=True)
            identity = hashlib.sha256(b"claude-code:parent").hexdigest()
            path = directory / (identity + ".json")
            path.write_text(json.dumps({"run_id": "run-1", "close_url": "https://kedeka.com/ai/agent-runs/run-1/session-end?signature=test"}))
            def fail_after_durable(pending):
                self.assertEqual(json.loads(path.read_text())["pending_close"], pending)
                raise OSError("offline")
            with patch.object(hooks.Path, "home", return_value=Path(home)), patch.object(hooks.sys, "stdin", io.StringIO(json.dumps(self.payload("SessionEnd")))), patch.object(hooks.sys, "stdout", new_callable=io.StringIO), patch.object(hooks.time, "time", return_value=1000), patch.object(hooks, "send_close", side_effect=fail_after_durable):
                hooks.main()
            self.assertIn("pending_close", json.loads(path.read_text()))
            with patch.object(hooks, "send_close") as send:
                hooks.flush_pending(directory, directory / "new-session.json")
                self.assertEqual(send.call_args.args[0]["occurred_at"], "1970-01-01T00:16:40Z")
            self.assertNotIn("pending_close", json.loads(path.read_text()))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


    def test_close_requires_json_acknowledgement_and_sends_no_task_fields(self):
        with patch.object(hooks.urllib.request, "urlopen") as opening:
            response = opening.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'{"closed":true}'
            hooks.send_close({"url": "https://kedeka.com/ai/agent-runs/run-1/session-end?signature=test", "occurred_at": "1970-01-01T00:16:40Z"})
            request = opening.call_args.args[0]
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(json.loads(request.data), {"occurred_at": "1970-01-01T00:16:40Z"})
            response.read.return_value = b'<html>not a callback acknowledgement</html>'
            with self.assertRaises(ValueError):
                hooks.send_close({"url": "https://kedeka.com/ai/agent-runs/run-1/session-end?signature=test", "occurred_at": "1970-01-01T00:16:40Z"})


    def test_close_transport_rejects_unexpected_destinations(self):
        for url in ["https://other.example/ai/agent-runs/one/session-end", "http://kedeka.com/ai/agent-runs/one/session-end", "https://kedeka.com/other"]:
            with self.assertRaises(ValueError):
                hooks.send_close({"url": url, "occurred_at": "1970-01-01T00:16:40Z"})


    def test_errors_cannot_clear_or_authorize_a_receipt(self):
        self.assertIsNone(hooks.response_data({"isError": True, "structuredContent": {"run": {"id": "fake"}}}))
        self.assertIsNone(hooks.response_data({"content": [{"text": "not JSON"}]}))


if __name__ == "__main__":
    unittest.main()
