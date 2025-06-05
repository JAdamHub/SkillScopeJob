# 🐳 SkillScopeJob Docker Deployment Guide
This guide provides instructions for deploying SkillScopeJob using Docker, with a focus on security and ease of use.

## 🔍 Information

SkillScopeJob consists of two interfaces:
- **Main Application (Port 8501)**: User interface for CV analysis and job matching
- **Admin Dashboard (Port 8502)**: Administrative interface for system management

## 🚀 Quick Start

### Option 1: Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/JAdamHub/SkillScopeJob.git
cd SkillScopeJob

# Set up environment variables
cp .env.example .env
# Edit .env with your Together API key
TOGETHER_API_KEY=your_together_api_key_here

# Start both interfaces
docker-compose up -d

# Access applications:
# Main: http://localhost:8501
# Admin: http://localhost:8502
```

### Option 2: Using GitHub Container Registry

```bash
# Pull the latest image
docker pull ghcr.io/jadamhub/skillscopejob:latest

# Create data directories
mkdir -p data/databases data/logs data/cache

# Run main application
docker run -d \
  --name skillscopejob-main \
  -p 8501:8501 \
  -e TOGETHER_API_KEY="your_api_key_here" \
  -v "$(pwd)/data:/app/data" \
  ghcr.io/jadamhub/skillscopejob:latest

# Run admin dashboard
docker run -d \
  --name skillscopejob-admin \
  -p 8502:8502 \
  -e TOGETHER_API_KEY="your_api_key_here" \
  -v "$(pwd)/data:/app/data" \
  ghcr.io/jadamhub/skillscopejob:latest admin
```

## 🏗️ Building Docker Image Locally

If you want to build the Docker image locally instead of using the pre-built image from GHCR:

```bash
# Clone the repository
git clone https://github.com/JAdamHub/SkillScopeJob.git
cd SkillScopeJob

# Build the image
docker build -t skillscopejob .

# Verify the image was created
docker images | grep skillscopejob

# Run the main application with your locally built image
docker run -d \
  --name skillscopejob-main \
  -p 8501:8501 \
  -e TOGETHER_API_KEY="your_api_key_here" \
  -v "$(pwd)/data:/app/data" \
  skillscopejob

# Run the admin dashboard with your locally built image
docker run -d \
  --name skillscopejob-admin \
  -p 8502:8502 \
  -e TOGETHER_API_KEY="your_api_key_here" \
  -v "$(pwd)/data:/app/data" \
  skillscopejob admin
```

## 🔒 Secure API Key Management

### Best Practices

The application requires a Together.ai API key to function. For security:

- **NEVER** store API keys in the Docker image or version control
- **ALWAYS** pass the API key at runtime via environment variables
- Use `.env` files (for docker-compose) or direct environment variables (for docker run)

### Method 1: Using .env File (for docker-compose)

```bash
# Create .env file (NEVER commit this to version control)
echo "TOGETHER_API_KEY=your_api_key_here" > .env

# Start with docker-compose
docker-compose up -d
```

### Method 2: Direct Environment Variable (for docker run)

```bash
docker run -d \
  --name skillscopejob-main \
  -p 8501:8501 \
  -e TOGETHER_API_KEY="your_api_key_here" \
  -v "$(pwd)/data:/app/data" \
  skillscopejob
```

### Method 3: Using Docker Secrets (Production)

For production environments, consider using Docker secrets:

```bash
# Create a secret
echo "your_api_key" | docker secret create together_api_key -

# Use the secret in a Docker Swarm service
docker service create \
  --name skillscopejob \
  --secret together_api_key \
  --publish 8501:8501 \
  ghcr.io/jadamhub/skillscopejob:latest
```

## 📊 Development Environment

For development with live code reloading:

```bash
# Start the development environment
docker-compose -f docker-compose.dev.yml up -d

# This mounts the src directory for live code editing
```

## 🔄 GitHub Container Registry Integration

SkillScopeJob images are automatically published to GitHub Container Registry via GitHub Actions whenever code is pushed to the main branch.

### Using Pre-built Images from GHCR

```bash
# Pull the latest image (recommended for Docker deployment)
docker pull ghcr.io/jadamhub/skillscopejob:latest

# Run main application using GHCR image from main branch
docker run -d \
  --name skillscopejob-main \
  -p 8501:8501 \
  -e TOGETHER_API_KEY="your_api_key_here" \
  -v "$(pwd)/data:/app/data" \
  ghcr.io/jadamhub/skillscopejob:latest
```

## 🧪 Testing Docker Setup Locally

To verify your Docker setup is working correctly:

```bash
# Check if containers are running
docker ps | grep skillscopejob

# Test main application endpoint
curl http://localhost:8501/_stcore/health

# Test admin dashboard endpoint
curl http://localhost:8502/_stcore/health

# View logs for debugging
docker logs skillscopejob-main
docker logs skillscopejob-admin
```

## 🛠️ Common Commands

```bash
# View logs
docker logs skillscopejob-main
docker logs skillscopejob-admin

# Stop containers
docker-compose down

# Restart services
docker-compose restart

# Check container status
docker ps -a | grep skillscopejob

# Remove containers
docker rm -f skillscopejob-main skillscopejob-admin
```
