#!/bin/bash

# Test Together AI API Key
# This script validates that your Together AI API key is working

set -e

echo "🔑 Together AI API Key Validator"
echo "=================================="

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "   Please create .env file with your TOGETHER_API_KEY"
    exit 1
fi

# Load environment variables
source .env

# Check if API key is set
if [ -z "$TOGETHER_API_KEY" ]; then
    echo "❌ Error: TOGETHER_API_KEY not set in .env file"
    exit 1
fi

# Check if API key is still placeholder
if [ "$TOGETHER_API_KEY" = "your_together_ai_api_key_here" ]; then
    echo "❌ Error: TOGETHER_API_KEY is still the placeholder value"
    echo "   Please replace with your actual Together AI API key"
    exit 1
fi

# Check if API key format looks correct
if [[ ! $TOGETHER_API_KEY =~ ^sk- ]]; then
    echo "⚠️  Warning: API key doesn't start with 'sk-'"
    echo "   Together AI keys typically start with 'sk-'"
fi

echo "🧪 Testing API key with Together AI..."

# Test API key by making a simple request
response=$(curl -s -X POST \
  "https://api.together.xyz/v1/models" \
  -H "Authorization: Bearer $TOGETHER_API_KEY" \
  -H "Content-Type: application/json" \
  --max-time 10)

# Check if request was successful
if echo "$response" | grep -q '"object": "list"'; then
    echo "✅ API key is valid and working!"
    echo "🎉 Your Together AI integration is ready"
    
    # Show available models
    model_count=$(echo "$response" | grep -o '"id":' | wc -l)
    echo "📊 Available models: $model_count"
    
    # Show some popular models if available
    if echo "$response" | grep -q "meta-llama"; then
        echo "🦙 Meta LLaMA models detected"
    fi
    if echo "$response" | grep -q "mistralai"; then
        echo "🌊 Mistral AI models detected"
    fi
    
else
    echo "❌ API key test failed"
    echo "🔍 Response: $response"
    
    if echo "$response" | grep -q "401"; then
        echo "💡 This looks like an authentication error"
        echo "   Please check your API key is correct"
    elif echo "$response" | grep -q "403"; then
        echo "💡 This looks like a permission error"
        echo "   Please check your Together AI account status"
    else
        echo "💡 Please check your internet connection and try again"
    fi
    exit 1
fi

echo ""
echo "🐳 You're ready to run SkillScopeJob with Docker!"
echo "   Run: ./docker-setup.sh"
