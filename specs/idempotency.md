# Spec: idempotent POST /orders (Lecture 3 exercise, Lecture 4 Demo 2)

**Goal:** a client that retries POST /orders after a timeout never creates a second order.

**Behaviour**
- Clients may send an `Idempotency-Key` header (1–64 chars). Without it, behaviour is unchanged.
- Keys are scoped per API key (`X-API-Key`, or `anonymous` if absent) and remembered for 24 h.
- First request with a key: create the order as today; store status code and body under the key.
- Repeat with the same key and the same body: return the stored status and body; create nothing.
- Same key, different body: `422 {"error": "idempotency_key_reused"}`.
- Same key while the first request is still in flight: `409 {"error": "request_in_progress"}`.
- Only successful (2xx) responses are stored; errors are not replayed.

**Constraints**
- 3 replicas: store keys in Redis via `app/cache.py`; claim a key atomically (`SET NX EX`).
- No new dependencies. TTL lives in `app/settings.py` (`idempotency_ttl_s`, default 86400).

**Done when**
- `tests/test_idempotency.py` covers: repeat → same response and one order in the DB; different body → 422; in-flight duplicate → 409; no header → unchanged behaviour; key expiry after TTL (fakeredis time).
- `make test` and `make lint` pass.

**Out of scope:** other routes, persisting keys beyond Redis, changing the order schema.

**Start from:** `app/routes/orders.py`, `app/cache.py`, `app/settings.py`, `tests/conftest.py`
