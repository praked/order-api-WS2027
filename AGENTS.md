# orders-api

FastAPI service for orders. SQLite for storage, Redis for shared state. Production runs 3 replicas.

## Commands
- Set up: `make setup` (creates .venv)
- Test: `make test` · Lint: `make lint` · Auto-fix: `make fmt`
- One test: `.venv/bin/python -m pytest tests/test_orders.py -k name`
- Sample data for the MCP server: `make seed`

## Conventions
- Config only via `app/settings.py` (never `os.environ` elsewhere).
- Redis only through `app/cache.py` (`get_cache` dependency). No in-process state: 3 replicas.
- Errors: raise `APIError(status, "code")` from `app/errors.py` → `{"error": "<code>"}`.
- New dependencies need a human's approval. Prefer the standard library.

## Tests
- Fixtures in `tests/conftest.py`: `client`, `settings`, `cache` (fakeredis), `order_payload`.
- Every behaviour in a spec's "Done when" gets its own test.
- Never skip, xfail or weaken a test to make it pass. A hook blocks it.

## Workflow
- Feature specs live in `specs/`. For multi-file work: plan (PLAN.md) → implement → review (REVIEW.md).
- Finish only with `make lint` and `make test` green. A stop hook checks this.

## Boundaries
- Don't edit `.claude/`, `.codex/`, `.cursor/`, `.mcp.json` or `tools/agent_hooks/`: they hold the guardrails. Ask a human.
- Never read `.env`. No `curl`/`wget` from the shell; use the web tools.
