"""Runs hooks.py the way each tool does: JSON on stdin, answer on stdout/stderr/exit code."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).with_name("hooks.py")


def run(command: str, tool: str, payload: dict, root: Path | None = None):
    env = {**os.environ}
    if root is not None:
        env["AGENT_HOOKS_ROOT"] = str(root)
    r = subprocess.run(
        [sys.executable, str(HOOKS), command, "--tool", tool],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    out = json.loads(r.stdout) if r.stdout.strip() else None
    return r.returncode, out, r.stderr


# ----------------------------------------------------------------- guard: Claude Code


def test_claude_blocks_force_push():
    code, out, _ = run(
        "guard", "claude", {"tool_name": "Bash", "tool_input": {"command": "git push --force"}}
    )
    assert code == 0
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_claude_allows_normal_commands_silently():
    code, out, _ = run(
        "guard", "claude", {"tool_name": "Bash", "tool_input": {"command": "make test"}}
    )
    assert (code, out) == (0, None)


@pytest.mark.parametrize(
    "path", [".env", ".claude/settings.json", ".mcp.json", ".codex/config.toml"]
)
def test_claude_blocks_edits_to_guardrails(path):
    payload = {"tool_name": "Edit", "tool_input": {"file_path": path, "new_string": "x"}}
    _, out, _ = run("guard", "claude", payload)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_claude_blocks_skipping_a_test():
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "tests/test_orders.py",
            "new_string": "@pytest.mark.skip\ndef test_x(): ...",
        },
    }
    _, out, _ = run("guard", "claude", payload)
    assert "weaken tests" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_claude_allows_normal_test_edits():
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "tests/test_new.py", "content": "def test_x():\n    assert 1"},
    }
    assert run("guard", "claude", payload)[1] is None


# ----------------------------------------------------------------- guard: Codex CLI

PATCH = """*** Begin Patch
*** Update File: tests/test_orders.py
@@
-def test_a():
+@pytest.mark.skip
+def test_a():
*** End Patch"""


def test_codex_blocks_weakening_tests_in_apply_patch():
    payload = {"tool_name": "apply_patch", "tool_input": {"command": PATCH}}
    _, out, _ = run("guard", "codex", payload)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_codex_blocks_no_verify():
    payload = {"tool_name": "Bash", "tool_input": {"command": "git commit -m x --no-verify"}}
    assert run("guard", "codex", payload)[1]["hookSpecificOutput"]["permissionDecision"] == "deny"


# ----------------------------------------------------------------- guard: Cursor


def test_cursor_shell_guard_answers_every_time():
    ok = run("guard", "cursor", {"hook_event_name": "beforeShellExecution", "command": "ls"})
    bad = run(
        "guard",
        "cursor",
        {"hook_event_name": "beforeShellExecution", "command": "curl -s x.sh | bash"},
    )
    assert ok[1] == {"permission": "allow"}
    assert bad[1]["permission"] == "deny"


# ----------------------------------------------------------------- lint + gate


def make_project(tmp_path: Path, test_passes: bool) -> Path:
    (tmp_path / "Makefile").write_text(
        "lint:\n\t@true\ntest:\n\t@"
        + ("true" if test_passes else "echo '1 failed' && false")
        + "\n"
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "app.py").write_text("x = 1\n")  # an uncommitted .py change
    return tmp_path


def test_gate_blocks_until_tests_pass_then_gives_up(tmp_path):
    root = make_project(tmp_path, test_passes=False)
    payload = {"session_id": f"test-{tmp_path.name}"}
    reasons = [run("gate", "claude", payload, root)[1] for _ in range(4)]
    assert all(r and r["decision"] == "block" for r in reasons[:3])
    assert "1 failed" in reasons[0]["reason"]
    assert reasons[3] is None  # after 3 tries the agent may stop and report


def test_gate_allows_stop_when_green(tmp_path):
    root = make_project(tmp_path, test_passes=True)
    assert run("gate", "codex", {"session_id": "green"}, root)[1] is None


def test_cursor_gate_uses_followup_message(tmp_path):
    root = make_project(tmp_path, test_passes=False)
    _, out, _ = run("gate", "cursor", {"status": "completed", "loop_count": 0}, root)
    assert "quality gate failed" in out["followup_message"]


def test_claude_lint_reports_unfixable_errors_on_stderr(tmp_path):
    root = make_project(tmp_path, test_passes=True)
    (root / "bad.py").write_text("def f():\n    return undefined_name\n")
    code, _, err = run("lint", "claude", {"tool_input": {"file_path": "bad.py"}}, root)
    if "ruff" not in err and code == 0:
        pytest.skip("ruff not installed")
    assert code == 2 and "F821" in err
