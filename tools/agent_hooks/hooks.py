#!/usr/bin/env python3
"""One policy, three adapters: the hook entry point for Claude Code, Codex CLI and Cursor.

Each tool's hook config calls this script with a command and the tool's name:

    python3 tools/agent_hooks/hooks.py guard --tool claude    # before a shell command or edit
    python3 tools/agent_hooks/hooks.py lint  --tool codex     # after an edit
    python3 tools/agent_hooks/hooks.py gate  --tool cursor    # when the agent wants to stop

The tool sends a JSON payload on stdin; the script answers in that tool's format.
The POLICY section is the same for all three tools. Only the adapters differ.
Standard library only, so it runs with any python3 >= 3.10.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(os.environ.get("AGENT_HOOKS_ROOT", Path(__file__).resolve().parents[2]))

# --------------------------------------------------------------------------- POLICY

# Files the agent must never edit: secrets, and the guardrails themselves.
PROTECTED_PATHS = [
    ".env",
    ".env.*",
    ".git/*",
    ".claude/*",
    ".codex/*",
    ".cursor/*",
    ".mcp.json",
    "tools/agent_hooks/*",
]

# Shell commands that are never OK in an agent session, with the reason the agent sees.
BLOCKED_COMMANDS = [
    (r"\bgit\s+push\b.*\s(--force\b|--force-with-lease\b|-f\b)", "Force-push is not allowed."),
    (r"\bgit\b.*\s--no-verify\b", "Skipping git hooks with --no-verify is not allowed."),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard throws work away. Ask the human to do it."),
    (r"\brm\s+-\S*[rR]\S*\s+(/|~|\$HOME)(\s|$)", "Recursive delete outside the project."),
    (r"\b(curl|wget)\b[^|]*\|\s*(ba|z)?sh\b", "Piping a download into a shell is not allowed."),
]

# Edits to tests/ that make a failing test "pass" without fixing the code.
TEST_WEAKENING = [
    r"pytest\.mark\.skip",
    r"pytest\.skip\(",
    r"pytest\.mark\.xfail",
    r"assert\s+True\b",
]

# The stop gate gives the agent this many tries to get lint + tests green.
MAX_GATE_ATTEMPTS = 3


@dataclass
class Decision:
    block: bool
    reason: str = ""


ALLOW = Decision(False)


def check_command(command: str) -> Decision:
    for pattern, reason in BLOCKED_COMMANDS:
        if re.search(pattern, command):
            return Decision(True, f"Blocked by project policy: {reason}")
    return ALLOW


def _relative(path: str) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(ROOT.resolve())
        except ValueError:
            return str(p)
    return p.as_posix().removeprefix("./")


def check_edit(path: str, new_text: str = "") -> Decision:
    rel = _relative(path)
    for pattern in PROTECTED_PATHS:
        if fnmatch.fnmatch(rel, pattern):
            return Decision(
                True,
                f"Blocked by project policy: {rel} holds secrets or guardrails. "
                "A human edits it by hand.",
            )
    if rel.startswith("tests/") and any(re.search(p, new_text) for p in TEST_WEAKENING):
        return Decision(
            True,
            "Blocked by project policy: don't skip or weaken tests to make them pass. "
            "Fix the code, or stop and report what is failing.",
        )
    return ALLOW


# --------------------------------------------------------------------------- HELPERS


def parse_patch(patch: str) -> list[tuple[str, str]]:
    """Codex apply_patch text -> [(path, added_text)]."""
    files: list[tuple[str, list[str]]] = []
    for line in patch.splitlines():
        m = re.match(r"\*\*\* (?:Add|Update|Delete) File: (.+)", line) or re.match(
            r"\*\*\* Move to: (.+)", line
        )
        if m:
            files.append((m.group(1).strip(), []))
        elif files and line.startswith("+"):
            files[-1][1].append(line[1:])
    return [(path, "\n".join(added)) for path, added in files]


def _as_text(value) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value or "")


def _ruff() -> list[str] | None:
    venv = ROOT / ".venv" / "bin" / "ruff"
    if venv.exists():
        return [str(venv)]
    found = shutil.which("ruff")
    return [found] if found else None


def lint_files(paths: list[str]) -> str:
    """Auto-fix and format Python files; return the lint errors that remain."""
    ruff = _ruff()
    targets = [str(ROOT / _relative(p)) for p in paths if p.endswith(".py")]
    targets = [t for t in targets if Path(t).exists()]
    if not ruff or not targets:
        return ""
    subprocess.run([*ruff, "check", "--fix", "--quiet", *targets], cwd=ROOT, capture_output=True)
    subprocess.run([*ruff, "format", "--quiet", *targets], cwd=ROOT, capture_output=True)
    result = subprocess.run(
        [*ruff, "check", "--output-format", "concise", *targets],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return "" if result.returncode == 0 else result.stdout.strip()


def python_changed() -> bool:
    out = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True
    ).stdout
    return any(line.rstrip().endswith(".py") for line in out.splitlines())


def run_gate() -> tuple[bool, str]:
    """Run make lint and make test. Returns (passed, tail of output)."""
    log = []
    for target in ("lint", "test"):
        r = subprocess.run(["make", "-s", target], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            log.append(f"$ make {target}\n{(r.stdout + r.stderr).strip()}")
    tail = "\n".join("\n\n".join(log).splitlines()[-40:])
    return (not log), tail


def _attempts_file(session: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session)[:80] or "default"
    return Path(tempfile.gettempdir()) / f"orders-api-gate-{safe}.count"


# --------------------------------------------------------------------------- ADAPTERS


def edits_from_payload(tool: str, payload: dict) -> tuple[list[str], list[tuple[str, str]]]:
    """Return (shell commands, [(path, new text)]) found in a pre-tool payload."""
    name = payload.get("tool_name", "")
    tin = payload.get("tool_input") or {}
    commands: list[str] = []
    edits: list[tuple[str, str]] = []

    if tool == "cursor" and payload.get("hook_event_name") == "beforeShellExecution":
        commands.append(_as_text(payload.get("command")))
    elif tool == "codex" and name == "apply_patch":
        edits.extend(parse_patch(_as_text(tin.get("command") or tin.get("patch"))))
    elif name in ("Bash", "Shell", "shell", "exec_command"):
        commands.append(_as_text(tin.get("command")))
    else:
        path = tin.get("file_path") or tin.get("notebook_path") or tin.get("path")
        if path:
            text = "\n".join(
                _as_text(tin.get(k))
                for k in ("new_string", "content", "contents", "new_source")
                if tin.get(k)
            )
            edits.append((path, text))
    return commands, edits


def guard(tool: str, payload: dict) -> int:
    commands, edits = edits_from_payload(tool, payload)
    decision = ALLOW
    for command in commands:
        decision = check_command(command)
        if decision.block:
            break
    if not decision.block:
        for path, text in edits:
            decision = check_edit(path, text)
            if decision.block:
                break

    if tool == "cursor":
        out = {"permission": "deny" if decision.block else "allow"}
        if decision.block:
            out |= {"user_message": decision.reason, "agent_message": decision.reason}
        print(json.dumps(out))
    elif decision.block:  # Claude Code and Codex share this format
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": decision.reason,
                    }
                }
            )
        )
    return 0


def lint(tool: str, payload: dict) -> int:
    if tool == "codex":
        tin = payload.get("tool_input") or {}
        paths = [p for p, _ in parse_patch(_as_text(tin.get("command") or tin.get("patch")))]
    elif tool == "cursor":
        paths = [payload.get("file_path", "")]
    else:
        paths = [(payload.get("tool_input") or {}).get("file_path", "")]

    errors = lint_files([p for p in paths if p])
    if not errors:
        return 0
    message = f"ruff found problems it could not fix automatically:\n{errors}"
    if tool == "claude":
        print(message, file=sys.stderr)  # exit 2: Claude sees stderr; the edit already happened
        return 2
    if tool == "codex":
        print(json.dumps({"decision": "block", "reason": message}))
    # Cursor's afterFileEdit has no output channel; the stop gate reports remaining errors.
    return 0


def gate(tool: str, payload: dict) -> int:
    if tool == "cursor" and payload.get("status") not in (None, "completed"):
        return 0  # the user aborted, or the run errored: don't loop
    if not python_changed():
        return 0
    session = str(payload.get("session_id") or payload.get("conversation_id") or "default")
    counter = _attempts_file(session)
    passed, output = run_gate()
    if passed:
        counter.unlink(missing_ok=True)
        return 0

    attempts = int(payload.get("loop_count", 0)) if tool == "cursor" else 0
    if tool != "cursor":
        attempts = int(counter.read_text()) if counter.exists() else 0
        counter.write_text(str(attempts + 1))
    if attempts >= MAX_GATE_ATTEMPTS:
        counter.unlink(missing_ok=True)
        return 0  # give up: let the agent stop and report to the human

    reason = (
        "The quality gate failed (make lint, make test). Fix the problems below, then finish. "
        "Do not skip or weaken tests. If you cannot fix it, stop and explain what is failing.\n\n"
        + output
    )
    if tool == "cursor":
        print(json.dumps({"followup_message": reason}))
    else:
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["guard", "lint", "gate"])
    parser.add_argument("--tool", choices=["claude", "codex", "cursor"], required=True)
    args = parser.parse_args()
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    handler = {"guard": guard, "lint": lint, "gate": gate}[args.command]
    try:
        return handler(args.tool, payload)
    except Exception as exc:  # a broken hook must never wedge the agent
        print(f"agent hook error ({args.command}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
