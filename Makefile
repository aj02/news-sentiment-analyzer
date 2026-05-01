.PHONY: help install dev test lint fmt typecheck run docker-build docker-up docker-down docker-logs clean

PYTHON ?= python
PIP ?= $(PYTHON) -m pip

help:
	@echo "Targets:"
	@echo "  install      Install runtime + dev dependencies into the active env."
	@echo "  test         Run pytest with coverage summary."
	@echo "  lint         Run ruff in lint mode."
	@echo "  fmt          Run ruff format (writes changes)."
	@echo "  typecheck    Run mypy."
	@echo "  run          Run uvicorn with reload (uses local .env)."
	@echo "  docker-build Build the runtime image."
	@echo "  docker-up    docker-compose up --build."
	@echo "  docker-down  docker-compose down -v."
	@echo "  docker-logs  Tail compose logs."
	@echo "  clean        Remove caches and build artifacts."

install:
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest -ra --cov=app --cov-report=term-missing

lint:
	$(PYTHON) -m ruff check .

fmt:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

typecheck:
	$(PYTHON) -m mypy app

run:
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker build -t news-sentiment-analyzer:local .

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

docker-logs:
	docker compose logs -f --tail=200

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build
	find . -type d -name __pycache__ -exec rm -rf {} +
