# Makefile for SkillScopeJob Docker operations

.PHONY: help build up down logs status clean setup dev-up dev-down health test

# Default target
help:
	@echo "SkillScopeJob Docker Commands"
	@echo "============================"
	@echo ""
	@echo "🔑 Setup Commands:"
	@echo "  check-api - Validate Together AI API key"
	@echo "  setup     - Initial setup with environment check"
	@echo ""
	@echo "Production Commands:"
	@echo "  build     - Build Docker images"
	@echo "  up        - Start all services"
	@echo "  down      - Stop all services"
	@echo "  restart   - Restart all services"
	@echo "  logs      - View logs from all services"
	@echo "  status    - Show service status"
	@echo "  health    - Run health checks"
	@echo ""
	@echo "Development Commands:"
	@echo "  dev-up    - Start development services with code mounting"
	@echo "  dev-down  - Stop development services"
	@echo "  dev-logs  - View development logs"
	@echo ""
	@echo "Maintenance Commands:"
	@echo "  clean     - Clean up Docker resources"
	@echo "  backup    - Backup database"
	@echo "  test      - Test Docker build"

# Check and validate API key
check-api:
	@echo "🔑 Checking Together AI API key..."
	@./test-api-key.sh

# Check if .env file exists
check-env:
	@if [ ! -f .env ]; then \
		echo "⚠️  .env file not found. Creating from template..."; \
		cp .env.docker .env; \
		echo "📝 Please edit .env file and add your TOGETHER_API_KEY"; \
		echo "   Get your API key from: https://together.ai"; \
		exit 1; \
	fi
	@if grep -q "your_together_ai_api_key_here" .env; then \
		echo "⚠️  Please update TOGETHER_API_KEY in .env file"; \
		exit 1; \
	fi
	@echo "✅ Environment configuration looks good"

# Initial setup
setup: check-env check-api
	@echo "🚀 Setting up SkillScopeJob..."
	@echo "✅ All checks passed!"
	@docker-compose build
	@docker-compose up -d
	@echo "🎉 SkillScopeJob is now running!"
	@echo "📱 Main Application: http://localhost:8501"
	@echo "📱 Admin Dashboard: http://localhost:8502"

# Build images
build:
	@echo "🏗️  Building Docker images..."
	@docker-compose build

# Start production services
up: check-env
	@echo "🚀 Starting SkillScopeJob services..."
	@docker-compose up -d
	@echo "✅ Services started!"
	@echo "📱 Main Application: http://localhost:8501"
	@echo "📱 Admin Dashboard: http://localhost:8502"

# Stop services
down:
	@echo "🛑 Stopping SkillScopeJob services..."
	@docker-compose down

# Restart services
restart: down up

# View logs
logs:
	@docker-compose logs -f

# Show status
status:
	@echo "📊 Service Status:"
	@docker-compose ps

# Run health checks
health:
	@./health-check.sh

# Development mode
dev-up: check-env
	@echo "🛠️  Starting development services..."
	@docker-compose -f docker-compose.dev.yml up -d
	@echo "✅ Development services started!"
	@echo "📱 Main Application: http://localhost:8501"
	@echo "📱 Admin Dashboard: http://localhost:8502"
	@echo "🔄 Code changes will be automatically reloaded"

dev-down:
	@echo "🛑 Stopping development services..."
	@docker-compose -f docker-compose.dev.yml down

dev-logs:
	@docker-compose -f docker-compose.dev.yml logs -f

# Clean up Docker resources
clean:
	@echo "🧹 Cleaning up Docker resources..."
	@docker-compose down --volumes --remove-orphans
	@docker system prune -f
	@echo "✅ Cleanup completed"

# Backup database
backup:
	@echo "💾 Creating database backup..."
	@mkdir -p backups
	@docker-compose exec skillscopejob-main \
		cp /app/data/databases/indeed_jobs.db \
		/app/data/databases/backup_$(shell date +%Y%m%d_%H%M%S).db
	@docker cp skillscopejob-main:/app/data/databases/backup_*.db ./backups/
	@echo "✅ Backup created in ./backups/"

# Test Docker build
test:
	@echo "🧪 Testing Docker build..."
	@docker build -t skillscopejob-test .
	@echo "✅ Build test completed"
	@docker rmi skillscopejob-test
