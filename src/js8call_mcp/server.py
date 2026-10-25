"""js8call-mcp: JS8Call MCP server for HF messaging.

**This server is in development.** It registers one tool, `get_version_info`,
and does nothing else yet.

It is published so the name is held while the work is planned in the open
(qso-graph-devel#48) — PyPI does not reserve a name for a pending trusted
publisher, so a name is only held once something is actually published. Given
that, the honest thing to publish is a package that says what it is.
"""

from __future__ import annotations

import sys
from typing import Any

from fastmcp import FastMCP

from . import __version__

PLANNED = (
    "Read-only access to JS8Call's API: the decode stream, stations heard, message "
    "traffic and the propagation those imply. No write, no PTT, no transmit control "
    "— a permanent constraint, not a first-version limit."
)
TRACKING = "https://github.com/qso-graph/qso-graph-devel/issues/48"

mcp = FastMCP(
    "js8call-mcp",
    version=__version__,
    instructions=(
        "IN DEVELOPMENT — this server has no working tools yet, and calling it will "
        "not answer questions about " + 'JS8Call MCP server for HF messaging'.lower() + ". "
        "Planned: " + PLANNED + " Progress: " + TRACKING
    ),
)


# MCP 2026-07-28 tool annotations. The defaults are pessimistic — a tool that
# declares nothing is advertised as destructive, non-idempotent and open-world,
# and the specification tells a client it may keep a human in the loop for that.
#
# `readOnlyHint` carries more weight here than in the rest of this fleet. For a
# reference server it means "writes no file"; for this one it means **the
# transmitter is never keyed**. PLANNED states that as a permanent constraint
# rather than a first-version limit, and tests/test_mcp_conformance.py asserts
# it against the source, so the day a tool calls JS8Call's TX API the test fails
# rather than this hint quietly becoming a false promise about a radio.
#
# `openWorldHint: false` is correct today because nothing here connects to
# anything. When the build-out reaches JS8Call's API over the local network it
# becomes a judgement call — a running JS8Call is another program whose decode
# stream we neither control nor can enumerate, which is how n1mm-mcp reasoned
# about N1MM's UDP broadcast and concluded `true`.
_ANSWERS_FROM_THE_PACKAGE = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


@mcp.tool(annotations=_ANSWERS_FROM_THE_PACKAGE)
def get_version_info() -> dict[str, Any]:
    """Get this server's version and development status.

    Returns:
        service_name, service_version, status, what is planned, and where the
        work is tracked.
    """
    return {
        "service_name": "js8call-mcp",
        "service_version": __version__,
        "status": "in development — no working tools yet",
        "planned": PLANNED,
        "tracking": TRACKING,
    }


def main() -> None:
    """Run the server."""
    args = sys.argv[1:]
    transport, port = "stdio", 8031
    for i, arg in enumerate(args):
        if arg == "--transport" and i + 1 < len(args):
            transport = args[i + 1]
        if arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
    # Written out rather than passed through: fastmcp takes a literal, and a
    # str that happens to hold the right word is not the same thing.
    if transport == "streamable-http":
        mcp.run(transport="streamable-http", port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
