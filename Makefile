VENV ?= .venv
PY   := $(VENV)/bin/python

.PHONY: setup test lint fmt run seed mcp-inspect check-kit

setup:            ## create .venv and install dependencies
	python3 -m venv $(VENV)
	$(PY) -m pip install -q -r requirements.txt

test:             ## run the test suite (the hooks call this too)
	$(PY) -m pytest

lint:             ## ruff lint + format check
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

fmt:              ## auto-fix lint issues and format
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .

run:              ## start the API on http://localhost:8000
	$(PY) -m uvicorn app.main:app --reload

seed:             ## create orders.db with sample orders (for the MCP demo)
	$(PY) scripts/seed.py

mcp-inspect:      ## open the MCP Inspector on the orders server (needs Node >= 22)
	npx @modelcontextprotocol/inspector $(PY) mcp_server/orders_mcp.py

check-kit:        ## test the hook scripts and the MCP server themselves
	$(PY) -m pytest tools/agent_hooks/test_hooks.py mcp_server/test_orders_mcp.py
