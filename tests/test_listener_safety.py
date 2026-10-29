"""The "Servers that listen" rules (MCP-SECURITY-FRAMEWORK), each with its planted case.

Rule 9: a sender not on the list must be shown to be dropped, and the same datagram
from an allowed sender shown to still work. A check that drops everything is not a check.
"""

from __future__ import annotations

import socket
import time

import pytest
from qso_graph_lib.jt import protocol as p

from jt_mcp import server
from jt_mcp.listener import UDPListener, resolve_listener
from jt_mcp.state import State

CQ = p.decode("WSJT-X", p.Decode(True, 45_000_000, -10, 0.1, 1200, "~", "CQ K1ABC FN42"))


def test_the_default_is_this_computer_alone():
    assert resolve_listener("127.0.0.1", None) == ("127.0.0.1", frozenset({"127.0.0.1"}))
    assert UDPListener(State()).bind_addr == "127.0.0.1"


@pytest.mark.parametrize("bind", ["0.0.0.0", "::", "0", "*", ""])
def test_every_interface_at_once_is_refused(bind):
    with pytest.raises(ValueError, match="every network interface"):
        resolve_listener(bind, ["192.168.1.40"])


def test_a_network_bind_without_allow_is_refused():
    with pytest.raises(ValueError, match="--allow is required"):
        resolve_listener("192.168.1.50", None)


def test_a_network_bind_accepts_only_the_named_senders():
    assert resolve_listener("192.168.1.50", ["192.168.1.40"]) == (
        "192.168.1.50", frozenset({"192.168.1.40"}))


@pytest.mark.parametrize("name", ["wsjtx-pc.local", "localhost.example", "pc"])
def test_a_name_is_not_accepted_as_an_allowed_sender(name):
    with pytest.raises(ValueError, match="Names are not accepted"):
        resolve_listener("192.168.1.50", [name])


def test_an_empty_allow_list_is_refused_rather_than_accepting_nothing():
    with pytest.raises(ValueError):
        UDPListener(State(), allowed_senders=frozenset())


def test_a_sender_not_on_the_list_is_dropped_unread_and_not_counted_as_received():
    s = State()
    lst = UDPListener(s, allowed_senders=frozenset({"127.0.0.1"}))
    lst.receive(CQ, "192.168.1.99")
    c = s.counters()
    assert c["received"] == 0 and s.decodes() == []
    assert c["rejected"]["total"] == 1 and c["rejected"]["senders"] == ["192.168.1.99"]


def test_the_same_datagram_from_an_allowed_sender_is_processed():
    s = State()
    UDPListener(s, allowed_senders=frozenset({"127.0.0.1"})).receive(CQ, "127.0.0.1")
    assert s.counters()["received"] == 1
    assert s.decodes()[0]["from_call"] == "K1ABC"


def test_a_malformed_datagram_is_counted_and_holds_nothing():
    s = State()
    UDPListener(s).receive(b"\xad\xbc\xcb\xda\x00\x00", "127.0.0.1")
    assert s.counters()["malformed"] == 1 and s.decodes() == []


def test_over_a_real_socket_the_sender_address_decides(monkeypatch):
    """The whole path, recvfrom included: allowed from 127.0.0.1, refused when the list
    names someone else."""
    cases = ((frozenset({"127.0.0.1"}), 1), (frozenset({"10.9.9.9"}), 0))
    for allowed, expect_decodes in cases:
        s = State()
        lst = UDPListener(s, port=0, allowed_senders=allowed)
        lst.start()
        try:
            out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            out.sendto(CQ, ("127.0.0.1", lst.bound_port))
            out.close()
            deadline = time.time() + 3
            while time.time() < deadline and not (
                    s.decodes() or s.counters()["rejected"]["total"]):
                time.sleep(0.02)
        finally:
            lst.stop()
        assert len(s.decodes()) == expect_decodes, allowed


def test_the_drop_count_and_addresses_are_visible_in_diagnostics(monkeypatch):
    s = State()
    lst = UDPListener(s)
    monkeypatch.setattr(server, "_state", s)
    monkeypatch.setattr(server, "_listener", lst)
    lst.receive(CQ, "192.168.1.99")
    d = server.jt_diagnostics()
    assert d["rejected"]["total"] == 1 and d["rejected"]["senders"] == ["192.168.1.99"]
    assert d["listening"]["allowed_senders"] == ["127.0.0.1"]
    assert "not proof of who sent" in d["sender_list"]


def test_a_port_in_use_is_reported_not_fatal():
    holder = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    holder.bind(("127.0.0.1", 0))
    try:
        lst = UDPListener(State(), port=holder.getsockname()[1])
        lst.start()
        assert lst.error and "could not listen" in lst.error
    finally:
        holder.close()
