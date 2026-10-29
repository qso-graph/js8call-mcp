"""Conformance with the Model Context Protocol, revision 2026-07-28.

We documented how to *publish* an MCP server in detail and never wrote down what makes
one *valid*, which is how missing ``isError`` and missing annotations reached every
server in the fleet.

**This server is a placeholder**, so most of what is worth asserting is the *reason* the
hints hold rather than the four values — anyone would guess those, and copied from
another server they would be right today and wrong after the build-out.

What is particular here, and is not in ``dxe-mcp``'s otherwise identical file:

* **``readOnlyHint`` is a promise about a transmitter, not about a file.** ``PLANNED``
  states it plainly: *"No write, no PTT, no transmit control — a permanent constraint,
  not a first-version limit."* For a reference server that hint means "writes no file";
  here it means the radio is never keyed. ``TestTheTransmitterIsNeverKeyed`` asserts it
  against the source, so the day a tool calls JS8Call's TX API the test fails rather
  than the hint quietly becoming a false promise about somebody's station.

* **``openWorldHint: false`` is correct today and is a judgement call tomorrow.** Nothing
  here connects to anything. When the build-out reaches JS8Call's API, a running JS8Call
  is another program whose decode stream we neither control nor can enumerate — which is
  how ``n1mm-mcp`` reasoned about N1MM's UDP broadcast and concluded ``true``.
  ``JS-C12`` fails when the first socket appears, which is the point at which somebody
  has to make that call deliberately.

Test IDs: JS-C01 onward.
"""

from __future__ import annotations

import asyncio

from fastmcp import Client

from jt_mcp import server

ANNOTATION_HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")

# What keying a radio looks like as *code*: the names a call would use, in JS8Call's
# API and in Hamlib underneath it. Identifiers only — see JS-C10 for why.
TRANSMIT = frozenset({
    "ptt", "set_ptt", "setptt", "transmit", "send_message", "sendmessage",
    "key_down", "keydown", "tx", "set_tx", "start_tx", "send_text",
})


def _tools() -> dict[str, object]:
    return {t.name: t for t in asyncio.run(server.mcp.list_tools())}


def _wire(tool: object) -> dict[str, object]:
    annotations = getattr(tool, "annotations", None)
    assert annotations is not None, "tool declares no annotations"
    return annotations.model_dump(by_alias=True, exclude_none=True)


def call(name: str, args: dict | None = None):
    async def go():
        async with Client(server.mcp) as c:
            return (await c.call_tool(name, args or {})).data
    return asyncio.run(go())


def _sources():
    import pathlib

    src = pathlib.Path(server.__file__).parent
    for py in src.rglob("*.py"):
        yield py, py.read_text()


class TestToolAnnotations:
    def test_every_tool_declares_all_four_hints(self) -> None:
        """JS-C01: the defaults are pessimistic, so silence is the wrong answer."""
        for name, tool in _tools().items():
            wire = _wire(tool)
            for hint in ANNOTATION_HINTS:
                assert hint in wire, f"{name} omits {hint}; got {sorted(wire)}"

    def test_the_values(self) -> None:
        """JS-C02: read-only, non-destructive, idempotent, closed-world."""
        for name, tool in _tools().items():
            wire = _wire(tool)
            assert wire["readOnlyHint"] is True, name
            assert wire["destructiveHint"] is False, name
            assert wire["idempotentHint"] is True, name
            assert wire["openWorldHint"] is False, name


