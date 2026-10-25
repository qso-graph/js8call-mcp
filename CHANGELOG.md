# Changelog

All notable changes to `js8call-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
