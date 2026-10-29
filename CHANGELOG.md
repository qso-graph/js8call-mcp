# Changelog

All notable changes to `jt-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **A WSJT-X listener, and the first working tools.** WSJT-X's UDP Server
  messages, decoded by `qso-graph-lib` (`qso_graph_lib.jt`), the code
  qso-graph-sim plays them with:
  - `jt_cq`: who is calling CQ, and what kind (plain, DX, activity such as
    POTA or SOTA, contest, region, frequency), the latest per station.
  - `jt_status`: dial frequency and band, mode, DX call and grid, Tx enabled
    or transmitting, your call and grid, per WSJT-X instance.
  - `jt_decodes`: recent decodes, each read into who is calling whom, grid,
    report and sign-off, filtered by callsign, CQ, SNR or band.
  - `jt_heard`, `jt_wspr`, and `jt_diagnostics` for the listener itself.
- **The listener follows the fleet's "Servers that listen" rule**
  (QGD-INT-0005/0006): 127.0.0.1 by default, every interface refused, `--allow`
  required on a network address, names refused, a sender not on the list
  dropped unread, counted and shown, and everything keyed by what a datagram
  says capped. Each rule has a test, and the sender check was removed once to
  prove the tests fail without it.
- **Still read-only**: nothing in the package sends a datagram, so WSJT-X's
  Reply, Halt Tx and Free Text cannot be sent from here, and the conformance
  test asserts it. `openWorldHint` is `true` for the tools that read WSJT-X.

### Changed

- **Renamed from `js8call-mcp` to `jt-mcp`, and the scope is the JT family.**
  WSJT-X, JTDX, WSJT-Z, MSHV and JS8Call share one UDP protocol and would have
  meant one listener each across several servers. One server covers them.

  **WSJT-X is first, and it defines the protocol** (KI7MT, 2026-10-29): the
  message definitions come from the WSJT-X project, `Network/NetworkMessage.hpp`
  at the schema WSJT-X states, because the project that owns a definition is its
  authority. A variant is supported where it works with those definitions; where
  it does not, its difference is not implemented here.

  The GitHub repository redirects from the old name. On PyPI, `js8call-mcp`
  cannot be renamed: its six releases are **yanked** (2026-10-29), so nothing
  installs it unless pinned, and the project is kept rather than deleted, because
  a deleted PyPI name can be registered by anyone and the MCP Registry and old
  configurations still name it. `jt-mcp` is a new project; nothing depended on
  the old one beyond `get_version_info`. Its first release is 0.2.0, because
  this repository's history already holds `v0.1.0`.

## [0.1.0] — 2026-10-26

### Changed

- **Python 3.11 is the minimum.** 3.10 reached end of life in October 2026
  ([PEP 619](https://peps.python.org/pep-0619/)), so it gets no further security
  releases on any platform. On Windows it was worse than unsupported: `uv`'s 3.10
  is built against OpenSSL 1.1.1w, end of life since September 2023, so HTTPS
  from this server ran over an unmaintained TLS library. `certifi` does not help
  with that — it supplies the root store, not the implementation.

  3.10 support was already nominal. This package has linted with
  `ruff target-version = "py311"` and type-checked with `mypy python_version =
  "3.11"` for some time, so nothing ever verified the 3.10 claim.

  `uv.lock` is regenerated and the diff is large, but **nothing is upgraded** —
  it is the 3.10 resolution branch disappearing. Packages that carried two pins,
  one per Python branch, now carry the single 3.11+ pin they already resolved to.
  An install on 3.11 or later is unchanged.

## [0.0.5] — 2026-10-26

### Changed

- `--transport streamable-http` now says where it bound, and the help text says
  it too. It binds `127.0.0.1`, and FastMCP takes no host option, so it was
  never reachable from another machine or from outside a container — and nothing
  said so. The bind address is unchanged: loopback-only is deliberate for a
  server that holds credentials and has no authentication of its own.

## [0.0.4] — 2026-10-26

### Fixed

- `--version` and `--help` now print and exit. They were ignored, so the
  command started the MCP server on stdio and waited for JSON-RPC — leaving a
  FastMCP banner on screen and an apparently hung terminal. Seven servers in
  this fleet already behaved correctly; this brings the rest in line, and a
  test asserts it.

## [0.0.3] — 2026-10-26

- Move every Node 20 action to its first Node 24 major
- The locked-dependency audit blocked every release
- Four upgrades arrived as 57 pull requests
- Nothing was auditing the lockfile
- Close every open security advisory in the lockfile
- A release is a workflow, not a merge

## [0.0.2] — 2026-10-25

### MCP specification 2026-07-28 (#5)

- **The one tool declares the four annotation hints.** Omitting them advertises it as
  `destructiveHint: true`, `idempotentHint: false`, `openWorldHint: true`.
- **There is no `isError` work, and the issue says so correctly** — "0 occurrences" of error
  payloads in `src/`, because nothing here can refuse yet.
- **`readOnlyHint` means more here than anywhere else in this fleet.** For a reference server it
  means "writes no file". Here `PLANNED` promises *"No write, no PTT, no transmit control — a
  permanent constraint, not a first-version limit"*, so the hint is a promise about a
  **transmitter**. A hint is a client UX affordance and never a security control, but a false one
  is worse than none: a client may skip a confirmation on the strength of it, and what is at the
  other end is a radio and an operator's licence. `JS-C10` asserts it against the code and `JS-C11`
  asserts the promise is still published, so dropping the sentence fails before the rule becomes
  unwritten.
- **`JS-C10` reads identifiers from the parse tree, because prose about PTT is not PTT.** The first
  version searched lines and flagged `PLANNED` itself — the sentence that promises no PTT, because
  it contains the word. Same trap as the error-payload check in `cq-zones-mcp`. It is falsified
  both ways: a planted `rig.set_ptt(1)` is caught, and a planted sentence mentioning PTT is not.
- **`openWorldHint: false` is right today and a judgement call tomorrow.** `JS-C12` fails on the
  first socket — which is when somebody must decide, because a running JS8Call is another program
  whose decode stream we neither control nor can enumerate, and that is how `n1mm-mcp` reasoned
  about N1MM's UDP broadcast and concluded `true`.
- `tests/test_mcp_conformance.py` (JS-C01 onward). Every check falsified — **10 of 10** — with a
  control proving the prose case is not a false positive.

### Lint (#4)

- **`E501` is adopted.** One line, the `PLANNED` string, not a defect; it reflows as adjacent
  literals so the published value is **byte-identical**.
- The publisher-name exemption the issue was filed for does not apply: this server names no
  publisher's field. Zero exemptions, no `# noqa: E501`.

### Not applicable here

- **No `certifi` work and no issue for it** (qso-graph-devel#73): no outbound call of any kind in
  `src/`. `JS-C12` names `certifi` in its failure message, for the build-out.

## [0.0.1] — 2026-10-11

- Placeholder release so the name is held on PyPI while the work is planned
  (qso-graph-devel#48). A pending trusted publisher does **not** reserve a name —
  PyPI's documentation is explicit that a name is held only once something is actually
  published — so this is a real, installable package rather than an empty repository.
- One tool, `get_version_info`, reporting the development status, what is planned, and
  where the work is tracked. The server's instructions say the same, so a client listing
  it sees the truth before calling anything.
