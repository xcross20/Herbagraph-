.PHONY: dev test coverage migrate seed lint format worker logs clean

dev:
	docker-compose up -d

test:
	pytest

coverage:
	pytest --cov=app --cov-report=html --cov-report=term-missing

migrate:
	alembic upgrade head

seed:
	python scripts/seed_db.py

lint:
	ruff check app tests
	mypy app

format:
	ruff format app tests

worker:
	celery -A app.workers.celery_app worker --loglevel=info

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
