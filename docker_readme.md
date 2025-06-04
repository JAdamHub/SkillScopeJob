# Dockerizing SkillScopeJob

This guide provides instructions on how to build and run the SkillScopeJob application using Docker.

## Prerequisites

- **Docker**: Ensure Docker Desktop or Docker Engine is installed and running on your system. You can download it from [docker.com](https://www.docker.com/products/docker-desktop/).
- **Together AI API Key**: You MUST have a valid Together AI API key. Get one from [together.ai](https://together.ai)

## Building the Docker Image

1.  **Navigate to the project root directory** (where the `Dockerfile` is located).
2.  **Build the image** using the following command. Replace `skillscopejob` with your preferred image name and tag:

    ```bash
    docker build -t skillscopejob .
    ```

    This command will:
    - Use the `Dockerfile` in the current directory.
    - Tag the image as `skillscopejob:latest`.

## Running the Container

### Environment Variables

-   `TOGETHER_API_KEY`: This is a **required** environment variable. You must provide your Together AI API key for the application's AI features to work.

### Data Persistence (SQLite Database)

The application uses an SQLite database located at `/app/data/databases/indeed_jobs.db` within the container. To persist this data across container restarts, you should mount a local directory to this path.

**Example**: If you want to store the database in `./my_skillscope_data/databases` on your host machine:

-   Create the host directory: `mkdir -p ./my_skillscope_data/databases`
-   When running the container, use the volume mount: `-v "$(pwd)/my_skillscope_data/databases:/app/data/databases"`

### Running the Main Application

To run the main SkillScopeJob application (default):

```bash
docker run -d \
  -p 8501:8501 \
  -e TOGETHER_API_KEY="YOUR_TOGETHER_AI_API_KEY" \
  -v "$(pwd)/my_skillscope_data/databases:/app/data/databases" \
  skillscopejob
```

Or explicitly:

```bash
docker run -d \
  -p 8501:8501 \
  -e TOGETHER_API_KEY="YOUR_TOGETHER_AI_API_KEY" \
  -v "$(pwd)/my_skillscope_data/databases:/app/data/databases" \
  skillscopejob main
```

-   `-d`: Runs the container in detached mode (in the background).
-   `-p 8501:8501`: Maps port 8501 on your host to port 8501 in the container.
-   `-e TOGETHER_API_KEY="YOUR_TOGETHER_AI_API_KEY"`: Sets the required API key. **Replace `"YOUR_TOGETHER_AI_API_KEY"` with your actual key.**
-   `-v "$(pwd)/my_skillscope_data/databases:/app/data/databases"`: Mounts the local directory for database persistence. Adjust `$(pwd)/my_skillscope_data/databases` to your desired host path.
-   `skillscopejob`: The name of the image you built.
-   `main` (optional): Specifies to run the main application (this is the default if omitted).

**Accessing the Main Application**: Open your web browser and go to `http://localhost:8501`.

### Running the Admin Dashboard

To run the admin dashboard application:

```bash
docker run -d \
  -p 8502:8502 \
  -e TOGETHER_API_KEY="YOUR_TOGETHER_AI_API_KEY" \
  -v "$(pwd)/my_skillscope_data/databases:/app/data/databases" \
  skillscopejob admin
```

-   `-p 8502:8502`: Maps port 8502 on your host to port 8502 in the container for the admin app.
-   `admin`: This argument to the `docker run` command tells the entrypoint script to start the admin application.

**Accessing the Admin Dashboard**: Open your web browser and go to `http://localhost:8502`.

### Stopping the Container

1.  Find the container ID: `docker ps`
2.  Stop the container: `docker stop <container_id>`

## Data Persistence Reminder

It is **crucial** to use the volume mount (`-v`) option as shown in the examples if you want your SQLite database (job data, user profiles, etc.) to persist when the container is stopped or removed. Otherwise, all data will be lost.

## GitHub Container Registry (GHCR) Integration (Optional)

You can publish your Docker image to GHCR to share it or use it in CI/CD pipelines.

### Prerequisites for GHCR

-   A GitHub account.
-   A Personal Access Token (PAT) with `write:packages` and `read:packages` scopes. You can create one in your GitHub Developer settings.

### Steps to Push to GHCR

1.  **Tag the image for GHCR**:
    Replace `YOUR_GITHUB_USERNAME` with your actual GitHub username and `skillscopejob` if you used a different local image name.

    ```bash
    docker tag skillscopejob ghcr.io/JAdamHub/skillscopejob:latest
    ```
    You can also use specific version tags, e.g., `ghcr.io/JAdamHub/skillscopejob:1.0.0`.

2.  **Log in to GHCR**:
    Use your GitHub username and the Personal Access Token (PAT) you created.

    ```bash
    docker login ghcr.io -u JAdamHub -p YOUR_PAT
    ```

3.  **Push the image to GHCR**:

    ```bash
    docker push ghcr.io/JAdamHub/skillscopejob:latest
    ```
    If you used a version tag, push that tag as well.

### Pulling and Running from GHCR

Once pushed, others (or your deployment systems) can pull and run the image:

1.  **Pull the image from GHCR** (public images don't require login for pulling):

    ```bash
    docker pull ghcr.io/JAdamHub/skillscopejob:latest
    ```
    If the package is private, the user will need to `docker login ghcr.io` first.

2.  **Run the image from GHCR**:
    The `docker run` commands are the same as above, just replace the image name with the GHCR path:

    **Main App Example:**
    ```bash
    docker run -d \
      -p 8501:8501 \
      -e TOGETHER_API_KEY="YOUR_TOGETHER_AI_API_KEY" \
      -v "$(pwd)/my_skillscope_data/databases:/app/data/databases" \
      ghcr.io/JAdamHub/skillscopejob:latest main
    ```

    **Admin App Example:**
    ```bash
    docker run -d \
      -p 8502:8502 \
      -e TOGETHER_API_KEY="YOUR_TOGETHER_AI_API_KEY" \
      -v "$(pwd)/my_skillscope_data/databases:/app/data/databases" \
      ghcr.io/JAdamHub/skillscopejob:latest admin
    ```

Remember to replace `YOUR_GITHUB_USERNAME` and provide the necessary environment variables and volume mounts. 