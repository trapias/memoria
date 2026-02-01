"""
Entry point for running the REST API server.

Usage:
    python -m mcp_memoria.api
"""

import os
import uvicorn

from .app import create_app

if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", "8765"))
    host = os.environ.get("API_HOST", "0.0.0.0")

    app = create_app()
    uvicorn.run(app, host=host, port=port)
