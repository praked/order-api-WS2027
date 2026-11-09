# Permission policy for agents in orders-api

One policy, written three times: `.claude/settings.json`, `.codex/config.toml` + `.codex/rules/policy.rules`, `.cursor/cli.json`.
Hooks (`tools/agent_hooks/hooks.py`) enforce what rules can't express, in all three tools.

| Action | Examples | Decision | Why |
|---|---|---|---|
| Read and search code | read files, grep | allow | Local, changes nothing |
| Edit code, tests, specs | `app/**`, `tests/**`, `specs/**`, PLAN.md | allow | Reversible with git |
| Run local checks | `make test`, `make lint`, pytest, ruff | allow | Local and fast |
| Inspect git | `git status`, `git diff`, `git log` | allow | Read-only |
| Query our MCP server | `get_order`, `recent_orders`, `order_stats` | allow | Read-only server we wrote |
| Fetch docs | fastapi.tiangolo.com, docs.python.org, pypi.org | allow | Known sources |
| Fetch other web pages | anything else | ask | Untrusted input (prompt injection) |
| Commit, push | `git commit`, `git push` | ask | A human signs off; push leaves the machine |
| Add dependencies | `pip install` | ask | Supply chain, network |
| Read secrets | `.env`, `.env.*` | deny | Secrets never enter the context |
| Edit the guardrails | `.claude/`, `.codex/`, `.cursor/`, `.mcp.json`, `tools/agent_hooks/` | deny | An agent can't loosen its own limits |
| Raw network from the shell | `curl`, `wget` | deny | Use the web tools, which are allowlisted |
| Destructive or evasive git | force-push, `reset --hard`, `--no-verify` | deny (hook) | Irreversible, or skips checks |
| Weaken tests | adding `pytest.mark.skip`, `xfail`, `assert True` in tests/ | deny (hook) | Rules can't see content; hooks can |

## Where each tool falls short

- **Claude Code**: `Read`/`Edit` deny rules cover its own file tools and common shell commands (`cat`, `sed`), not arbitrary scripts. Turn on `/sandbox` for OS-level enforcement. Project `allow` rules apply only after you accept the workspace trust dialog.
- **Codex CLI**: project config, hooks and rules load only for trusted projects. File denies need a permission profile (`default_permissions`), not `sandbox_mode`.
- **Cursor**: `.cursor/cli.json` applies to the Cursor CLI. The IDE uses `.cursor/permissions.json` and its run modes. Hook support in the CLI is partial; check your version.
