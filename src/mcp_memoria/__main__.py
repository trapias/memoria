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
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,  # MCP uses stdout for protocol
    )

    logger = logging.getLogger("mcp_memoria")
    logger.info("Starting MCP Memoria server...")
    logger.info(f"Qdrant path: {settings.qdrant_path}")
    logger.info(f"Ollama host: {settings.ollama_host}")
    logger.info(f"Embedding model: {settings.embedding_model}")

    # Run server
    server = MemoriaServer(settings)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
