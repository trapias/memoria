"""Entry point for MCP Memoria server."""

import argparse
import asyncio
import logging
import subprocess
import sys

from mcp_memoria import __version__
from mcp_memoria.config.settings import get_settings
from mcp_memoria.core.update_checker import check_for_updates, is_running_in_docker
from mcp_memoria.server import MemoriaServer


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="mcp-memoria",
        description="MCP Memoria - Unlimited local AI memory server",
    )
    parser.add_argument(
        "--version", action="version", version=f"mcp-memoria {__version__}"
    )
    parser.add_argument(
        "--skip-update-check",
        action="store_true",
        help="Skip checking for updates at startup",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update Memoria to the latest version and exit",
    )
    return parser.parse_args()


def do_update() -> None:
    """Run the update command (native only)."""
    if is_running_in_docker():
        print(
            "Running inside Docker. To update, run from the host:\n"
            "  docker compose pull && docker compose up -d",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Updating Memoria...", file=sys.stderr)
    try:
        subprocess.run(
            [
                sys.executable, "-m", "pip", "install", "--upgrade",
                "git+https://github.com/trapias/memoria.git",
            ],
            check=True,
        )
        print("Update complete.", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"Update failed: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    args = parse_args()

    if args.update:
        do_update()
        return

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
    logger.info(f"Starting MCP Memoria server v{__version__}...")
    logger.info(f"Qdrant path: {settings.qdrant_path}")
    logger.info(f"Ollama host: {settings.ollama_host}")
    logger.info(f"Embedding model: {settings.embedding_model}")

    # Non-blocking update check
    skip_check = args.skip_update_check or settings.skip_update_check
    if not skip_check:
        try:
            msg = asyncio.run(check_for_updates())
            if msg:
                logger.warning(msg)
        except Exception:
            pass  # Never let update check prevent startup

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
