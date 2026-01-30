"""Entry point for MCP Memoria server."""

import asyncio
import logging
import sys

from mcp_memoria.config.settings import get_settings
from mcp_memoria.server import MemoriaServer


def main() -> None:
    """Main entry point."""
    settings = get_settings()

    # Configure logging
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_level = getattr(logging, settings.log_level)

    # Always log to stderr (MCP uses stdout for protocol)
    logging.basicConfig(
        level=log_level,
        format=log_format,
        stream=sys.stderr,
    )

    # Optionally also log to file
    if settings.log_file:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(settings.log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)

    logger = logging.getLogger("mcp_memoria")
    logger.info("Starting MCP Memoria server...")
    logger.info(f"Qdrant path: {settings.qdrant_path}")
    logger.info(f"Ollama host: {settings.ollama_host}")
    logger.info(f"Embedding model: {settings.embedding_model}")

    # Run server
    server = MemoriaServer(settings)

    if settings.http_port:
        # HTTP/SSE mode
        logger.info(f"Transport: HTTP/SSE on {settings.http_host}:{settings.http_port}")
        asyncio.run(server.run_http(settings.http_port, settings.http_host))
    else:
        # stdio mode (default)
        logger.info("Transport: stdio")
        asyncio.run(server.run())


if __name__ == "__main__":
    main()
