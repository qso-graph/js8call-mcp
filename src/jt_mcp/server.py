"""jt-mcp: the JT-mode programs' UDP messages, for an AI app. WSJT-X first.

WSJT-X sends what it is doing and every decode to a UDP Server address (Settings,
Reporting). This server listens there and answers questions about it: what WSJT-X
is tuned to, who is calling CQ, who has been heard, recent decodes, WSPR spots,
and the listener's own health.

Read-only, permanently: nothing here sends WSJT-X a message, so nothing here can
answer a call, key the transmitter or change a setting.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from . import __version__
from .listener import DEFAULT_PORT, UDPListener, resolve_listener
from .messages import CQ_TYPES
from .state import State
from .state import band as band_of

PLANNED = (
    "Read-only access to the JT-mode programs' UDP messages, WSJT-X first: what WSJT-X "
    "is doing, the decode stream, who is calling CQ, stations heard, and WSPR spots. "
    "No write, no PTT, no transmit control — a permanent constraint, not a "
    "first-version limit."
)
TRACKING = "https://github.com/qso-graph/jt-mcp/milestones"

mcp = FastMCP(
    "jt-mcp",
    version=__version__,
    instructions=(
        "Live WSJT-X data over its UDP Server: what it is tuned to (jt_status), who is "
        "calling CQ and what kind of CQ (jt_cq), stations heard (jt_heard), recent decodes "
        "(jt_decodes), WSPR spots (jt_wspr), and the listener's health (jt_diagnostics). "
        "Times are UTC. If a tool says nothing has been received, WSJT-X is not sending "
        "here: jt_diagnostics says where this server listens. Read-only: it never "
        "answers a call or keys a transmitter."
    ),
)

# The package's own facts, answered without WSJT-X.
_ANSWERS_FROM_THE_PACKAGE = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}
# What a running WSJT-X has sent. Read-only — and here that means the transmitter is
# never keyed, which tests/test_mcp_conformance.py asserts against the source.
# `openWorldHint: true`: WSJT-X is another program whose decode stream we neither
# control nor can enumerate, which is how n1mm-mcp reasoned about N1MM's broadcast.
_READS_WSJTX = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

_state = State()
_listener: UDPListener | None = None

_CALL = re.compile(r"^[A-Z0-9/]{1,13}$")
_MODIFIER = re.compile(r"^(?:[0-9]{3}|[A-Z]{1,4})$")
_NOTHING_YET = (
    "Nothing received from WSJT-X yet. In WSJT-X, Settings, Reporting, UDP Server must "
    "name the address and port jt_diagnostics shows."
)


# --------------------------------------------------------------- validation

def _callsign(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    call = value.strip().upper()
    if not _CALL.match(call):
        raise ToolError(f"callsign {value!r}: letters, digits and / only, 13 at most")
    return call


def _bounded(name: str, value: int, low: int, high: int) -> int:
    if not low <= value <= high:
        raise ToolError(f"{name} must be between {low} and {high}, not {value}")
    return value


def _instance(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    if len(value) > 256:
        raise ToolError("instance: 256 characters at most")
    return value


def _age(at: float | None, now: float) -> float | None:
    return None if at is None else round(now - at, 1)


def _public(record: dict[str, Any], now: float) -> dict[str, Any]:
    out = {k: v for k, v in record.items() if k != "received"}
    out["age_seconds"] = _age(record["received"], now)
    return out


def _received_anything() -> bool:
    return bool(_state.counters()["received"] > 0)


# --------------------------------------------------------------- tools

@mcp.tool(annotations=_ANSWERS_FROM_THE_PACKAGE)
def get_version_info() -> dict[str, Any]:
    """Get this server's version, what it does, and where its work is tracked.

    Returns:
        service_name, service_version, status, what it does, and the milestones.
    """
    return {
        "service_name": "jt-mcp",
        "service_version": __version__,
        "status": "WSJT-X listener: status, decodes, CQ, heard, WSPR, diagnostics",
        "planned": PLANNED,
        "tracking": TRACKING,
    }


@mcp.tool(annotations=_READS_WSJTX)
def jt_status(instance: str | None = None) -> dict[str, Any]:
    """What each running WSJT-X is doing now: dial frequency and band, mode, the station
    being worked (DX call and grid), whether Tx is enabled or transmitting, and your own
    call and grid.

    Args:
        instance: one WSJT-X by the Id it sends (e.g. "WSJT-X - FT-991A"); every one
            if left out.

    Returns:
        instances: one entry per WSJT-X heard, with its last Status and how old it is.
    """
    wanted = _instance(instance)
    now = time.time()
    out = []
    for inst in _state.instances():
        if wanted and inst.id != wanted:
            continue
        s = dict(inst.status or {})
        out.append({
            "instance": inst.id,
            "version": inst.version,
            "schema": inst.schema,
            "closed": inst.closed_at is not None,
            "status_age_seconds": _age(inst.status_at, now),
            "heartbeat_age_seconds": _age(inst.last_heartbeat, now),
            "band": band_of(s.get("dial_hz")),
            **s,
        })
    result: dict[str, Any] = {"instances": out}
    if not out:
        result["note"] = _NOTHING_YET if not _received_anything() else (
            f"no WSJT-X instance named {wanted!r}" if wanted else "no Status received yet"
        )
    return result


@mcp.tool(annotations=_READS_WSJTX)
def jt_cq(
    cq_type: str | None = None,
    modifier: str | None = None,
    band: str | None = None,
    since_minutes: int = 5,
    instance: str | None = None,
) -> dict[str, Any]:
    """Who is calling CQ, and what kind of CQ: plain, DX, an activity (POTA, SOTA, WWFF,
    IOTA), a contest (TEST, FD, RU, WW), a region (NA, EU, ...), or a frequency (CQ 290).
    The latest CQ per station, newest first.

    Args:
        cq_type: one of plain, dx, activity, contest, region, frequency, other.
        modifier: the exact word after CQ, e.g. "POTA" or "NA".
        band: e.g. "20m".
        since_minutes: how far back, 1 to 1440 (default 5).
        instance: one WSJT-X by its Id; every one if left out.

    Returns:
        calls: call, grid, cq_type, cq_modifier, snr, df, mode, band, dial_hz, utc,
        age_seconds, instance.
    """
    if cq_type is not None and cq_type not in CQ_TYPES:
        raise ToolError(f"cq_type must be one of {', '.join(CQ_TYPES)}")
    mod = modifier.strip().upper() if modifier and modifier.strip() else None
    if mod is not None and not _MODIFIER.match(mod):
        raise ToolError("modifier: three digits, or one to four letters (e.g. POTA, DX, NA)")
    _bounded("since_minutes", since_minutes, 1, 1440)
    wanted = _instance(instance)
    now = time.time()
    latest: dict[str, dict[str, Any]] = {}
    for d in _state.decodes():
        if d.get("kind") != "cq" or now - d["received"] > since_minutes * 60:
            continue
        if (cq_type and d.get("cq_type") != cq_type) or (mod and d.get("cq_modifier") != mod):
            continue
        if (band and d.get("band") != band) or (wanted and d["instance"] != wanted):
            continue
        latest[d["from_call"]] = d
    calls = sorted(latest.values(), key=lambda d: d["received"], reverse=True)
    result: dict[str, Any] = {
        "since_minutes": since_minutes,
        "count": len(calls),
        "calls": [
            {
                "call": d["from_call"], "grid": d.get("grid"), "cq_type": d.get("cq_type"),
                "cq_modifier": d.get("cq_modifier"), "snr": d["snr"], "df": d["df"],
                "mode": d["mode"], "band": d["band"], "dial_hz": d["dial_hz"], "utc": d["utc"],
                "age_seconds": _age(d["received"], now), "instance": d["instance"],
            }
            for d in calls
        ],
    }
    if not _received_anything():
        result["note"] = _NOTHING_YET
    return result


@mcp.tool(annotations=_READS_WSJTX)
def jt_decodes(
    callsign: str | None = None,
    cq_only: bool = False,
    min_snr: int | None = None,
    band: str | None = None,
    since_minutes: int = 15,
    limit: int = 50,
    instance: str | None = None,
) -> dict[str, Any]:
    """Recent decodes, newest first, each read into its parts: CQ (with its type), or
    who is calling whom, with the grid, report or sign-off it carries.

    Args:
        callsign: decodes sent by or to this call.
        cq_only: CQ calls only.
        min_snr: this SNR in dB or better (-50 to 50).
        band: e.g. "20m".
        since_minutes: how far back, 1 to 1440 (default 15).
        limit: at most this many, 1 to 500 (default 50).
        instance: one WSJT-X by its Id; every one if left out.

    Returns:
        decodes: utc, age_seconds, snr, dt, df, mode, band, message, kind, from_call,
        to_call, grid, report, signoff, cq_type, cq_modifier, instance; total_matching.
    """
    call = _callsign(callsign)
    if min_snr is not None:
        _bounded("min_snr", min_snr, -50, 50)
    _bounded("since_minutes", since_minutes, 1, 1440)
    _bounded("limit", limit, 1, 500)
    wanted = _instance(instance)
    now = time.time()
    matched = []
    for d in reversed(_state.decodes()):
        if now - d["received"] > since_minutes * 60:
            break
        if call and call not in (d.get("from_call"), d.get("to_call")):
            continue
        if cq_only and d.get("kind") != "cq":
            continue
        if min_snr is not None and (d["snr"] is None or d["snr"] < min_snr):
            continue
        if (band and d.get("band") != band) or (wanted and d["instance"] != wanted):
            continue
        matched.append(d)
    result: dict[str, Any] = {
        "since_minutes": since_minutes,
        "total_matching": len(matched),
        "decodes": [_public(d, now) for d in matched[:limit]],
    }
    if not _received_anything():
        result["note"] = _NOTHING_YET
    return result


@mcp.tool(annotations=_READS_WSJTX)
def jt_heard(
    callsign: str | None = None,
    sort: str = "last_heard",
    since_minutes: int = 60,
    limit: int = 50,
) -> dict[str, Any]:
    """Stations heard since this server started: how often, last SNR, last grid sent,
    mode and band, first and last heard.

    Args:
        callsign: one station only.
        sort: last_heard (default), snr or count.
        since_minutes: heard within this many minutes, 1 to 1440 (default 60).
        limit: at most this many, 1 to 500 (default 50).

    Returns:
        stations: call, count, last_snr, last_grid, last_mode, last_band,
        first_heard_utc, last_heard_utc, age_seconds; partial is true when the
        oldest stations were dropped to stay within the cap.
    """
    call = _callsign(callsign)
    if sort not in ("last_heard", "snr", "count"):
        raise ToolError("sort must be last_heard, snr or count")
    _bounded("since_minutes", since_minutes, 1, 1440)
    _bounded("limit", limit, 1, 500)
    now = time.time()
    rows = [
        h for h in _state.heard()
        if now - h.last_heard <= since_minutes * 60 and (not call or h.call == call)
    ]
    key = {"last_heard": lambda h: h.last_heard, "snr": lambda h: h.last_snr,
           "count": lambda h: h.count}[sort]
    rows.sort(key=key, reverse=True)

    def utc(t: float) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))

    result: dict[str, Any] = {
        "since_minutes": since_minutes,
        "total": len(rows),
        "partial": _state.counters()["heard_capped"],
        "stations": [
            {"call": h.call, "count": h.count, "last_snr": h.last_snr,
             "last_grid": h.last_grid, "last_mode": h.last_mode, "last_band": h.last_band,
             "first_heard_utc": utc(h.first_heard), "last_heard_utc": utc(h.last_heard),
             "age_seconds": _age(h.last_heard, now)}
            for h in rows[:limit]
        ],
    }
    if not _received_anything():
        result["note"] = _NOTHING_YET
    return result


@mcp.tool(annotations=_READS_WSJTX)
def jt_wspr(
    callsign: str | None = None,
    band: str | None = None,
    since_minutes: int = 60,
    limit: int = 50,
) -> dict[str, Any]:
    """WSPR spots WSJT-X has decoded, newest first: call, grid, power, SNR, drift.

    Args:
        callsign: one station only.
        band: e.g. "30m".
        since_minutes: how far back, 1 to 1440 (default 60).
        limit: at most this many, 1 to 500 (default 50).

    Returns:
        spots: utc, age_seconds, call, grid, power_dbm, snr, dt, drift_hz,
        frequency_hz, band, instance; total_matching.
    """
    call = _callsign(callsign)
    _bounded("since_minutes", since_minutes, 1, 1440)
    _bounded("limit", limit, 1, 500)
    now = time.time()
    matched = [
        s for s in reversed(_state.wspr())
        if now - s["received"] <= since_minutes * 60
        and (not call or (s.get("call") or "").upper() == call)
        and (not band or s.get("band") == band)
    ]
    result: dict[str, Any] = {
        "since_minutes": since_minutes,
        "total_matching": len(matched),
        "spots": [_public(s, now) for s in matched[:limit]],
    }
    if not _received_anything():
        result["note"] = _NOTHING_YET
    return result


@mcp.tool(annotations=_READS_WSJTX)
def jt_diagnostics() -> dict[str, Any]:
    """The listener itself: where it listens, who may send, what has arrived, what was
    dropped and from where, and each WSJT-X instance's version and last heartbeat.

    Returns:
        listening (address, port, allowed_senders, bind_error), received, malformed,
        by_kind, rejected (total, senders, more_not_listed), instances,
        instances_refused, uptime_seconds, and what the sender list does not do.
    """
    now = time.time()
    c = _state.counters()
    lst = _listener
    return {
        "listening": {
            "address": lst.bind_addr if lst else None,
            "port": (lst.bound_port or lst.port) if lst else None,
            "allowed_senders": sorted(lst.allowed_senders) if lst else [],
            "bind_error": lst.error if lst else "the listener has not been started",
        },
        "received": c["received"],
        "malformed": c["malformed"],
        "by_kind": c["by_kind"],
        "last_received_age_seconds": _age(c["last_received"], now),
        "rejected": c["rejected"],
        "instances": [
            {"instance": i.id, "version": i.version, "revision": i.revision,
             "schema": i.schema, "max_schema": i.max_schema, "decodes_held": len(i.decodes),
             "heartbeat_age_seconds": _age(i.last_heartbeat, now),
             "closed": i.closed_at is not None}
            for i in _state.instances()
        ],
        "instances_refused": c["instances_refused"],
        "uptime_seconds": round(now - _state.started, 1),
        "sender_list": (
            "keeps other machines out; it is not proof of who sent, because a UDP source "
            "address can be forged on the same network. This server only reads, so a "
            "forged datagram can mislead about WSJT-X and cannot make anything happen."
        ),
    }


# --------------------------------------------------------------- command line

USAGE = """\
usage: jt-mcp [--bind ADDR] [--allow ADDR ...] [--udp-port N]
              [--transport stdio|streamable-http] [--port N] [--version] [--help]

