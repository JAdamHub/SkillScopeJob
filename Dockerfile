FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including graphviz and curl for healthchecks
RUN apt-get update && apt-get install -y \
    graphviz \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entrypoint script and make it executable
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Copy the rest of the application
COPY . .

# Create necessary directories if they don't exist
RUN mkdir -p data/databases data/logs data/cache data/ontologies

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_ENABLE_CORS=false
ENV STREAMLIT_SERVER_HEADLESS=true

# Expose ports for Streamlit apps
EXPOSE 8501
EXPOSE 8502

# Command to run when container starts
ENTRYPOINT ["./docker-entrypoint.sh"]
