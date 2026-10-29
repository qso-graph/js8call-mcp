<!-- mcp-name: io.github.qso-graph/jt-mcp -->
# jt-mcp

[![PyPI](https://img.shields.io/pypi/v/jt-mcp?label=PyPI&color=blue)](https://pypi.org/project/jt-mcp/)

> ### In development
>
> This package is published so the name is held while the work is planned in the open.
> It registers one tool, `get_version_info`, and **does nothing else yet**. If you install
> it expecting a working server, that is what you will find — which is why it says so
> here, in the server's own instructions, and in the one tool it has.
>
> PyPI does not reserve a name for a pending trusted publisher, so a name is only held
> once something is actually published. Given that, a package that says what it is beats
> an empty one that does not.

Read-only access to the JT-mode programs' UDP messages: the decode stream, stations heard, and the propagation those imply. No write, no PTT, no transmit control — a permanent constraint, not a first-version limit.

**WSJT-X first, and WSJT-X defines the protocol.** The UDP message definitions come from
the WSJT-X project — `Network/NetworkMessage.hpp`, at the schema WSJT-X states — because
the project that owns a definition is its authority. JTDX, WSJT-Z, MSHV and JS8Call are
forks of, or deliberate reimplementations of, that protocol; each is supported where it
works with those definitions, and where one does not, its difference is not implemented
here. Message types and fields beyond the schema are ignored, which that protocol already
requires of a conforming client.

This server was `js8call-mcp` until 2026-10-29. One server covers the family because they
share one protocol and one listener; JS8Call remains in scope, after WSJT-X.

Planned work, including the data sources it would use and whether each is actually
available, is tracked in
[qso-graph-devel#48](https://github.com/qso-graph/qso-graph-devel/issues/48).

Part of the [qso-graph](https://qso-graph.io/) project.

## Install

```bash
uvx jt-mcp            # run it; nothing to install
```

## Tools

| Tool | Description |
|------|-------------|
| `get_version_info` | Service version, development status, and where the work is tracked |

## Quick Start

No credentials needed — install and configure your MCP client.

### Configure your MCP client

jt-mcp works with any MCP-compatible client. Add the server config and restart.

#### Claude Desktop

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on macOS,
`%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "js8call": {
      "command": "uvx",
      "args": ["jt-mcp"]
    }
  }
}
```

#### Claude Code

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "js8call": {
      "command": "uvx",
      "args": ["jt-mcp"]
    }
  }
}
```

#### ChatGPT Desktop

Configure via Settings > Apps & Connectors, or in your agent definition:

```json
{
  "mcpServers": {
    "js8call": {
      "command": "uvx",
      "args": ["jt-mcp"]
    }
  }
}
```

### Questions it will answer

Not yet — these are what the finished server is for:

> "Who has JS8Call heard on 40m in the last hour?"

> "What message traffic has come through for my callsign?"

> "Which stations are relaying, and how far away are they?"

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).