An MCP server: an AI app (Claude Desktop, Claude Code, ...) starts it and talks
to it over stdio. Run on its own it waits for that app; press Ctrl-C to stop.
Set up a client: https://github.com/qso-graph/jt-mcp#quick-start

It listens for WSJT-X's UDP Server messages (WSJT-X: Settings, Reporting).
  --bind ADDR     where to listen (default 127.0.0.1: WSJT-X on this PC). For
                  WSJT-X on another PC, one address of THIS PC, with --allow.
                  Every interface at once (0.0.0.0) is refused.
  --allow ADDR    a PC that may send; repeatable; required with a network --bind.
                  Anything else is dropped unread and counted (jt_diagnostics).
  --udp-port N    WSJT-X's UDP Server port (default 2237).

streamable-http binds 127.0.0.1 only: not another machine,
not a container.
"""


def _parse(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="jt-mcp", add_help=False)
    p.add_argument("--bind", default="127.0.0.1")
    p.add_argument("--allow", action="append")
    p.add_argument("--udp-port", type=int, default=DEFAULT_PORT)
    p.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http"])
    p.add_argument("--port", type=int, default=8031)
    return p.parse_args(argv)


def main() -> None:
    """Run the server."""
    global _listener
    argv = sys.argv[1:]
    if any(a in ("-h", "--help") for a in argv):
        print(USAGE, end="")
        return
    if "--version" in argv:
        print(f"jt-mcp {__version__}")
        return
    args = _parse(argv)
    # Before a socket: a refusal leaves nothing started and says what to run instead.
    try:
        bind_addr, allowed = resolve_listener(args.bind, args.allow)
        if not 1 <= args.udp_port <= 65_535:
            raise ValueError(f"--udp-port {args.udp_port} is not a port (1 to 65535)")
    except ValueError as e:
        print(f"jt-mcp: {e}", file=sys.stderr)
        raise SystemExit(2) from None

    _listener = UDPListener(_state, args.udp_port, bind_addr, allowed)
    _listener.start()
    try:
        if args.transport == "streamable-http":
            print(f"jt-mcp on http://127.0.0.1:{args.port}/mcp - loopback only",
                  file=sys.stderr)
            mcp.run(transport="streamable-http", port=args.port)
        else:
            mcp.run(transport="stdio")
    finally:
        _listener.stop()


if __name__ == "__main__":
    main()
