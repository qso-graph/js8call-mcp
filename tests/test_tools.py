"""The tools: what they answer from what WSJT-X sent, and what they refuse."""

from __future__ import annotations

import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from qso_graph_lib.jt import protocol as p

from jt_mcp import server
from jt_mcp.state import State


@pytest.fixture
def fed(monkeypatch) -> State:
    s = State()
    monkeypatch.setattr(server, "_state", s)
    s.handle(p.parse(p.heartbeat("WSJT-X", "2.7.0")))
    s.handle(p.parse(p.status("WSJT-X", p.Status(
        dial_hz=14_074_000, mode="FT8", dx_call="W9XYZ", dx_grid="EN37", tx_enabled=True,
        de_call="KI7MT", de_grid="DN13"))))
    for msg, snr, df in [
        ("CQ POTA K1ABC FN42", -5, 600), ("CQ W9XYZ EN37", -12, 900),
        ("KI7MT W9XYZ -12", -10, 900), ("CQ DX JA1ZZZ PM95", 3, 1500),
        ("CQ NA VE3AAA FN03", 1, 2100), ("TNX 73 GL", -20, 300),
    ]:
        d = p.Decode(True, 45_000_000, snr, 0.1, df, "~", msg)
        s.handle(p.parse(p.decode("WSJT-X", d)))
    return s


def call(name: str, args: dict | None = None):
    async def go():
        async with Client(server.mcp) as c:
            return (await c.call_tool(name, args or {})).data
    return asyncio.run(go())


def test_status(fed):
    inst = server.jt_status()["instances"][0]
    assert (inst["band"], inst["mode"], inst["dx_call"], inst["de_call"], inst["version"]) == (
        "20m", "FT8", "W9XYZ", "KI7MT", "2.7.0")
    assert inst["tx_enabled"] is True


def test_cq_lists_each_caller_once_with_its_type(fed):
    calls = {c["call"]: c["cq_type"] for c in server.jt_cq()["calls"]}
    assert calls == {"K1ABC": "activity", "W9XYZ": "plain", "JA1ZZZ": "dx", "VE3AAA": "region"}


@pytest.mark.parametrize("args, expect", [
    ({"cq_type": "activity"}, {"K1ABC"}),
    ({"modifier": "pota"}, {"K1ABC"}),
    ({"cq_type": "dx"}, {"JA1ZZZ"}),
    ({"band": "40m"}, set()),
])
def test_cq_filters(fed, args, expect):
    assert {c["call"] for c in server.jt_cq(**args)["calls"]} == expect


def test_decodes_for_a_callsign_cover_both_directions(fed):
    got = server.jt_decodes(callsign="w9xyz")["decodes"]
    assert {d["message"] for d in got} == {"CQ W9XYZ EN37", "KI7MT W9XYZ -12"}


def test_decodes_by_snr_and_cq_only(fed):
    strong = {d["from_call"] for d in server.jt_decodes(min_snr=0)["decodes"]}
    assert strong == {"JA1ZZZ", "VE3AAA"}
    assert all(d["kind"] == "cq" for d in server.jt_decodes(cq_only=True)["decodes"])


def test_heard_counts_a_station_each_time_it_is_heard(fed):
    w9 = server.jt_heard(callsign="W9XYZ")["stations"][0]
    assert (w9["count"], w9["last_grid"], w9["last_band"]) == (2, "EN37", "20m")


def test_nothing_received_says_where_to_look(monkeypatch):
    monkeypatch.setattr(server, "_state", State())
    assert "UDP Server" in server.jt_cq()["note"]
    assert server.jt_status()["instances"] == []


@pytest.mark.parametrize("tool, args", [
    ("jt_decodes", {"callsign": "K1ABC; DROP"}),
    ("jt_decodes", {"limit": 0}),
    ("jt_decodes", {"min_snr": 99}),
    ("jt_cq", {"cq_type": "everything"}),
    ("jt_cq", {"modifier": "POTA!"}),
    ("jt_cq", {"since_minutes": 5000}),
    ("jt_heard", {"sort": "random"}),
    ("jt_wspr", {"limit": 501}),
])
def test_bad_input_is_a_tool_error_the_model_can_see(fed, tool, args):
    """isError: true, per the MCP spec, so the model can correct itself."""
    with pytest.raises(ToolError):
        call(tool, args)
