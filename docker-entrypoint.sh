#!/bin/bash
set -e

# Function to initialize database if it doesn't exist
init_database_if_needed() {
    if [ ! -f "/app/data/databases/indeed_jobs.db" ]; then
        echo "Database not found. Initializing..."
        python /app/scripts/setup_database.py
        echo "Database initialization completed."
    else
        echo "Database already exists."
    fi
}

# Always ensure directories exist and database is initialized
mkdir -p /app/data/databases /app/data/logs /app/data/cache /app/data/ontologies
init_database_if_needed

# Handle different run modes
case "$1" in
    "main"|"")
        echo "Starting SkillScopeJob Main Application..."
        exec streamlit run src/skillscope/ui/main_app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
        ;;
    "admin")
        echo "Starting SkillScopeJob Admin Dashboard..."
        exec streamlit run src/skillscope/ui/admin_app.py --server.port=8502 --server.address=0.0.0.0 --server.headless=true
        ;;
    *)
        echo "Usage: docker run skillscopejob [main|admin]"
        echo "  main  - Run the main application (default)"
        echo "  admin - Run the admin dashboard"
        exit 1
        ;;
esac
