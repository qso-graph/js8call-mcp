"""What the state keeps, and that everything keyed by a datagram's content is bounded."""

from __future__ import annotations

from qso_graph_lib.jt import protocol as p

from jt_mcp import state as st


def _decode(sender: str, message: str, ms: int = 45_000_000, snr: int = -10,
            df: int = 1200, is_new: bool = True) -> p.Message:
    return p.parse(p.decode(sender, p.Decode(is_new, ms, snr, 0.1, df, "~", message)))


def test_a_decode_takes_the_band_from_the_last_status():
    s = st.State()
    s.handle(p.parse(p.status("WSJT-X", p.Status(dial_hz=7_074_000, mode="FT8"))))
    s.handle(_decode("WSJT-X", "CQ K1ABC FN42"))
    d = s.decodes()[0]
    got = (d["band"], d["mode"], d["from_call"], d["cq_type"])
    assert got == ("40m", "FT8", "K1ABC", "plain")


def test_a_replayed_decode_is_kept_once():
    s = st.State()
    s.handle(_decode("WSJT-X", "CQ K1ABC FN42"))
    s.handle(_decode("WSJT-X", "CQ K1ABC FN42", is_new=False))  # sent again on Replay
    assert len(s.decodes()) == 1


def test_decodes_held_are_bounded(monkeypatch):
    monkeypatch.setattr(st, "MAX_DECODES", 5)
    s = st.State()
    for i in range(12):
        s.handle(_decode("WSJT-X", f"CQ K{i}ABC FN42", df=100 + i))
    held = s.decodes()
    assert len(held) == 5 and held[-1]["from_call"] == "K11ABC"


def test_instances_are_bounded_and_the_refusals_counted(monkeypatch):
    monkeypatch.setattr(st, "MAX_INSTANCES", 2)
    s = st.State()
    for i in range(5):
        s.handle(_decode(f"WSJT-X {i}", "CQ K1ABC FN42"))
    assert len(s.instances()) == 2
    assert s.counters()["instances_refused"] == 3


def test_stations_heard_are_bounded_and_say_so(monkeypatch):
    monkeypatch.setattr(st, "MAX_HEARD", 3)
    s = st.State()
    for i in range(6):
        s.handle(_decode("WSJT-X", f"CQ K{i}ABC FN42", df=100 + i), now=1000.0 + i)
    heard = {h.call for h in s.heard()}
    assert heard == {"K3ABC", "K4ABC", "K5ABC"}  # the longest ago made room
    assert s.counters()["heard_capped"] is True


def test_rejected_senders_are_bounded_and_the_total_exact():
    s = st.State()
    for i in range(st.MAX_REJECTED_SENDERS + 15):
        s.record_rejected_sender(f"10.0.0.{i}")
    r = s.counters()["rejected"]
    assert r["total"] == st.MAX_REJECTED_SENDERS + 15
    assert len(r["senders"]) == st.MAX_REJECTED_SENDERS
    assert r["more_not_listed"] is True


def test_a_decode_from_just_before_midnight_is_dated_the_day_before():
    # Received at 00:00:30 UTC on 2026-10-29, decoded at 23:59:45 the day before.
    received = 1_793_232_030.0  # 2026-10-29T00:00:30Z
    assert st._utc_of((23 * 3600 + 59 * 60 + 45) * 1000, received) == "2026-10-28T23:59:45Z"
    assert st._utc_of(15_000, received) == "2026-10-29T00:00:15Z"


def test_wspr_spots_are_kept():
    w = (p._header(p.MessageType.WSPR_DECODE, "WSJT-X").boolean(True).qtime(3_600_000)
         .i32(-21).f64(0.4).u64(10_140_123).i32(-1).utf8("K1ABC").utf8("FN42").i32(23)
         .boolean(False).bytes())
    s = st.State()
    s.handle(p.parse(w))
    spot = s.wspr()[0]
    assert (spot["call"], spot["grid"], spot["power_dbm"], spot["band"]) == (
        "K1ABC", "FN42", 23, "30m")
