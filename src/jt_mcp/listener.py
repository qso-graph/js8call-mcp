"""The UDP listener: WSJT-X's messages in, nothing out.

The rules are QSO Graph Desktop's (QGD-INT-0005, QGD-INT-0006), as the fleet's
"Servers that listen" section (qso-graph-devel MCP-SECURITY-FRAMEWORK.md) adopts
them, and as n1mm-mcp implements them:

1. The default is this computer alone: 127.0.0.1.
2. Nothing binds every interface. 0.0.0.0 and :: are refused.
3. Who may send is a list, checked before a byte is read. On a network address
   the list is required, and there is no value meaning anyone.
4. The sender's address is used: it is what the check reads.
5. Names are not accepted as senders: the check runs on every datagram.
6. The list keeps other machines out; it is not proof of who sent. A UDP source
   address can be forged on the same network. What contains that is that this
   server only reads: a forged datagram can mislead about what WSJT-X is doing,
   and cannot make anything happen.
7. A dropped datagram is not counted as received.
8. Everything keyed by sender is bounded (state.py).

The socket only receives. Nothing in this package sends a datagram, so WSJT-X's
Reply, Halt Tx and Free Text, the messages that act on its transmitter, cannot
be sent from here.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading

from qso_graph_lib.jt import protocol

from .state import State

logger = logging.getLogger(__name__)

DEFAULT_PORT = 2237  # WSJT-X's default UDP Server port (Settings, Reporting)
_BUFSIZE = 65_535

_BIND_EVERYTHING = frozenset({"0.0.0.0", "::", "0", "::0", "0:0:0:0:0:0:0:0", "*", ""})
_LOOPBACK = frozenset({"127.0.0.1", "localhost"})


def own_addresses() -> list[str]:
    """This machine's IPv4 addresses, for an error message. Best effort."""
    try:
        _, _, addrs = socket.gethostbyname_ex(socket.gethostname())
    except OSError:
        return []
    return sorted(a for a in addrs if not a.startswith("127."))


def _ipv4(value: str, what: str) -> str:
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        raise ValueError(
            f"{what} {value} is not an IP address. Names are not accepted: the check runs "
            "on every datagram, and resolving a name then would make who is trusted depend "
            "on DNS at that moment."
        ) from None
    if addr.version != 4:
        raise ValueError(f"{what} {value} is IPv6; WSJT-X's UDP Server is reached over IPv4.")
    return str(addr)


def resolve_listener(bind: str, allow: list[str] | None) -> tuple[str, frozenset[str]]:
    """The address to listen on and the senders to accept, or ValueError."""
    bind = (bind or "").strip()
    if bind.lower() in _BIND_EVERYTHING:
        mine = own_addresses()
        example = mine[0] if mine else "192.168.1.50"
        raise ValueError(
            f"--bind {bind or '(empty)'} would listen on every network interface at once, "
            "which is more than you need and cannot be narrowed afterwards.\n"
            "Name the one address of this PC that WSJT-X can reach"
            + (f" (this PC: {', '.join(mine)})" if mine else "")
            + ", and name who may send:\n"
            f"  jt-mcp --bind {example} --allow <the PC running WSJT-X>\n"
            "Or leave --bind unset for WSJT-X on this PC."
        )

    allowed = [_ipv4(a.strip(), "--allow") for a in (allow or []) if a and a.strip()]

    if bind.lower() in _LOOPBACK:
        return "127.0.0.1", frozenset({"127.0.0.1", *allowed})

    bind = _ipv4(bind, "--bind")
    if not allowed:
        raise ValueError(
            f"--bind {bind} listens on a network, so --allow is required: name each PC "
            "that may send.\n"
            f"  jt-mcp --bind {bind} --allow 192.168.1.40\n"
            "Repeat --allow for more than one. There is no value meaning anyone."
        )
    return bind, frozenset(allowed)


class UDPListener:
    """Receives WSJT-X's datagrams on a background thread and hands them to State."""

    def __init__(
        self,
        state: State,
        port: int = DEFAULT_PORT,
        bind_addr: str = "127.0.0.1",
        allowed_senders: frozenset[str] | None = None,
    ) -> None:
        self.state = state
        self.port = port
        self.bind_addr = bind_addr
        self.allowed_senders = (
            frozenset({"127.0.0.1"}) if allowed_senders is None else allowed_senders
        )
        if not self.allowed_senders:
            raise ValueError("allowed_senders is empty, which would accept nothing")
        self.bound_port: int | None = None
        self.error: str | None = None
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        try:
            sock.bind((self.bind_addr, self.port))
        except OSError as e:
            sock.close()
            # Said, not raised: the tools still answer, and jt_diagnostics says why
            # nothing arrives (most often another program already has the port).
            self.error = f"could not listen on {self.bind_addr}:{self.port}: {e.strerror or e}"
            logger.error("%s", self.error)
            return
        self._sock = sock
        self.bound_port = sock.getsockname()[1]
        logger.info("listening for WSJT-X on %s:%d, accepting %s", self.bind_addr,
                    self.bound_port, ", ".join(sorted(self.allowed_senders)))
        self._thread = threading.Thread(target=self._loop, daemon=True, name="jt-udp")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._sock:
            self._sock.close()
        if self._thread:
            self._thread.join(timeout=3.0)

    def _loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                data, addr = self._sock.recvfrom(_BUFSIZE)
            except socket.timeout:
                continue
            except OSError:
                if self._stop.is_set():
                    break
                raise
            self.receive(data, addr[0])

    def receive(self, data: bytes, sender: str) -> None:
        """One datagram: who sent it first, and only then what it says."""
        if sender not in self.allowed_senders:
            self.state.record_rejected_sender(sender)
            return
        try:
            msg = protocol.parse(data)
        except ValueError:
            self.state.record_malformed()
            return
        self.state.handle(msg)
