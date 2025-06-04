# 🐳 Docker Deployment for SkillScopeJob

This document provides comprehensive instructions for deploying SkillScopeJob using Docker.

## Quick Start

### ⚠️ Important: Together AI API Key Required

Before you can run SkillScopeJob, you **MUST** obtain a Together AI API key:

1. Visit [together.ai](https://together.ai)
2. Sign up for an account
3. Navigate to the API section
4. Generate a new API key
5. Keep this key handy for the setup process

### Option 1: Automated Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/JAdamHub/SkillScopeJob.git
cd SkillScopeJob

# Run the automated setup script (it will prompt for your API key)
./docker-setup.sh
```

The script will:
- Create a `.env` file from template
- Prompt you to add your Together AI API key
- Validate the API key is set
- Build and start the Docker services

### Option 2: Manual Setup

```bash
# Clone the repository
git clone https://github.com/JAdamHub/SkillScopeJob.git
cd SkillScopeJob

# Copy environment template
cp .env.docker .env

# ⚠️ CRITICAL: Edit .env with your ACTUAL Together AI API key
# Replace "your_together_ai_api_key_here" with your real API key
nano .env

# Build and start services
docker-compose up -d
```

**Example .env file:**
```bash
# Together AI API Key (Required)
TOGETHER_API_KEY=sk-1234567890abcdef...your_actual_api_key_here
```

## Access Points

- **Main Application**: http://localhost:8501
- **Admin Dashboard**: http://localhost:8502

## Docker Files Overview

### Core Docker Files

- **`Dockerfile`**: Multi-stage build for optimized container
- **`docker-compose.yml`**: Service orchestration with both main and admin apps
- **`docker-entrypoint.sh`**: Smart entrypoint handling database initialization
- **`.dockerignore`**: Optimized build context
- **`.env.docker`**: Environment template for Docker

### Helper Scripts

- **`docker-setup.sh`**: Automated setup and deployment script

## Container Architecture

### Main Application Container
- **Port**: 8501
- **Service**: Main SkillScopeJob application
- **Health Check**: Streamlit health endpoint
- **Auto-restart**: Unless stopped manually

### Admin Dashboard Container
- **Port**: 8502
- **Service**: Administrative interface
- **Health Check**: Streamlit health endpoint
- **Auto-restart**: Unless stopped manually

## Data Persistence

### Volume Mounts
The following directories are automatically mounted for data persistence:

```
./data/databases   → /app/data/databases   (SQLite database)
./data/logs        → /app/data/logs        (Application logs)
./data/cache       → /app/data/cache       (Temporary cache)
```

### Database Initialization
- Database is automatically created on first run
- Uses the same `setup_database.py` script as local installation
- Persistent across container restarts

## Environment Variables

### Required Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TOGETHER_API_KEY` | Together AI API key for LLM services | *Required* |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `STREAMLIT_SERVER_HEADLESS` | Run Streamlit in headless mode | `true` |
| `PYTHONUNBUFFERED` | Unbuffered Python output | `1` |

## Docker Commands

### Basic Operations

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Restart services
docker-compose restart

# View service status
docker-compose ps

# Scale services (if needed)
docker-compose up -d --scale skillscopejob-main=2
```

### Individual Container Management

```bash
# Build single image
docker build -t skillscopejob .

# Run main app only
docker run -d \
  -p 8501:8501 \
  -e TOGETHER_API_KEY="your_api_key" \
  -v "$(pwd)/data/databases:/app/data/databases" \
  skillscopejob main

# Run admin dashboard only
docker run -d \
  -p 8502:8502 \
  -e TOGETHER_API_KEY="your_api_key" \
  -v "$(pwd)/data/databases:/app/data/databases" \
  skillscopejob admin
```

## GitHub Container Registry (GHCR)

### Publishing to GHCR

```bash
# Tag for GHCR
docker tag skillscopejob ghcr.io/JAdamHub/skillscopejob:latest

# Login to GHCR
docker login ghcr.io -u JAdamHub -p YOUR_PAT

# Push to GHCR
docker push ghcr.io/JAdamHub/skillscopejob:latest
```

### Using from GHCR

```bash
# Pull from GHCR
docker pull ghcr.io/JAdamHub/skillscopejob:latest

# Run from GHCR
docker run -d \
  -p 8501:8501 \
  -e TOGETHER_API_KEY="your_api_key" \
  -v "$(pwd)/data/databases:/app/data/databases" \
  ghcr.io/JAdamHub/skillscopejob:latest
```

## Troubleshooting

### Common Issues

#### Port Already in Use
```bash
# Check what's using the port
lsof -i :8501
lsof -i :8502

# Use different ports
docker-compose up -d --scale skillscopejob-main=1 --scale skillscopejob-admin=1
```

#### Permission Issues
```bash
# Fix data directory permissions
sudo chown -R $USER:$USER ./data
```

#### Container Won't Start
```bash
# Check logs
docker-compose logs skillscopejob-main
docker-compose logs skillscopejob-admin

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

#### Database Issues
```bash
# Reinitialize database
docker-compose exec skillscopejob-main python scripts/setup_database.py

# Check database file
docker-compose exec skillscopejob-main ls -la data/databases/
```

### Health Checks

```bash
# Check container health
docker-compose ps

# Manual health check
curl http://localhost:8501/_stcore/health
curl http://localhost:8502/_stcore/health
```

## Production Deployment

### Security Considerations

1. **Environment Variables**: Never commit API keys to version control
2. **Network Security**: Consider using Docker networks for service isolation
3. **Resource Limits**: Set appropriate CPU and memory limits
4. **SSL/TLS**: Use reverse proxy (nginx) for HTTPS in production

### Example Production docker-compose.yml

```yaml
version: '3.8'

services:
  skillscopejob-main:
    image: ghcr.io/JAdamHub/skillscopejob:latest
    container_name: skillscopejob-main
    ports:
      - "127.0.0.1:8501:8501"  # Bind to localhost only
    environment:
      - TOGETHER_API_KEY=${TOGETHER_API_KEY}
    volumes:
      - skillscope_data:/app/data
    command: main
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G

volumes:
  skillscope_data:
    driver: local
```

## Monitoring and Logging

### Log Management

```bash
# View logs
docker-compose logs -f --tail=100

# Export logs
docker-compose logs > skillscope.log

# Rotate logs (in production)
docker-compose logs --tail=0 -f | logger -t skillscope
```

### Monitoring

```bash
# Resource usage
docker stats $(docker-compose ps -q)

# Container health
docker-compose ps
```

## Backup and Recovery

### Database Backup

```bash
# Backup database
docker-compose exec skillscopejob-main \
  cp /app/data/databases/indeed_jobs.db /app/data/databases/backup_$(date +%Y%m%d_%H%M%S).db

# Copy backup to host
docker cp skillscopejob-main:/app/data/databases/backup_*.db ./
```

### Full Data Backup

```bash
# Create compressed backup
tar -czf skillscope_backup_$(date +%Y%m%d_%H%M%S).tar.gz ./data
```

## Updates and Maintenance

### Updating the Application

```bash
# Pull latest images
docker-compose pull

# Recreate containers with new images
docker-compose up -d --force-recreate

# Clean up old images
docker image prune -f
```

### Maintenance Tasks

```bash
# Clean up Docker system
docker system prune -f

# View disk usage
docker system df

# Clean up volumes (careful!)
docker volume prune -f
```
