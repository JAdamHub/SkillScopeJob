#!/bin/bash

# Ensure directories exist
mkdir -p /app/data/databases
mkdir -p /app/data/logs
mkdir -p /app/data/cache
mkdir -p /app/data/ontologies

# Initialize database if it doesn't exist
if [ ! -f /app/data/databases/indeed_jobs.db ]; then
  echo "Initializing database..."
  python /app/scripts/setup_database.py
fi

# Start both Streamlit applications
echo "Starting SkillScopeJob applications..."
echo "Main application will be available at http://localhost:8501"
echo "Admin dashboard will be available at http://localhost:8502"

# Launch both applications
streamlit run /app/src/skillscope/ui/main_app.py --server.port=8501 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false &
PID1=$!

streamlit run /app/src/skillscope/ui/admin_app.py --server.port=8502 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false &
PID2=$!

# Function to handle termination
terminate() {
  echo "Received SIGTERM, shutting down..."
  kill -TERM $PID1 $PID2
  wait $PID1 $PID2
  exit 0
}

# Set up signal handling
trap terminate SIGTERM

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?
