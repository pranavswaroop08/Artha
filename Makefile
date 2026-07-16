# ---------------------------------------------------------------
# Makefile - single entry point for dev workflow
# ---------------------------------------------------------------
PY ?= python
ENV ?= dev

.PHONY: help install bootstrap dev-up dev-down migrate lint type test \
        test-unit test-integration pre-commit gen-issues

help:
	@echo "Targets:"
	@echo "  install        Install package + dev deps (uv or pip)"
	@echo "  bootstrap      Full local setup: install, start stack, migrate"
	@echo "  dev-up         Start docker-compose stack (pg, redis, minio, qdrant, mlflow)"
	@echo "  dev-down       Stop the stack"
	@echo "  migrate        Run alembic upgrade head"
	@echo "  lint           ruff + black"
	@echo "  type           mypy"
	@echo "  test           pytest (all)"
	@echo "  gen-issues     Regenerate the 150-issue backlog markdown"

install:
	$(PY) -m pip install -e ".[dev]" || uv pip install -e ".[dev]"

bootstrap: install dev-up migrate test
	@echo "Bootstrap complete."

dev-up:
	docker compose up -d

dev-down:
	docker compose down

migrate:
	alembic upgrade head

lint:
	ruff check src tests
	black --check src tests

type:
	mypy src

test:
	pytest

test-unit:
	pytest tests/unit

test-integration:
	pytest tests/integration

pre-commit:
	pre-commit run --all-files

gen-issues:
	$(PY) gen_issues.py
