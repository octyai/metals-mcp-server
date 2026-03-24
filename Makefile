.PHONY: dev install test lint run ingest schemas package

install:
	python -m pip install -e .[dev]

dev:
	uvicorn metals_mcp.app:create_app --factory --reload --port 8080

test:
	pytest

lint:
	ruff check src tests

run:
	uvicorn metals_mcp.app:create_app --factory --host 0.0.0.0 --port 8080

ingest:
	python -m metals_mcp.cli ingest --all

schemas:
	python scripts/export_schemas.py
	python scripts/export_openapi.py

package:
	tar --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' --exclude='.mypy_cache' --exclude='*.pyc' --exclude='*.db' --exclude='data/raw' --exclude='data/reports' --exclude='.env' --exclude='.venv' --exclude='artifacts' --exclude='htmlcov' --exclude='coverage.xml' -czf metals-mcp-server.tar.gz .
