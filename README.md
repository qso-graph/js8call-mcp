<!-- mcp-name: io.github.qso-graph/js8call-mcp -->
# js8call-mcp

[![PyPI](https://img.shields.io/pypi/v/js8call-mcp?label=PyPI&color=blue)](https://pypi.org/project/js8call-mcp/)

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

Read-only access to JS8Call's API: the decode stream, stations heard, message traffic and the propagation those imply. No write, no PTT, no transmit control — a permanent constraint, not a first-version limit.

Planned work, including the data sources it would use and whether each is actually
available, is tracked in
[qso-graph-devel#48](https://github.com/qso-graph/qso-graph-devel/issues/48).

Part of the [qso-graph](https://qso-graph.io/) project.

## Install

```bash
uvx js8call-mcp            # run it; nothing to install
```

## Tools

| Tool | Description |
|------|-------------|
| `get_version_info` | Service version, development status, and where the work is tracked |

## Quick Start

No credentials needed — install and configure your MCP client.

### Configure your MCP client

js8call-mcp works with any MCP-compatible client. Add the server config and restart.

#### Claude Desktop

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on macOS,
`%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "js8call": {
      "command": "uvx",
      "args": ["js8call-mcp"]
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
      "args": ["js8call-mcp"]
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
      "args": ["js8call-mcp"]
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
