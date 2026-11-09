# Spec: rate limiting for POST /orders (Lecture 3, Demo 1)

**Goal:** stop clients flooding POST /orders.

**Behaviour**
- 10 requests/min per API key (header `X-API-Key`); no key → per client IP (`X-Forwarded-For`, first entry).
- Over the limit → `429 {"error": "rate_limited"}` plus a `Retry-After` header in seconds.

**Constraints**
- 3 replicas: keep counters in Redis via `app/cache.py`.
- No new dependencies. The limit lives in `app/settings.py` (`rate_limit_per_min`, default 10).

**Done when**
- `tests/test_rate_limit.py`: the 11th call within a minute → 429 with Retry-After; the counter resets after 60 s; `GET /health` is never limited.
- `make test` and `make lint` pass.

**Out of scope:** auth changes, other routes.

**Start from:** `app/routes/orders.py`, `app/cache.py`, `tests/conftest.py`
