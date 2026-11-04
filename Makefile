.PHONY: setup db migrate backend frontend check test e2e
setup:
	uv sync --project backend --frozen
	npm ci --prefix frontend

db:
	docker compose up -d db

migrate:
	@if [ -n "$$MIGRATION_DATABASE_URL" ]; then DATABASE_URL="$$MIGRATION_DATABASE_URL" uv run --project backend python backend/manage.py migrate; else uv run --project backend python backend/manage.py migrate; fi

backend:
	uv run --project backend python backend/manage.py runserver 127.0.0.1:8000

frontend:
	npm run dev --prefix frontend

check:
	uv run --directory backend ruff check .
	uv run --directory backend ruff format --check .
	uv run --directory backend mypy library config
	uv run --project backend python backend/manage.py check
	uv run --project backend python backend/manage.py makemigrations --check --dry-run
	uv run --project backend pytest -q
	npm test --prefix frontend
	npm run build --prefix frontend

test:
	uv run --project backend pytest
	npm test --prefix frontend

e2e:
	bash scripts/e2e.sh

schema:
	mkdir -p .superpowers
	uv run --project backend python scripts/export_schema.py > .superpowers/openapi.json
	npx --prefix frontend openapi-typescript .superpowers/openapi.json -o frontend/src/generated/schema.d.ts
