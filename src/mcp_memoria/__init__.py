"""MCP Memoria - Unlimited local AI memory server."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mcp-memoria")
except PackageNotFoundError:
    __version__ = "0.0.0"

__author__ = "Alberto Velo"

from mcp_memoria.server import MemoriaServer

__all__ = ["MemoriaServer", "__version__"]
