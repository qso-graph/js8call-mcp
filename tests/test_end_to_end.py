"""qso-graph-sim plays WSJT-X's sample ALL.TXT, as WSJT-X's own messages, into a live
listener, and the tools answer from it. No radio, no WSJT-X."""

from __future__ import annotations

import socket
import time
from importlib.resources import files

from qso_graph_lib.jt import alltxt
from qso_graph_sim.player import Player, Station

from jt_mcp import server
from jt_mcp.listener import UDPListener
from jt_mcp.state import State

SAMPLE = files("qso_graph_lib.jt").joinpath("samples", "ALL-sample.TXT").read_text("utf-8")


def test_the_sample_played_by_qso_graph_sim(monkeypatch):
    s = State()
    lst = UDPListener(s, port=0)
    lst.start()
    monkeypatch.setattr(server, "_state", s)
    monkeypatch.setattr(server, "_listener", lst)
    log = alltxt.read(SAMPLE)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.bind(("127.0.0.1", 0))
    try:
        Player(sock=sender, target=("127.0.0.1", lst.bound_port), log=log,
               station=Station(sender="WSJT-X", call="KI7MT", grid="DN13"),
               speed=1000, say=lambda _line: None).run()
        # The player ends with Close; wait for it to land.
        deadline = time.time() + 5
        while time.time() < deadline and not s.counters()["by_kind"].get("CLOSE"):
            time.sleep(0.02)
    finally:
        sender.close()
        lst.stop()

    played = sum(len(c.decodes) for c in log.cycles)  # Tx lines are already left out
    d = server.jt_diagnostics()
    assert d["rejected"]["total"] == 0 and d["malformed"] == 0
    assert d["by_kind"]["DECODE"] == played
    assert server.jt_status()["instances"][0]["de_call"] == "KI7MT"
    assert server.jt_decodes(since_minutes=1440, limit=500)["total_matching"] == played
    assert server.jt_cq(since_minutes=1440)["count"] > 0
    assert server.jt_heard(since_minutes=1440)["total"] > 0
