.PHONY: help setup start stop restart logs clean backup ingest

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

setup: ## Initial setup (create .env, start containers)
	@./setup.sh

start: ## Start all containers
	@echo "Starting Ummatics Impact Monitor..."
	@docker-compose up -d
	@echo "Services started!"
	@echo "Dashboard: http://localhost:3000"

stop: ## Stop all containers
	@echo "Stopping containers..."
	@docker-compose down
	@echo "Containers stopped!"

restart: ## Restart all containers
	@echo "Restarting containers..."
	@docker-compose restart
	@echo "Containers restarted!"

logs: ## View logs from all containers
	@docker-compose logs -f

logs-api: ## View API logs
	@docker-compose logs -f api

logs-scheduler: ## View scheduler logs
	@docker-compose logs -f scheduler

logs-frontend: ## View frontend logs
	@docker-compose logs -f frontend

logs-db: ## View database logs
	@docker-compose logs -f db

status: ## Show status of all containers
	@docker-compose ps

ingest: ## Run manual data ingestion
	@echo "Running data ingestion..."
	@docker-compose exec api python ingestion.py

backup: ## Backup the database
	@echo "Backing up database..."
	@mkdir -p backups
	@docker-compose exec -T db pg_dump -U postgres ummatics_monitor > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup saved to backups/"

restore: ## Restore database from latest backup (use BACKUP_FILE=path to specify)
	@echo "Restoring database..."
	@docker-compose exec -T db psql -U postgres ummatics_monitor < $(BACKUP_FILE)
	@echo "Database restored!"

clean: ## Remove all containers and volumes
	@echo "⚠️  This will remove all containers and data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		echo "Cleanup complete!"; \
	fi

shell-api: ## Open shell in API container
	@docker-compose exec api /bin/sh

shell-db: ## Open PostgreSQL shell
	@docker-compose exec db psql -U postgres -d ummatics_monitor

test-backend: ## Run backend tests
	@docker-compose exec api pytest

install-frontend: ## Install frontend dependencies
	@cd frontend && npm install

dev-frontend: ## Run frontend in development mode (local)
	@cd frontend && npm run dev

dev-backend: ## Run backend in development mode (local)
	@cd backend && source venv/bin/activate && python api.py

build: ## Build all containers
	@docker-compose build

rebuild: ## Rebuild all containers from scratch
	@docker-compose build --no-cache

health: ## Check health of all services
	@echo "Checking service health..."
	@curl -s http://localhost:5000/api/health | python -m json.tool
