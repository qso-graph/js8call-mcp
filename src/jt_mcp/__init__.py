"""jt-mcp — JS8Call MCP server for HF messaging."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("jt-mcp")
except PackageNotFoundError:  # a source tree without an install
    __version__ = "0.0.0"
