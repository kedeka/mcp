#!/usr/bin/env python3
"""Kedeka lifecycle bridge. Uses Codex's MCP OAuth client, never reads tokens."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit


EVENTS = {"PreToolUse", "SessionStart", "UserPromptSubmit", "PostToolUse", "SubagentStart",
          "SubagentStop", "Stop", "Interrupt", "SessionEnd"}
CLOSE_EVENTS = {"Stop": "pause", "SubagentStop": "pause",
                "Interrupt": "interrupt", "SessionEnd": "session_end"}
ENDPOINT = "https://kedeka.com/mcp/kedeka"
TRACKING_SCOPE = (
    "Tracking applies to authorized implementation work. Read-only investigation, discussion and review "
    "do not require a prepared task. This hook only manages task tracking. Execution permissions and "
    "workflow selection belong to the user and host, independently of tracking. "
    "No skill-specific registration is required by Kedeka."
)


class ToolError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__("Kedeka tool failed")


def session_key(payload):
    identity = payload.get("agent_id") or payload.get("session_id")
    if not isinstance(identity, str) or not identity:
        raise ValueError("Missing harness session identity")
    prefix = "codex:"
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", identity):
        identity = hashlib.sha256(identity.encode()).hexdigest()
    return prefix + identity


def structured(value):
    if isinstance(value, dict):
        if isinstance(value.get("structuredContent"), dict):
            return value["structuredContent"]
        for child in value.values():
            found = structured(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = structured(child)
            if found is not None:
                return found
    return None


class McpClient:
    """An ephemeral protocol client; no model turn or child agent is launched."""

    def __init__(self, cwd):
        native = Path.home() / ".codex/packages/standalone/current/bin/codex"
        binary = str(native) if native.is_file() else shutil.which("codex")
        if not binary:
            raise RuntimeError("Codex CLI unavailable")
        config = ('mcp_servers={kedeka={url="' + ENDPOINT + '",'
                  'scopes=["read","write"],startup_timeout_sec=20,tool_timeout_sec=30}}')
        self.process = subprocess.Popen(
            [binary, "app-server", "--stdio", "-c", config], cwd=cwd,
            env={**os.environ, "KEDEKA_HOOK_BRIDGE": "1"},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
        )
        self.messages = queue.Queue()
        self.sequence = 0
        self.deadline = time.monotonic() + 35
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.rpc("initialize", {"clientInfo": {"name": "kedeka_lifecycle",
                     "title": "Kedeka lifecycle bridge", "version": "1"},
                     "capabilities": {"experimentalApi": True}})
            self._send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
            self.thread = self.rpc("thread/start", {"cwd": cwd, "ephemeral": True,
                                   "approvalPolicy": "never", "sandbox": "read-only"})["thread"]["id"]
            self.rpc("mcpServerStatus/list", {"threadId": self.thread, "serverName": "kedeka"})
        except Exception:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                self.messages.put(json.loads(line))
        finally:
            self.messages.put(None)

    def _send(self, value):
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def rpc(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = self.deadline
        while True:
            message = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
            if message is None:
                raise RuntimeError("MCP bridge closed")
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError("MCP protocol request failed")
                return message["result"]
            if time.monotonic() >= deadline:
                raise TimeoutError("MCP bridge timed out")

    def call(self, tool, arguments):
        result = structured(self.rpc("mcpServer/tool/call", {
            "threadId": self.thread, "server": "kedeka", "tool": tool, "arguments": arguments,
        }))
        if result is not None and "error" in result:
            raise ToolError(result["error"].get("code"))
        if result is None:
            raise RuntimeError("Kedeka tool failed")
        return result

    def close(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
        self.process.stdin.close()
        self.process.stdout.close()


def git_context(cwd):
    remote = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"], capture_output=True, text=True, timeout=3, check=True).stdout.strip()
    if re.match(r"^[^/@:]+@[^/:]+:", remote):
        remote = "https://" + remote.split("@", 1)[1].replace(":", "/", 1)
    parsed = urlsplit(remote if "://" in remote else "https://" + remote)
    repo = ((parsed.hostname or "") + parsed.path).rstrip("/").removesuffix(".git").lower()
    branch = subprocess.run(["git", "-C", cwd, "branch", "--show-current"], capture_output=True, text=True, timeout=3, check=True).stdout.strip()
    return {"repo": repo, "branch": branch or "HEAD"}


READ = "read"
EXTERNAL = "external"
UNKNOWN = "unknown"
PROJECT = "project"
TRACKING_REMINDER = (
    "Perintah belum dapat diklasifikasikan oleh hook tracking; tidak diblokir. "
    "Jika ini implementasi proyek, siapkan task/brief melalui projects/tracking/prepare. "
    "Izin eksekusi tetap mengikuti pengguna dan host."
)


def shell_tokens(command):
    """Tokenize words and operators without executing shell code or losing quotes."""
    tokens, word = [], []
    quote, started, index = None, False, 0
    dynamic = False
    while index < len(command):
        char = command[index]
        if char in {"$", "`"} and quote != "'":
            dynamic = True
        if char == "\\" and quote != "'":
            if index + 1 >= len(command):
                raise ValueError("Incomplete escape")
            index += 1
            if command[index] != "\n":
                word.append(command[index])
                started = True
        elif quote:
            if char == quote:
                quote = None
            else:
                word.append(char)
        elif char in {"'", '"'}:
            quote, started = char, True
        elif char == "#" and not started:
            while index < len(command) and command[index] != "\n":
                index += 1
            continue
        elif char.isspace() or char in ";&|<>":
            if started:
                tokens.append(("".join(word), False))
                word, started = [], False
            if char in ";&|<>" or char == "\n":
                operator = char
                while index + 1 < len(command) and command[index + 1] in "&|<>":
                    index += 1
                    operator += command[index]
                tokens.append((operator, True))
        else:
            word.append(char)
            started = True
        index += 1
    if quote:
        raise ValueError("Incomplete quote")
    if started:
        tokens.append(("".join(word), False))
    return ([("__dynamic__", True)] if dynamic else []) + tokens


def project_root(cwd):
    path = Path(cwd).resolve()
    return next((parent for parent in [path, *path.parents] if (parent / ".git").exists()), path)


def destination_kind(value, cwd, root):
    if not value or any(char in value for char in "$`*?{}()"):
        return UNKNOWN
    if value in {"-", "/dev/null", "/dev/stdout", "/dev/stderr"}:
        return READ
    path = Path(value).expanduser()
    path = (path if path.is_absolute() else cwd / path).resolve()
    return PROJECT if path.is_relative_to(root) else EXTERNAL


def combine(kinds):
    return next((kind for kind in [PROJECT, UNKNOWN, EXTERNAL] if kind in kinds), READ)


def command_kind(parts, cwd, root):
    if not parts:
        return READ
    if parts[0] == "rtk":
        parts = parts[1:]
        while parts and parts[0] in {"-u", "--ultra-compact", "-v", "-vv", "-vvv"}:
            parts = parts[1:]
        if parts in [["--version"], ["-V"], ["--help"], ["-h"]]:
            return READ
        if parts[:1] in [["proxy"], ["err"]]:
            parts = parts[1:]
    if not parts:
        return READ
    name, args = Path(parts[0]).name, parts[1:]
    if name == "git":
        if args[:1] == ["-C"] and len(args) > 2:
            target = Path(args[1])
            cwd = (target if target.is_absolute() else cwd / target).resolve()
            args = args[2:]
        if not args:
            return READ
        action, options = args[0], args[1:]
        if action == "branch":
            mutates = bool(options) and options not in [["--show-current"], ["--list"], ["-a"], ["-r"], ["-v"], ["-vv"]]
            if options[:1] == ["--list"]:
                mutates = False
        elif action == "tag" and (not options or options[0] in {"-l", "--list"}):
            return READ
        elif action == "stash" and options[:1] in [["list"], ["show"]]:
            return READ
        elif action == "remote":
            mutates = bool(options) and options[0] not in {"get-url", "-v", "--verbose", "show"}
        elif action in {"status", "diff", "log", "show", "ls-files", "rev-parse", "ls-remote"}:
            return READ
        elif action in {"add", "commit", "push", "pull", "fetch", "merge", "rebase", "reset", "restore", "checkout", "switch", "clean", "rm", "mv", "cherry-pick", "revert", "stash", "tag", "apply"}:
            mutates = True
        else:
            return UNKNOWN
        return destination_kind(str(cwd), cwd, root) if mutates else READ
    if name in {"touch", "mkdir", "rm", "rmdir", "truncate", "tee"}:
        return combine([destination_kind(arg, cwd, root) for arg in args if not arg.startswith("-")])
    if name in {"cp", "mv", "install", "ln"}:
        paths = [arg for arg in args if not arg.startswith("-")]
        if not paths:
            return UNKNOWN
        targets = paths if name == "mv" else paths[-1:]
        return combine([destination_kind(arg, cwd, root) for arg in targets])
    if name == "sed":
        if any(arg == "--in-place" or arg.startswith("--in-place=") or arg.startswith("-i") for arg in args):
            return destination_kind(args[-1], cwd, root) if args else UNKNOWN
        return READ if (len(args) >= 3 and args[0] == "-n"
                        and re.fullmatch(r"\d+(?:,\d+|,\$)?p", args[1])
                        and all(not arg.startswith("-") for arg in args[2:])) else UNKNOWN
    if name in {"rsvg-convert", "sips"}:
        for index, arg in enumerate(args):
            if arg in {"-o", "--output", "--out"} and index + 1 < len(args):
                return destination_kind(args[index + 1], cwd, root)
            if arg.startswith(("--output=", "--out=")):
                return destination_kind(arg.split("=", 1)[1], cwd, root)
        return READ if name == "rsvg-convert" or "-g" in args or "--getProperty" in args else UNKNOWN
    if name in {"magick", "convert"} and args:
        return destination_kind(args[-1], cwd, root)
    if name == "sort" and "-o" in args:
        index = args.index("-o")
        return destination_kind(args[index + 1], cwd, root) if index + 1 < len(args) else UNKNOWN
    if name in {"rg", "grep", "find"} and any(arg in {"--pre", "-exec", "-execdir", "-delete"} or arg.startswith("--pre=") for arg in args):
        return UNKNOWN
    if name in {"npm", "pnpm", "bun", "composer"} and args and args[0] in {"install", "add", "remove", "update", "require", "build"}:
        return destination_kind(str(cwd), cwd, root)
    if name in {"ls", "pwd", "cat", "rg", "grep", "head", "tail", "read", "which", "whoami", "nl", "stat", "file", "wc", "sort", "uniq", "cut", "du", "df", "find", "echo", "printf", "true", "false"}:
        return READ
    return UNKNOWN


def classify_work(payload):
    name = payload.get("tool_name", "")
    args = payload.get("tool_input") or {}
    cwd = Path(payload.get("cwd") or os.getcwd()).resolve()
    root = project_root(cwd)
    if isinstance(args, dict):
        workdir = Path(args.get("workdir") or args.get("cwd") or cwd)
        cwd = (workdir if workdir.is_absolute() else cwd / workdir).resolve()
    if name in {"Edit", "Write", "NotebookEdit"}:
        path = args.get("file_path") or args.get("notebook_path")
        return destination_kind(path, cwd, root) if path else PROJECT
    if name == "apply_patch":
        patch = args if isinstance(args, str) else args.get("patch", args.get("input", ""))
        paths = re.findall(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", patch, re.MULTILINE)
        return combine([destination_kind(path, cwd, root) for path in paths]) if paths else PROJECT
    if name not in {"Bash", "exec_command"}:
        return READ
    command = args.get("command", args.get("cmd", ""))
    if not isinstance(command, str):
        return UNKNOWN
    try:
        tokens = shell_tokens(command)
    except ValueError:
        return UNKNOWN
    kinds, parts, index = [], [], 0
    while index < len(tokens):
        value, operator = tokens[index]
        if operator and value == "__dynamic__":
            kinds.append(UNKNOWN)
        elif operator and value in {";", "&&", "||", "|", "&", "\n"}:
            if parts[:1] == ["cd"] and len(parts) == 2 and not any(c in parts[1] for c in "$`"):
                target = Path(parts[1]).expanduser()
                if value in {";", "&&", "\n"}:
                    cwd = (target if target.is_absolute() else cwd / target).resolve()
            else:
                kinds.append(command_kind(parts, cwd, root))
            parts = []
        elif operator:
            if parts and parts[-1].isdigit():
                parts.pop()
            if index + 1 >= len(tokens) or tokens[index + 1][1]:
                kinds.append(UNKNOWN)
            else:
                index += 1
                target = tokens[index][0]
                if value in {">", ">>", ">|", "&>", "&>>", "<>"} or (value == ">&" and not target.isdigit() and target != "-"):
                    kinds.append(destination_kind(target, cwd, root))
                elif value not in {"<", ">&", "<&"}:
                    kinds.append(UNKNOWN)
        else:
            parts.append(value)
        index += 1
    kinds.append(command_kind(parts, cwd, root))
    return combine(kinds)


def requires_work(payload):
    return classify_work(payload) == PROJECT


def tracking_notice(payload):
    return {"systemMessage": TRACKING_REMINDER} if classify_work(payload) == UNKNOWN else {}


def deny_work(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "deny", "permissionDecisionReason": reason}}


def lifecycle(payload, state, client_factory=McpClient, clock=time.time):
    event = payload["hook_event_name"]
    key = session_key(payload)
    now = clock()
    occurred_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(payload.get("_kedeka_occurred_at", now)))
    output = {}
    if event == "PreToolUse":
        if not requires_work(payload):
            return tracking_notice(payload)
        client = None
        try:
            repository = git_context(payload["cwd"])
            if state.get("run_id") and state.get("work_protocol") and repository == state.get("guard_repository") and now < state.get("guard_ready_until", 0):
                return output
            client = client_factory(payload["cwd"])
            current = client.call("get_report", {"report": "current_work", "params": {"session_key": key}})
            run = current.get("this_session")
            protocol = (run.get("context") or {}).get("work_protocol") if run else None
            context = (run.get("context") or {}) if run else {}
            if not protocol or context.get("repo") != repository["repo"] or (context.get("branch") and context["branch"] != repository["branch"]):
                return deny_work("Sebelum mengubah proyek, baca brief relevan lalu siapkan task melalui create_record agent_run: task_id atau task_title/task_description, repo, session_key, briefs_read [{id, revision}]. Jika tidak ada task yang cocok, buat otomatis tanpa meminta konfirmasi lagi. Lihat get_help projects/tracking/prepare.")
            state.update(run_id=run["id"], work_protocol=protocol, guard_ready_until=now + 30, guard_repository=repository)
            return output
        except Exception:
            return deny_work("Task dan brief belum dapat diverifikasi. Pulihkan koneksi Kedeka sebelum mengubah proyek; pemeriksaan baca saja tetap tersedia.")
        finally:
            if client:
                client.close()
    if event == "PostToolUse" and requires_work(payload) and state.get("run_id"):
        state["work_started"] = True
    context_events = {"SessionStart", "UserPromptSubmit", "SubagentStart"}
    if event in context_events:
        context = (f"Kedeka session_key={key}. Before coding, read get_report current_work with repo and branch, "
                   "find the repository project and read relevant briefs. Search for a matching task; if none exists, "
                   "automatically create it as authorized by the coding request. Use create_record agent_run with "
                   "task_id or task_title/task_description, repo, this session_key, and briefs_read [{id, revision}]. "
                   "Use lifecycle_hooks=true only when this bridge is active. See get_help projects/tracking/prepare. "
                   "Finish explicitly with summary, verification, commits/PR and task_status=done after acceptance criteria pass; "
                   "use review when external review remains, or keep for a pause. Update affected briefs with current revisions. "
                   "Hooks never infer completion from Stop or Interrupt. Parent registers each authorized child with its own "
                   "codex:<agent_id>; do not duplicate runs or choose unrelated suggestions. " + TRACKING_SCOPE)
        output["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": context}

    tool_input = payload.get("tool_input") or {}
    tracking_call = isinstance(tool_input, dict) and tool_input.get("entity") == "agent_run"
    if event == "PostToolUse" and not tracking_call and now - state.get("checked_at", 0) < 300:
        return output

    client = None
    try:
        client = client_factory(payload["cwd"])
        if state.get("pending"):
            try:
                if state["pending"]["data"]["event"] != "heartbeat":
                    client.call("update_record", state["pending"])
            except ToolError as error:
                if error.code != "ENTITY_NOT_FOUND":
                    raise
            state.pop("pending")
        current = client.call("get_report", {"report": "current_work", "params": {"session_key": key}})
        run = current.get("this_session")
        state["checked_at"] = now
        state["run_id"] = run["id"] if run else None
        state["work_protocol"] = (run.get("context") or {}).get("work_protocol") if run else None
        if not run:
            state["work_started"] = False
            state.pop("guard_ready_until", None)
        if event == "Stop" and run and state.get("work_protocol"):
            return {"decision": "block", "reason": "Pekerjaan masih punya run aktif. Simpan hasil melalui update_record agent_run dengan summary, verification dan task_status=done setelah terverifikasi; review jika menunggu pemeriksaan, atau event=pause untuk pekerjaan yang belum selesai. Perbarui brief yang berubah sebelum menutup pekerjaan."}
        if run:
            arguments = {"entity": "agent_run", "id": run["id"], "data": {
                "event": CLOSE_EVENTS.get(event, "heartbeat"), "session_key": key,
            }}
            if event in CLOSE_EVENTS:
                arguments["data"]["occurred_at"] = occurred_at
                state["pending"] = arguments
            result = client.call("update_record", arguments)
            state.pop("pending", None)
            if event in CLOSE_EVENTS and not result.get("run", {}).get("is_active"):
                state["run_id"] = None
    except Exception:
        if event in CLOSE_EVENTS and state.get("run_id") and state.get("pending", {}).get("data", {}).get("event") not in CLOSE_EVENTS.values():
            state["pending"] = {"entity": "agent_run", "id": state["run_id"], "data": {
                "event": CLOSE_EVENTS[event], "session_key": key,
                "occurred_at": occurred_at,
            }}
        output["systemMessage"] = ("Kedeka tracking belum tersinkron. Callback disimpan bila ID run "
                                   "diketahui dan akan dicoba ulang; idle lease tetap melindungi timer. "
                                   "Periksa koneksi dengan codex mcp login kedeka dan get_report current_work.")
    finally:
        if client:
            client.close()
    return output


def process_event(payload, directory, wait=False):
    key = session_key(payload)
    identity = hashlib.sha256((ENDPOINT + key).encode()).hexdigest()
    state_path = directory / (identity + ".json")
    with (directory / (identity + ".lock")).open("a+", encoding="utf-8") as handle:
        os.chmod(handle.name, 0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            return {"systemMessage": "Kedeka sedang menyinkronkan sesi ini; callback antrean akan dicoba ulang."}
        raw = state_path.read_text() if state_path.exists() else ""
        state = json.loads(raw) if raw else {}
        result = lifecycle(payload, state)
        with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as saved:
            json.dump(state, saved)
            saved.flush()
            os.fsync(saved.fileno())
        os.replace(saved.name, state_path)
        return result


def main():
    if os.environ.get("KEDEKA_HOOK_BRIDGE") == "1":
        print("{}")
        return
    directory = Path.home() / ".local/state/kedeka/hooks"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    worker = len(sys.argv) == 3 and sys.argv[1] == "--worker"
    spool = Path(sys.argv[2]) if worker else None
    payload = json.loads(spool.read_text()) if worker else json.load(sys.stdin)
    globals()["_event_payload"] = payload
    if payload.get("hook_event_name") not in EVENTS:
        print("{}")
        return
    session_key(payload)
    if not worker:
        for pending in sorted(directory.glob("event-*.json"))[:3]:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", str(pending)],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True, close_fds=True)
    if not worker and payload["hook_event_name"] in CLOSE_EVENTS and payload["hook_event_name"] != "Stop":
        queued = {k: payload[k] for k in ("session_id", "agent_id", "cwd", "hook_event_name") if k in payload}
        queued["_kedeka_occurred_at"] = time.time()
        with tempfile.NamedTemporaryFile(mode="w", prefix="event-", suffix=".json", dir=directory, delete=False) as saved:
            json.dump(queued, saved)
            saved.flush()
            os.fsync(saved.fileno())
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", saved.name],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, close_fds=True)
        print("{}")
        return
    for attempt in range(3 if worker else 1):
        result = process_event(payload, directory, wait=worker)
        if "systemMessage" not in result:
            break
        if worker and attempt < 2:
            time.sleep(attempt + 1)
    if spool is not None and "systemMessage" not in result:
        spool.unlink(missing_ok=True)
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if globals().get("_event_payload", {}).get("hook_event_name") == "PreToolUse" and requires_work(globals()["_event_payload"]):
            print(json.dumps(deny_work("Pemeriksaan task/brief gagal. Pulihkan hook dan koneksi sebelum mengubah proyek.")))
            sys.exit(0)
        print(json.dumps({"systemMessage": "Kedeka hook gagal dijalankan; periksa konfigurasi hook dan koneksi MCP."}))
