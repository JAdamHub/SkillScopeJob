# 🐳 SkillScopeJob - Docker Setup

This document explains how to run SkillScopeJob using Docker for easy deployment and consistent environments.

## Prerequisites

- [Docker](https://www.docker.com/get-started) installed on your system
- [Docker Compose](https://docs.docker.com/compose/install/) installed on your system
- A Together AI API key

## Quick Start

1. **Clone the repository (if you haven't already)**
   ```bash
   git clone https://github.com/JAdamHub/SkillScopeJob.git
   cd SkillScopeJob
   ```

2. **Set the Together AI API key**
   
   The API key can be set in two ways:
   
   - In the `.env` file (recommended):
     ```
     TOGETHER_API_KEY=your_key_here
     ```
   
   - Or as an environment variable when running docker-compose:
     ```bash
     export TOGETHER_API_KEY=your_key_here
     ```

3. **Build and start the containers**
   ```bash
   docker-compose up -d
   ```

4. **Access the applications**
   - Main application: [http://localhost:8501](http://localhost:8501)
   - Admin dashboard: [http://localhost:8502](http://localhost:8502)

## Data Persistence

The Docker setup mounts the `data` directory as a volume, ensuring that:
- Database files
- Ontology files
- Logs
- Cache files

All persist between container restarts.

## Docker Commands

- **Start the services**
  ```bash
  docker-compose up -d
  ```

- **Stop the services**
  ```bash
  docker-compose down
  ```

- **View logs**
  ```bash
  docker-compose logs -f
  ```

- **Rebuild the image** (after code changes)
  ```bash
  docker-compose build
  ```

- **Restart the services**
  ```bash
  docker-compose restart
  ```

## Troubleshooting

- **Services not starting**
  Check logs: `docker-compose logs`

- **Database issues**
  Remove the database file and let the container rebuild it:
  ```bash
  rm -f data/databases/indeed_jobs.db
  docker-compose restart
  ```

- **Port conflicts**
  If ports 8501 or 8502 are already in use, edit the `docker-compose.yml` file to map to different ports:
  ```yaml
  ports:
    - "8503:8501"  # Map main app to 8503
    - "8504:8502"  # Map admin app to 8504
  ```

## Security Notes

- The Together AI API key is included in the container environment. In production, consider using Docker secrets or a secure environment variable management system.
- The default configuration exposes services only to localhost. For public deployments, add proper authentication and HTTPS.
- SQLite data is persisted in a volume. For production, consider using a more robust database solution.

## Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Streamlit Deployment](https://docs.streamlit.io/knowledge-base/deploy/docker)
