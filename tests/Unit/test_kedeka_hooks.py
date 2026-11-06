"""Lifecycle contracts with a fake transport, without OAuth, models or network."""

import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("kedeka_hooks", Path(__file__).resolve().parents[2] / ".agents/hooks/kedeka.py")
hooks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hooks)


class FakeMcp:
    def __init__(self, run=None, fail=False):
        self.run = run
        self.fail = fail
        self.calls = []
        self.closed = False

    def call(self, name, arguments):
        self.calls.append((name, arguments))
        if self.fail:
            raise OSError("offline secret must never escape")
        return {"this_session": self.run} if name == "get_report" else {"operation": "ok"}

    def close(self):
        self.closed = True


class LifecycleTest(unittest.TestCase):
    def event(self, name, **extra):
        return {"hook_event_name": name, "session_id": "parent-session", "cwd": "/tmp", **extra}

    def apply(self, payload, state, fake, now=1000):
        with patch.object(hooks, "git_context", return_value={"repo": "github.com/example/coding", "branch": "main"}):
            return hooks.lifecycle(payload, state, client_factory=lambda cwd: fake, clock=lambda: now)

    def test_parent_and_children_have_distinct_stable_keys(self):
        self.assertEqual(hooks.session_key(self.event("Stop")), "codex:parent-session")
        self.assertEqual(hooks.session_key(self.event("SubagentStop", agent_id="child-id")), "codex:child-id")
        self.assertNotEqual(hooks.session_key(self.event("SubagentStop", agent_id="a")), hooks.session_key(self.event("SubagentStop", agent_id="b")))
        self.assertEqual(hooks.session_key(self.event("PostToolUse", session_id="child-id")), hooks.session_key(self.event("SubagentStop", agent_id="child-id")))

    def test_untrusted_identity_is_hashed_and_missing_identity_fails(self):
        self.assertRegex(hooks.session_key(self.event("Stop", session_id="../../session")), r"^codex:[a-f0-9]{64}$")
        with self.assertRaises(ValueError):
            hooks.session_key({})

    def test_context_identifies_session_and_does_not_select_suggested_task(self):
        fake = FakeMcp()
        result = self.apply(self.event("SessionStart"), {}, fake)
        self.assertIn("session_key=codex:parent-session", result["hookSpecificOutput"]["additionalContext"])
        self.assertEqual([name for name, _ in fake.calls], ["get_report"])
        self.assertTrue(fake.closed)

    def test_context_only_describes_tracking_without_selecting_execution_workflows(self):
        for event in ["SessionStart", "UserPromptSubmit", "SubagentStart"]:
            with self.subTest(event=event):
                fake = FakeMcp()
                result = self.apply(self.event(event), {}, fake)
                context = result["hookSpecificOutput"]["additionalContext"]
                self.assertIn("workflow selection belong to the user and host", context)
                self.assertIn("No skill-specific registration is required", context)
                self.assertIn("do not require a prepared task", context)
                for policy in ["council", "delegation permission", "No delegation", "Do not delegate", "Native-orchestration", "Jev"]:
                    self.assertNotIn(policy, context)
                self.assertEqual([name for name, _ in fake.calls], ["get_report"])

    def test_shell_discovery_regressions_are_allowed_offline_on_both_tool_names(self):
        for name, field in [("Bash", "command"), ("exec_command", "cmd")]:
            for command in ["rtk --version", "rtk --help", "git branch --show-current",
                            "rtk proxy git branch --show-current", "git branch -a",
                            "sed -n '200,232p' .agents/hooks/kedeka.py",
                            "rtk proxy sed -n '1,155p' tests/example.py"]:
                with self.subTest(name=name, command=command):
                    fake = FakeMcp(fail=True)
                    result = self.apply(self.event("PreToolUse", tool_name=name, tool_input={field: command}), {}, fake)
                    self.assertEqual(result, {})
                    self.assertEqual(fake.calls, [])

    def test_similar_mutating_commands_still_require_preparation(self):
        for command in ["git branch new", "git branch -D old", "git branch -m renamed",
                        "sed -i 's/old/new/' file", "rtk --version && touch file"]:
            with self.subTest(command=command):
                result = self.apply(self.event("PreToolUse", tool_name="Bash", tool_input={"command": command}), {}, FakeMcp())
                self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_quoted_patterns_and_composed_reads_do_not_contact_mcp(self):
        commands = [
            "git remote get-url origin && git branch --show-current && cat public/favicon.svg",
            "rtk proxy rg -n 'command|requires_work|receipt' .agents/hooks/kedeka.py",
            "rg 'a;b & c > d < e' file | head -n 5",
            "cat file\nnl -ba file; stat file",
            "printf '%s' '$(touch literal)'",
            "cat file 2>&1 | wc -l",
            "git branch --list feature && git tag --list && git stash list",
            "rg 'a|b' file # comment with > and ;\ncat file",
        ]
        for name, field in [("Bash", "command"), ("exec_command", "cmd")]:
            for command in commands:
                with self.subTest(name=name, command=command):
                    fake = FakeMcp(fail=True)
                    result = self.apply(self.event("PreToolUse", tool_name=name, tool_input={field: command}), {}, fake)
                    self.assertEqual(result, {})
                    self.assertEqual(fake.calls, [])

    def test_unknown_commands_warn_without_network_or_denial(self):
        for command in ["python3 edit.py", "custom-tool --inspect", "echo 'unterminated",
                        'printf "%s" "$(touch file)"', "rg --pre=script term",
                        "sed -n '1w output' file", "find . -exec script {} +"]:
            with self.subTest(command=command):
                fake = FakeMcp(fail=True)
                result = self.apply(self.event("PreToolUse", tool_name="Bash", tool_input={"command": command}), {}, fake)
                self.assertIn("systemMessage", result)
                self.assertNotIn("permissionDecision", str(result))
                self.assertEqual(fake.calls, [])

    def test_artifacts_outside_repo_are_allowed_but_repo_targets_are_guarded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            (root / ".git").mkdir()
            outside = Path(directory) / "artifact.png"
            commands = [
                "rsvg-convert -w 300 -h 300 public/favicon.svg -o {target}",
                "rsvg-convert public/favicon.svg --output={target}",
                "sips -z 300 300 favicon.png --out {target}",
                "magick favicon.svg -resize 300x300 {target}",
                "cat public/favicon.svg > {target}",
                "printf '%s' output >> {target}",
                "cat file >& {target}",
                "cat file 2> {target}",
                "cp public/favicon.svg {target}",
                "touch {target}",
            ]
            for command in commands:
                for target, required in [(outside, False), (root / "favicon.png", True)]:
                    with self.subTest(command=command, target=target):
                        payload = self.event("PreToolUse", cwd=str(root), tool_name="exec_command", tool_input={"cmd": command.format(target=target)})
                        self.assertEqual(hooks.requires_work(payload), required)
            for name in ["Write", "Edit", "NotebookEdit"]:
                payload = self.event("PreToolUse", cwd=str(root), tool_name=name, tool_input={"file_path": str(outside)})
                self.assertEqual(self.apply(payload, {}, FakeMcp(fail=True)), {})
                payload["tool_input"]["file_path"] = str(root / "file.py")
                self.assertTrue(hooks.requires_work(payload))
            payload = self.event("PreToolUse", cwd=str(root), tool_name="apply_patch", tool_input={"patch": "*** Begin Patch\n*** Add File: " + str(outside) + "\n+artifact\n*** End Patch"})
            self.assertFalse(hooks.requires_work(payload))
            payload["tool_input"]["patch"] += "\n*** Update File: app.py"
            self.assertTrue(hooks.requires_work(payload))

    def test_targets_use_workdir_cd_and_resolved_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            (root / ".git").mkdir()
            (root / "subdir").mkdir()
            outside = Path(directory) / "outside"
            outside.mkdir()
            (outside / "back").symlink_to(root, target_is_directory=True)
            (root / "external").symlink_to(outside, target_is_directory=True)
            for command, required in [
                ("cd subdir && touch file", True),
                ("cd ../outside && touch file", False),
                ("cd ../outside | cat; touch file", True),
                ("cd ../outside & touch file", True),
                ("touch ../outside/back/file", True),
                ("touch external/file", False),
                ("git status && touch app.py", True),
                ("custom-tool && touch app.py", True),
                ("cat file > ../outside/file; touch app.py", True),
            ]:
                with self.subTest(command=command):
                    payload = self.event("PreToolUse", cwd=str(root), tool_name="Bash", tool_input={"command": command})
                    self.assertEqual(hooks.requires_work(payload), required)
            payload = self.event("PreToolUse", cwd=str(root), tool_name="exec_command", tool_input={"cmd": "touch file", "workdir": str(outside)})
            self.assertFalse(hooks.requires_work(payload))
            payload["tool_input"]["workdir"] = "../outside"
            self.assertFalse(hooks.requires_work(payload))

    def test_all_close_events_preserve_status_and_results(self):
        for event, action in hooks.CLOSE_EVENTS.items():
            with self.subTest(event=event):
                fake = FakeMcp({"id": "run-1"})
                state = {}
                self.apply(self.event(event), state, fake)
                self.assertEqual(fake.calls[-1], ("update_record", {"entity": "agent_run", "id": "run-1", "data": {"event": action, "session_key": "codex:parent-session", "occurred_at": "1970-01-01T00:16:40Z"}}))
                self.assertIsNone(state["run_id"])
                self.assertNotIn("pending", state)

    def test_child_stop_only_addresses_child_session(self):
        fake = FakeMcp({"id": "child-run"})
        self.apply(self.event("SubagentStop", agent_id="child-1"), {}, fake)
        self.assertEqual(fake.calls[0][1]["params"]["session_key"], "codex:child-1")
        self.assertEqual(fake.calls[-1][1]["id"], "child-run")

    def test_heartbeat_is_throttled_but_tracking_tool_and_stop_are_not(self):
        state = {"checked_at": 999}
        fake = FakeMcp({"id": "run-1"})
        self.apply(self.event("PostToolUse"), state, fake)
        self.assertEqual(fake.calls, [])
        self.apply(self.event("PostToolUse", tool_input={"entity": "agent_run"}), state, fake)
        self.assertEqual(fake.calls[-1][1]["data"]["event"], "heartbeat")
        self.apply(self.event("Stop"), state, fake)
        self.assertEqual(fake.calls[-1][1]["data"]["event"], "pause")

    def test_no_active_run_never_mutates_another_run(self):
        fake = FakeMcp()
        self.apply(self.event("Stop"), {"run_id": "stale-run"}, fake)
        self.assertEqual([name for name, _ in fake.calls], ["get_report"])

    def test_offline_stop_persists_exact_run_and_retries_before_new_work(self):
        state = {"run_id": "old-run", "pending": {"entity": "agent_run", "id": "old-run", "data": {"event": "heartbeat", "session_key": "codex:parent-session"}}}
        offline = FakeMcp(fail=True)
        result = self.apply(self.event("Interrupt"), state, offline)
        self.assertEqual(state["pending"]["data"]["event"], "interrupt")
        self.assertEqual(state["pending"]["data"]["occurred_at"], "1970-01-01T00:16:40Z")
        self.assertNotIn("secret", str(result))
        online = FakeMcp({"id": "new-run"})
        self.apply(self.event("UserPromptSubmit"), state, online, now=2000)
        self.assertEqual(online.calls[0][1]["id"], "old-run")
        self.assertEqual(online.calls[-1][1]["id"], "new-run")
        self.assertNotIn("pending", state)

    def test_structured_protocol_result_can_be_wrapped(self):
        self.assertEqual(hooks.structured({"result": {"content": [], "structuredContent": {"this_session": None}}}), {"this_session": None})

    def test_close_hook_durably_queues_only_identity_before_detaching_worker(self):
        for event in set(hooks.CLOSE_EVENTS) - {"Stop"}:
            with self.subTest(event=event), tempfile.TemporaryDirectory() as home:
                payload = self.event(event, last_assistant_message="private conversation")
                with patch.object(hooks.Path, "home", return_value=Path(home)), \
                     patch.object(hooks.sys, "argv", ["kedeka.py"]), \
                     patch.object(hooks.sys, "stdin", io.StringIO(json.dumps(payload))), \
                     patch.object(hooks.sys, "stdout", new_callable=io.StringIO) as output, \
                     patch.dict(hooks.os.environ, {"KEDEKA_HOOK_BRIDGE": "0"}), \
                     patch.object(hooks.subprocess, "Popen") as spawn:
                    hooks.main()
                    self.assertEqual(json.loads(output.getvalue()), {})
                    spawn.assert_called_once()
                    self.assertTrue(spawn.call_args.kwargs["start_new_session"])
                spool = list((Path(home) / ".local/state/kedeka/hooks").glob("event-*.json"))
                self.assertEqual(len(spool), 1)
                saved = json.loads(spool[0].read_text())
                self.assertEqual(saved["hook_event_name"], event)
                self.assertIn("_kedeka_occurred_at", saved)
                self.assertNotIn("last_assistant_message", saved)
                self.assertEqual(spool[0].stat().st_mode & 0o777, 0o600)

    def test_edit_requires_a_prepared_task_and_current_brief_context(self):
        result = self.apply(self.event("PreToolUse", tool_name="apply_patch"), {}, FakeMcp())
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        result = self.apply(self.event("PreToolUse", tool_name="apply_patch"), {}, FakeMcp({"id": "legacy-run", "context": {}}))
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        state = {}
        fake = FakeMcp({"id": "prepared", "context": {"repo": "github.com/example/coding", "work_protocol": {"version": 1}}})
        self.assertEqual(self.apply(self.event("PreToolUse", tool_name="apply_patch"), state, fake), {})
        self.assertEqual(state["run_id"], "prepared")
        self.assertEqual(self.apply(self.event("PreToolUse", tool_name="apply_patch"), state, FakeMcp(fail=True), now=1001), {})
        expired = self.apply(self.event("PreToolUse", tool_name="apply_patch"), state, FakeMcp(fail=True), now=1031)
        self.assertEqual(expired["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_read_only_discovery_is_available_without_task_or_connection(self):
        for command in ["rtk git status", "rtk proxy rg task app", "git remote get-url origin", "pwd"]:
            fake = FakeMcp(fail=True)
            result = self.apply(self.event("PreToolUse", tool_name="Bash", tool_input={"command": command}), {}, fake)
            self.assertEqual(result, {})
            self.assertEqual(fake.calls, [])
        for command in ["git commit -am change", "cat file > new", "git remote add other foo"]:
            self.assertTrue(hooks.requires_work(self.event("PreToolUse", tool_name="Bash", tool_input={"command": command})))

    def test_stop_requires_explicit_result_after_edits_but_interrupt_only_pauses(self):
        run = {"id": "prepared", "context": {"repo": "github.com/example/coding", "work_protocol": {"version": 1}}}
        state = {"run_id": "prepared", "work_started": True}
        fake = FakeMcp(run)
        result = self.apply(self.event("Stop"), state, fake)
        self.assertEqual(result["decision"], "block")
        self.assertEqual([name for name, _ in fake.calls], ["get_report"])
        result = self.apply(self.event("Interrupt"), state, FakeMcp(run))
        self.assertNotIn("decision", result)
        finished = self.apply(self.event("Stop"), state, FakeMcp())
        self.assertNotIn("decision", finished)

    def test_prepared_task_from_another_repository_cannot_authorize_edits(self):
        run = {"id": "other", "context": {"repo": "github.com/other/repo", "work_protocol": {"version": 1}}}
        result = self.apply(self.event("PreToolUse", tool_name="apply_patch"), {}, FakeMcp(run))
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_stop_executes_synchronously_instead_of_silently_queueing_a_pause(self):
        with tempfile.TemporaryDirectory() as home:
            with patch.object(hooks.Path, "home", return_value=Path(home)), \
                 patch.object(hooks.sys, "argv", ["kedeka.py"]), \
                 patch.object(hooks.sys, "stdin", io.StringIO(json.dumps(self.event("Stop")))), \
                 patch.object(hooks.sys, "stdout", new_callable=io.StringIO) as output, \
                 patch.dict(hooks.os.environ, {"KEDEKA_HOOK_BRIDGE": "0"}), \
                 patch.object(hooks, "process_event", return_value={"decision": "block", "reason": "Finish first"}) as process, \
                 patch.object(hooks.subprocess, "Popen") as spawn:
                hooks.main()
                process.assert_called_once()
                spawn.assert_not_called()
                self.assertEqual(json.loads(output.getvalue())["decision"], "block")


    def test_post_edit_marks_work_before_the_heartbeat_throttle(self):
        state = {"run_id": "run-1", "checked_at": 999}
        self.apply(self.event("PostToolUse", tool_name="apply_patch"), state, FakeMcp())
        self.assertTrue(state["work_started"])


    def test_worker_retries_connection_failures_without_losing_event_time(self):
        with tempfile.TemporaryDirectory() as home:
            spool = Path(home) / "event.json"
            payload = self.event("Interrupt", _kedeka_occurred_at=1000)
            spool.write_text(json.dumps(payload))
            with patch.object(hooks.Path, "home", return_value=Path(home)), \
                 patch.object(hooks.sys, "argv", ["kedeka.py", "--worker", str(spool)]), \
                 patch.object(hooks.sys, "stdout", new_callable=io.StringIO), \
                 patch.dict(hooks.os.environ, {"KEDEKA_HOOK_BRIDGE": "0"}), \
                 patch.object(hooks, "process_event", side_effect=[{"systemMessage": "offline"}, {"systemMessage": "reconnecting"}, {}]) as process, \
                 patch.object(hooks.time, "sleep"):
                hooks.main()
                self.assertEqual(process.call_count, 3)
                self.assertTrue(all(c.kwargs["wait"] for c in process.call_args_list))
                self.assertTrue(all(c.args[0]["_kedeka_occurred_at"] == 1000 for c in process.call_args_list))
                self.assertFalse(spool.exists())


if __name__ == "__main__":
    unittest.main()
