#!/bin/bash

# SkillScopeJob Docker startup helper script

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Please install Docker first: https://www.docker.com/get-started"
    exit 1
fi

# Check if Docker Compose plugin is available
if ! docker compose version &> /dev/null; then
    echo "Docker Compose plugin not found. Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env file with the provided API key..."
    echo "TOGETHER_API_KEY=f7f98865262e753df89a8ac3b7bc474ff5eb2e86416e78550148a64d061e36ed" > .env
else
    # Check if TOGETHER_API_KEY is in .env
    if ! grep -q "TOGETHER_API_KEY" .env; then
        echo "Adding Together AI API key to .env..."
        echo "TOGETHER_API_KEY=f7f98865262e753df89a8ac3b7bc474ff5eb2e86416e78550148a64d061e36ed" >> .env
    fi
fi

# Create necessary directories
mkdir -p data/databases
mkdir -p data/logs
mkdir -p data/cache
mkdir -p data/ontologies

echo "Building and starting SkillScopeJob Docker containers..."
docker compose up -d

echo ""
echo "✅ SkillScopeJob is starting up!"
echo "🔍 Main application: http://localhost:8501"
echo "⚙️ Admin dashboard: http://localhost:8502"
echo ""
echo "To view logs: docker compose logs -f"
echo "To stop: docker compose down"
