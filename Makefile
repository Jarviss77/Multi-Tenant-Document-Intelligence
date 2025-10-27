.PHONY: help build up down restart logs clean migrate test

help:
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build:
	cd docker && docker-compose build

up:
	cd docker && docker-compose up -d

down:
	cd docker && docker-compose down

restart:
	cd docker && docker-compose restart

logs:
	cd docker && docker-compose logs -f

logs-app:
	cd docker && docker-compose logs -f app

logs-worker:
	cd docker && docker-compose logs -f worker

logs-kafka:
	cd docker && docker-compose logs -f kafka

clean: ## Stop and remove all containers, networks, and volumes
	cd docker && docker-compose down -v
	cd docker && docker system prune -f

migrate:
	cd docker && docker-compose exec app alembic upgrade head

shell-app:
	cd docker && docker-compose exec app bash

shell-worker: ## Access worker shell
	cd docker && docker-compose exec worker bash

shell-db: ## Access database shell
	cd docker && docker-compose exec db psql -U postgres -d document_intelligence

status: ## Show status of all services
	cd docker && docker-compose ps

rebuild:
	cd docker && docker-compose down
	cd docker && docker-compose up -d --build

stats: ## Show resource usage
	cd docker && docker stats

