"""Reading a decode's text: CQ and its type, who is calling whom, grid, report."""

from __future__ import annotations

import pytest

from jt_mcp.messages import read


@pytest.mark.parametrize("text, call, grid, cq_type, modifier", [
    ("CQ K1ABC FN42", "K1ABC", "FN42", "plain", None),
    ("CQ K1ABC", "K1ABC", None, "plain", None),
    ("CQ DX JA1ZZZ PM95", "JA1ZZZ", "PM95", "dx", "DX"),
    ("CQ POTA K1ABC FN42", "K1ABC", "FN42", "activity", "POTA"),
    ("CQ SOTA W7XYZ DN13", "W7XYZ", "DN13", "activity", "SOTA"),
    ("CQ TEST W1AW FN31", "W1AW", "FN31", "contest", "TEST"),
    ("CQ FD W1AW FN31", "W1AW", "FN31", "contest", "FD"),
    ("CQ NA VE3AAA FN03", "VE3AAA", "FN03", "region", "NA"),
    ("CQ 290 K1ABC FN42", "K1ABC", "FN42", "frequency", "290"),
    ("CQ ZZZ K1ABC FN42", "K1ABC", "FN42", "other", "ZZZ"),
    ("CQ PJ4/K1ABC", "PJ4/K1ABC", None, "plain", None),
    ("CQ <PJ4/K1ABC> FK52", "PJ4/K1ABC", "FK52", "plain", None),
])
def test_a_cq_is_read_with_its_type(text, call, grid, cq_type, modifier):
    r = read(text)
    assert (r.kind, r.from_call, r.grid, r.cq_type, r.cq_modifier) == (
        "cq", call, grid, cq_type, modifier)


def test_a_callsign_is_never_taken_for_a_modifier():
    # "K1ABC" fits no modifier pattern, but the rule that decides is that a modifier
    # needs a callsign after it: here the grid follows, so K1ABC is the caller.
    assert read("CQ K1ABC FN42").cq_modifier is None


@pytest.mark.parametrize("text, to_call, from_call, grid, report, signoff", [
    ("KI7MT W9XYZ EN37", "KI7MT", "W9XYZ", "EN37", None, None),
    ("KI7MT W9XYZ -12", "KI7MT", "W9XYZ", None, "-12", None),
    ("W9XYZ KI7MT R+05", "W9XYZ", "KI7MT", None, "R+05", None),
    ("KI7MT W9XYZ RR73", "KI7MT", "W9XYZ", None, None, "RR73"),
    ("KI7MT W9XYZ RRR", "KI7MT", "W9XYZ", None, None, "RRR"),
    ("KI7MT W9XYZ 73", "KI7MT", "W9XYZ", None, None, "73"),
    ("KI7MT W9XYZ", "KI7MT", "W9XYZ", None, None, None),
    ("<...> W9XYZ -12", None, "W9XYZ", None, "-12", None),
])
def test_a_directed_message_is_read(text, to_call, from_call, grid, report, signoff):
    r = read(text)
    assert (r.kind, r.to_call, r.from_call, r.grid, r.report, r.signoff) == (
        "directed", to_call, from_call, grid, report, signoff)


@pytest.mark.parametrize("text", [
    "", "TNX 73 GL", "CQ", "CQ DX", "CQ <...>", "HELLO WORLD FROM ME", "KI7MT W9XYZ QRZ?",
    "123 456", "CQ ' OR 1=1 --",
])
def test_anything_else_is_other_and_names_no_station(text):
    r = read(text)
    assert r.kind == "other"
    assert r.from_call is None and r.to_call is None
