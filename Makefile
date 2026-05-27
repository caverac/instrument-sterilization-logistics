.PHONY: dev-up dev-down dev-reset dev-logs dev-topics lint typecheck test cov

# ---- Local dev stack -------------------------------------------------------

dev-up:
	docker compose up -d

dev-down:
	docker compose down

dev-reset:
	docker compose down -v

dev-logs:
	docker compose logs -f

dev-topics:
	docker compose exec redpanda rpk topic list

# ---- Quality gates ---------------------------------------------------------

lint:
	uv run pre-commit run --all-files

typecheck:
	uv run mypy services/

test:
	uv run pytest services/ -v

cov:
	uv run pytest services/ --cov --cov-report=term-missing --cov-fail-under=100
