# orders-api: starter kit for Agentic AI Coding (L3 + L4)

A small FastAPI service with a full agent setup for **Claude Code, Codex CLI and Cursor**: context files, hooks, subagents, skills, a read-only MCP server and one permission policy written for all three tools.

It is the running example for Lecture 3 (specs, context, iteration, skills, CLI) and Lecture 4 (customizing your agentic setup).

## Quick start

```bash
make setup            # .venv + dependencies (Python 3.11+)
make test lint        # 6 tests, lint clean
make seed             # orders.db with sample orders for the MCP server
make check-kit        # tests for the hook scripts and the MCP server themselves
git init && git add -A && git commit -m "start"   # the hooks and the demos rely on git
```

Needs `make`, `git`, Python 3.11+. The MCP Inspector (`make mcp-inspect`) needs Node 22+.

## What's where

| Path | What it is | Used by |
|---|---|---|
| `AGENTS.md` | Project instructions: commands, conventions, boundaries | Codex, Cursor, Claude Code (via `CLAUDE.md`) |
| `CLAUDE.md` | `@AGENTS.md` plus Claude-specific workflow | Claude Code |
| `.cursor/rules/tests.mdc` | Rule scoped to `tests/**` | Cursor |
| `.claude/settings.json` | Permissions (allow / ask / deny) and hooks | Claude Code |
| `.codex/config.toml`, `.codex/rules/policy.rules`, `.codex/hooks.json` | Permission profile, command rules, hooks, MCP server | Codex CLI |
| `.cursor/cli.json`, `.cursor/hooks.json`, `.cursor/mcp.json` | Permissions, hooks, MCP server | Cursor (CLI) |
| `tools/agent_hooks/hooks.py` | **One policy, three adapters**: `guard`, `lint`, `gate` | all three tools' hooks |
| `.claude/agents/*.md`, `.codex/agents/*.toml` | planner → implementer → reviewer subagents | Claude Code, Codex (Cursor reads `.claude/agents`) |
| `.agents/skills/` (linked as `.claude/skills`) | `add-endpoint`, `bump-dependency` skills | all three tools |
| `mcp_server/orders_mcp.py` | Read-only MCP server: `get_order`, `recent_orders`, `order_stats` | `.mcp.json`, Codex, Cursor |
| `specs/` | Six-part specs: rate limiting (L3), idempotency (L4) | demos |
| `docs/permission-policy.md` | The policy matrix behind all the configs | humans |

## The hooks

| Hook | Claude Code | Codex CLI | Cursor |
|---|---|---|---|
| **guard**: block force-push, `reset --hard`, `--no-verify`, `curl \| sh`; block edits to secrets and guardrail files; block skipping tests | PreToolUse `Bash\|Edit\|Write\|NotebookEdit` | PreToolUse `Bash`, `apply_patch` | beforeShellExecution, preToolUse `Write` |
| **lint**: ruff fix + format on each edited file; report what's left | PostToolUse `Edit\|Write` (exit 2 → Claude sees it) | PostToolUse `apply_patch` | afterFileEdit (format only: no output channel) |
| **gate**: `make lint` + `make test` must pass before the agent may stop; gives up after 3 tries | Stop | Stop | stop (`followup_message`, `loop_limit: 3`) |

Run `make check-kit` after changing the policy in `hooks.py`.

## First run in each tool

- **Claude Code**: start `claude` in the repo and accept the workspace trust dialog (project `allow` rules and hooks apply only after that), then approve the `orders` MCP server. `/context`, `/mcp`, `/agents` show what loaded.
- **Codex CLI**: trust the project when asked (project config, hooks and rules load only for trusted projects), then review the hooks with `/hooks`. Check with `codex mcp list` and `codex execpolicy check --pretty --rules .codex/rules/policy.rules -- git push --force`.
- **Cursor**: open the folder. The Cursor CLI reads `.cursor/cli.json`; the IDE uses its own run modes and `.cursor/permissions.json` (not included). Hook support in the CLI is partial: check your version.

Start every agent from the repo root: the MCP configs use paths relative to it.

## Demos

**Lecture 3**
1. *Vague prompt → spec → plan*: plan mode with "Add rate limiting to the API", then `/clear` and `specs/rate-limit.md`.
2. *Write a skill, then trigger it*: compare with `.agents/skills/add-endpoint/`.
3. *Two attempts, keep one*: two worktrees (`claude --worktree rl-a`, `agent -w rl-b`) with different algorithms.

**Lecture 4**
1. *Hooks*: ask the agent to force-push, to skip a failing test, and to finish with a broken test. Watch guard, lint and gate respond.
2. *Subagents*: "Use the planner subagent to plan specs/idempotency.md", review PLAN.md, then implementer, then reviewer in a fresh context.
3. *MCP server + policy*: live-code a server from the slide (`git stash` the committed one, which is the fallback), test it with `make mcp-inspect`, wire it into a tool, and show that the permission rules allow only its three read-only tools.

## Tested with (29 Sep 2026)

- **Claude Code 2.1.284**: guard blocked `git push --force`; the stop gate made the agent fix a failing test; the agent called `order_stats` over MCP; subagents and skills were discovered; the planner wrote PLAN.md for `specs/idempotency.md`.
- **Codex CLI 0.159.0**: `codex doctor` parses the config (restricted filesystem + network, approval on-request); `codex mcp list` shows the server; `codex execpolicy check` confirms the rules. Hooks were not run live (no login in the test environment).
- **MCP Python SDK 2.2.0** (spec 2026-07-28): `mcp_server/test_orders_mcp.py` talks to the server over stdio.
- **Cursor**: configs follow the official docs but were not run.

Two things the live tests caught, both worth showing students:
1. The stop gate lints the whole repo, so leftover lint debt in *any* file keeps the agent looping until the 3-try limit.
2. An env var in `.mcp.json` that did not expand crashed the server; the model saw only "Error executing tool order_stats". Fix: resolve paths in the server, and raise `ToolError` with a hint for failures you expect.

## Windows

`.claude/skills` is a symlink to `.agents/skills`. On Windows copy the folder instead, and replace `.venv/bin/python` with `.venv\Scripts\python.exe` in the MCP configs.
