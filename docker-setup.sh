#!/bin/bash

# Build and run SkillScopeJob with Docker Compose
# This script simplifies the Docker setup process

set -e

echo "🐳 SkillScopeJob Docker Setup Script"
echo "====================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.docker .env
    echo ""
    echo "🔑 IMPORTANT: You need a Together AI API key to use SkillScopeJob!"
    echo ""
    echo "📋 Steps to get your API key:"
    echo "   1. Visit: https://together.ai"
    echo "   2. Sign up for an account (free tier available)"
    echo "   3. Navigate to the API section"
    echo "   4. Generate a new API key"
    echo "   5. Copy the key (starts with 'sk-')"
    echo ""
    echo "📝 Then edit the .env file and replace 'your_together_ai_api_key_here'"
    echo "   with your actual API key."
    echo ""
    echo "   Example: TOGETHER_API_KEY=sk-1234567890abcdef..."
    echo ""
    echo "💡 After setting your API key, run this script again."
    exit 1
fi

# Check if TOGETHER_API_KEY is set
if grep -q "TOGETHER_API_KEY=your_together_ai_api_key_here" .env; then
    echo "⚠️  API key not configured!"
    echo ""
    echo "🔑 Please update your TOGETHER_API_KEY in the .env file"
    echo "   Current value is still the default placeholder."
    echo ""
    echo "📋 To get your API key:"
    echo "   1. Visit: https://together.ai"
    echo "   2. Sign up for an account"
    echo "   3. Generate an API key"
    echo "   4. Replace 'your_together_ai_api_key_here' in .env"
    echo ""
    echo "💡 Your API key should start with 'sk-'"
    exit 1
fi

# Additional validation - check if key looks valid
api_key=$(grep "TOGETHER_API_KEY=" .env | cut -d'=' -f2)
if [[ ! $api_key =~ ^sk- ]]; then
    echo "⚠️  Warning: Your API key doesn't start with 'sk-'"
    echo "   Please verify your Together AI API key is correct."
    echo "   Together AI keys typically start with 'sk-'"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✅ API key appears to be configured correctly"

echo "🏗️  Building Docker images..."
docker-compose build

echo "🚀 Starting SkillScopeJob services..."
docker-compose up -d

echo ""
echo "✅ SkillScopeJob is now running!"
echo ""
echo "📱 Access the applications:"
echo "   • Main Application:  http://localhost:8501"
echo "   • Admin Dashboard:   http://localhost:8502"
echo ""
echo "🔧 Useful commands:"
echo "   • View logs:         docker-compose logs -f"
echo "   • Stop services:     docker-compose down"
echo "   • Restart services:  docker-compose restart"
echo "   • View status:       docker-compose ps"
echo ""
echo "📊 Database persistence:"
echo "   Your data is persisted in: ./data/databases/"
echo ""