class TestTheTransmitterIsNeverKeyed:
    """The reason `readOnlyHint: true` means more here than anywhere else in the fleet.

    `PLANNED` promises no write, no PTT and no transmit control, as a permanent
    constraint. A hint is a client UX affordance and never a security control, so this
    does not *enforce* anything — but a false one is worse than none, because a client
    may skip a confirmation on the strength of it, and what is at the other end is a
    transmitter and an operator's licence.
    """

    def test_nothing_in_the_package_can_key_a_radio(self) -> None:
        """JS-C10: read as code, because prose about PTT is not PTT.

        Reads identifiers out of the parse tree — the names a call would use — rather
        than searching text. The first version searched lines and flagged ``PLANNED``
        itself, the sentence that *promises* no PTT, because it contains the word. That
        is the same trap that caught the error-payload check in ``cq-zones-mcp``: a text
        search cannot tell a sentence about a thing from the thing.

        Command strings like ``TX.SEND`` are not checked here because they can only
        reach JS8Call down a socket, and ``JS-C12`` already fails on the first socket.
        """
        import ast

        offenders = []
        for py, text in _sources():
            for node in ast.walk(ast.parse(text)):
                name = None
                if isinstance(node, ast.Attribute):
                    name = node.attr
                elif isinstance(node, (ast.Name, ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.id if isinstance(node, ast.Name) else node.name
                if name and name.lower() in TRANSMIT:
                    offenders.append(f"{py.name}:{node.lineno}: {name}")
        assert not offenders, (
            "this package can transmit, so readOnlyHint: true is a false promise about "
            "a radio — and PLANNED calls the constraint permanent:\n" + "\n".join(offenders)
        )

    def test_the_promise_is_still_published(self) -> None:
        """JS-C11: the constraint is stated where a caller can read it.

        If the sentence is ever dropped from PLANNED, JS-C10 is still enforcing a rule
        nobody has written down any more. This fails first.
        """
        assert "No write, no PTT, no transmit control" in server.PLANNED
        assert "permanent constraint" in server.PLANNED


class TestTheHintsReasonHolds:
    def test_nothing_in_the_package_opens_a_socket(self) -> None:
        """JS-C12: `openWorldHint: false` depends on this, and only for now.

        When the build-out reaches JS8Call's API this fails, and that is the point:
        a running JS8Call is another program whose decode stream we neither control nor
        can enumerate, which is how n1mm-mcp reasoned about N1MM's UDP broadcast and
        concluded `openWorldHint: true`. Somebody has to decide, deliberately.
        """
        offenders = [
            f"{py.name}:{i}: {line.strip()}"
            for py, text in _sources()
            for i, line in enumerate(text.splitlines(), 1)
            if any(t in line for t in ("urlopen", "urllib", "http.client", "socket.",
                                       "requests.", "httpx."))
        ]
        assert not offenders, (
            "something here reaches the network: openWorldHint needs deciding (see "
            "n1mm-mcp), and an outbound HTTPS call needs certifi "
            "(qso-graph-devel#73):\n" + "\n".join(offenders)
        )

    def test_nothing_in_the_package_writes(self) -> None:
        """JS-C13: the ordinary half of `readOnlyHint: true`."""
        offenders = [
            f"{py.name}:{i}: {line.strip()}"
            for py, text in _sources()
            for i, line in enumerate(text.splitlines(), 1)
            if any(t in line for t in ("write_text(", ".write(", "mkdir("))
        ]
        assert not offenders, "something here writes:\n" + "\n".join(offenders)

    def test_there_is_still_only_the_one_tool(self) -> None:
        """JS-C14: a second tool must choose its own hints, not inherit these."""
        assert set(_tools()) == {"get_version_info"}


class TestNothingCanFail:
    def test_no_error_payload_anywhere_in_the_source(self) -> None:
        """JS-C20: issue #5 says "0 occurrences", and it is right.

        Reads the parse tree for a dict literal with an ``"error"`` key rather than
        searching text. There is no `isError` work in this repo because nothing here
        can refuse; this notices when the build-out adds the first thing that can.
        """
        import ast

        offenders = [
            f"{py.name}:{node.lineno}"
            for py, text in _sources()
            for node in ast.walk(ast.parse(text))
            if isinstance(node, ast.Dict)
            and any(isinstance(k, ast.Constant) and k.value == "error" for k in node.keys)
        ]
        assert not offenders, (
            "an error payload exists now, so this server needs the isError conversion "
            f"the rest of the fleet had: {offenders}"
        )


class TestItSaysItIsNotReady:
    def test_the_server_instructions_say_in_development(self) -> None:
        """JS-C30: the instructions are what a client reads before anything else."""
        instructions = server.mcp.instructions or ""
        assert "IN DEVELOPMENT" in instructions
        assert server.TRACKING in instructions

    def test_get_version_info_says_so_too(self) -> None:
        """JS-C31: and so does the one answer it can give."""
        info = call("get_version_info")
        assert info["service_name"] == "jt-mcp"
        assert info["service_version"]
        assert "in development" in info["status"]
        assert info["tracking"] == server.TRACKING
