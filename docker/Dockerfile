# MCP Memoria Server Dockerfile
FROM python:3.12-slim

LABEL maintainer="alberto"
LABEL description="MCP Memoria - Unlimited local AI memory server"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app user
RUN groupadd -r memoria && useradd -r -g memoria memoria

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files (con permessi per l'utente memoria)
COPY --chown=memoria:memoria pyproject.toml README.md ./
COPY --chown=memoria:memoria src ./src

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create data directories con permessi corretti
RUN mkdir -p /data/qdrant /data/cache && \
    chown -R memoria:memoria /data /app

# Set environment defaults
ENV MEMORIA_QDRANT_PATH=/data/qdrant \
    MEMORIA_CACHE_PATH=/data/cache \
    MEMORIA_OLLAMA_HOST=http://host.docker.internal:11434 \
    MEMORIA_LOG_LEVEL=INFO

# Switch to non-root user
USER memoria

# Expose volume for persistent data
VOLUME ["/data"]

# Run the MCP server
ENTRYPOINT ["python", "-m", "mcp_memoria"]
