"""
Memoria REST API module.

Provides HTTP endpoints for the Web UI to interact with memories and the knowledge graph.
"""

from .app import create_app

__all__ = ["create_app"]
