"""What the listener has heard from WSJT-X, held in memory and read by the tools.

Everything here arrives in a UDP datagram, so everything keyed by what a
datagram says is bounded ("Servers that listen", rule 8, MCP-SECURITY-FRAMEWORK):
a forged flood can name a different WSJT-X instance or callsign in every
datagram, and an uncapped table of them is a memory leak anyone on the network
can reach. Each cap keeps its total exact and says when its list is partial.

Nothing is written anywhere. Restarting the server starts empty.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from qso_graph_lib.jt.protocol import MODE_CHARACTER, Message, MessageType

from . import messages

MAX_INSTANCES = 8
MAX_DECODES = 5_000  # per instance: about an hour of a busy 20 m FT8 band
MAX_WSPR = 2_000
MAX_HEARD = 5_000
MAX_REJECTED_SENDERS = 10

_MODE_NAME = {char: name for name, char in MODE_CHARACTER.items()}

# Amateur bands, by dial frequency, for a caller who asks about "20 m" rather than Hz.
_BANDS = (
    ("2200m", 135_700, 137_800), ("630m", 472_000, 479_000), ("160m", 1_800_000, 2_000_000),
    ("80m", 3_500_000, 4_000_000), ("60m", 5_060_000, 5_450_000),
    ("40m", 7_000_000, 7_300_000),
    ("30m", 10_100_000, 10_150_000), ("20m", 14_000_000, 14_350_000),
    ("17m", 18_068_000, 18_168_000), ("15m", 21_000_000, 21_450_000),
    ("12m", 24_890_000, 24_990_000), ("10m", 28_000_000, 29_700_000),
    ("6m", 50_000_000, 54_000_000), ("4m", 70_000_000, 71_000_000),
    ("2m", 144_000_000, 148_000_000),
)


def band(dial_hz: int | None) -> str | None:
    if not dial_hz:
        return None
    for name, low, high in _BANDS:
        if low <= dial_hz <= high:
            return name
    return None


def _utc_of(ms_of_day: int, received: float) -> str:
    """The decode's UTC time: WSJT-X sends milliseconds since UTC midnight only.

    The date is the day it was received, or the day before when the time of day is
    ahead of the clock, which is a decode from just before midnight arriving after it.
    """
    now = datetime.fromtimestamp(received, timezone.utc)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    at = day + timedelta(milliseconds=ms_of_day)
    if at - now > timedelta(hours=1):
        at -= timedelta(days=1)
    return at.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Heard:
    call: str
    count: int
    first_heard: float
    last_heard: float
    last_snr: int
    last_grid: str | None
    last_mode: str
    last_band: str | None


@dataclass
class Instance:
    """One running WSJT-X, by the Id it sends (``WSJT-X``, ``WSJT-X - FT-991A``)."""

    id: str
    first_seen: float
    last_seen: float
    version: str | None = None
    revision: str | None = None
    max_schema: int | None = None
    schema: int | None = None
    last_heartbeat: float | None = None
    status: dict[str, Any] | None = None
    status_at: float | None = None
    cleared_at: float | None = None
    closed_at: float | None = None
    decodes: deque[dict[str, Any]] = field(default_factory=deque)
    wspr: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=MAX_WSPR))
    _decode_keys: set[tuple[int, int, str]] = field(default_factory=set)
    _key_order: deque[tuple[int, int, str]] = field(default_factory=deque)


class State:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started = time.time()
        self._instances: dict[str, Instance] = {}
        self._heard: dict[str, Heard] = {}
        self.heard_capped = False
        self.instances_refused = 0
        self.received = 0
        self.malformed = 0
        self.by_kind: dict[str, int] = {}
        self.last_received: float | None = None
        self._rejected: set[str] = set()
        self.rejected_total = 0
        self._rejected_capped = False

    # ------------------------------------------------------------ the listener

    def record_rejected_sender(self, addr: str) -> None:
        """A datagram was dropped unread: its sender is not on the list.

        Not counted as received (rule 7), so a forged flood cannot look like a
        healthy WSJT-X feed.
        """
        with self._lock:
            self.rejected_total += 1
            if len(self._rejected) < MAX_REJECTED_SENDERS:
                self._rejected.add(addr)
            elif addr not in self._rejected:
                self._rejected_capped = True

    def record_malformed(self) -> None:
        with self._lock:
            self.received += 1
            self.malformed += 1

    def handle(self, msg: Message, now: float | None = None) -> None:
        """Take in one well-formed message from an allowed sender."""
        now = time.time() if now is None else now
        kind = MessageType(msg.kind).name if msg.known else f"type {msg.kind}"
        with self._lock:
            self.received += 1
            self.last_received = now
            self.by_kind[kind] = self.by_kind.get(kind, 0) + 1
            inst = self._instance(msg.sender or "", msg.schema, now)
            if inst is None:
                return
            f = msg.fields
            if msg.kind == MessageType.HEARTBEAT:
                inst.last_heartbeat = now
                inst.closed_at = None
                if "version" in f:
                    inst.version, inst.revision = f["version"], f["revision"]
                    inst.max_schema = f["max_schema"]
            elif msg.kind == MessageType.STATUS:
                inst.status, inst.status_at, inst.closed_at = dict(f), now, None
            elif msg.kind == MessageType.DECODE:
                self._decode(inst, f, now)
            elif msg.kind == MessageType.WSPR_DECODE:
                self._wspr(inst, f, now)
            elif msg.kind == MessageType.CLEAR:
                inst.cleared_at = now
            elif msg.kind == MessageType.CLOSE:
                inst.closed_at = now

    def _instance(self, ident: str, schema: int, now: float) -> Instance | None:
        inst = self._instances.get(ident)
        if inst is None:
            if len(self._instances) >= MAX_INSTANCES:
                self.instances_refused += 1
                return None
            inst = self._instances[ident] = Instance(id=ident, first_seen=now, last_seen=now)
        inst.last_seen, inst.schema = now, schema
        return inst

    def _decode(self, inst: Instance, f: dict[str, object], now: float) -> None:
        message = str(f.get("message") or "")
        key = (int(f["ms_of_day"]), int(f["df"]), message)  # type: ignore[call-overload]
        # A decode WSJT-X sends again (not new: another program asked it to
        # Replay) is already here; keep the first.
        if not f.get("is_new") and key in inst._decode_keys:
            return
        status = inst.status or {}
        dial = status.get("dial_hz")
        mode_char = str(f.get("mode") or "")
        reading = messages.read(message)
        record = {
            "utc": _utc_of(int(f["ms_of_day"]), now),  # type: ignore[call-overload]
            "received": now,
            "instance": inst.id,
            "snr": f.get("snr"),
            "dt": round(float(f.get("dt") or 0.0), 2),  # type: ignore[arg-type]
            "df": f.get("df"),
            "mode": _MODE_NAME.get(mode_char, mode_char),
            "message": message,
            "low_confidence": bool(f.get("low_confidence")),
            "dial_hz": dial,
            "band": band(dial),
            **{k: v for k, v in asdict(reading).items() if v is not None},
        }
        inst.decodes.append(record)
        inst._key_order.append(key)
        inst._decode_keys.add(key)
        if len(inst.decodes) > MAX_DECODES:
            inst.decodes.popleft()
            inst._decode_keys.discard(inst._key_order.popleft())
        if reading.from_call:
            self._hear(reading.from_call, record, now)

    def _wspr(self, inst: Instance, f: dict[str, object], now: float) -> None:
        hz = f.get("frequency_hz")
        inst.wspr.append({
            "utc": _utc_of(int(f["ms_of_day"]), now),  # type: ignore[call-overload]
            "received": now,
            "instance": inst.id,
            "call": f.get("callsign"),
            "grid": f.get("grid"),
            "power_dbm": f.get("power_dbm"),
            "snr": f.get("snr"),
            "dt": round(float(f.get("dt") or 0.0), 2),  # type: ignore[arg-type]
            "drift_hz": f.get("drift_hz"),
            "frequency_hz": hz,
            "band": band(hz),  # type: ignore[arg-type]
        })

    def _hear(self, call: str, record: dict[str, Any], now: float) -> None:
        h = self._heard.get(call)
        if h is None:
            if len(self._heard) >= MAX_HEARD:
                # The station heard longest ago makes room, and the list says it
                # is partial.
                oldest = min(self._heard.values(), key=lambda x: x.last_heard)
                del self._heard[oldest.call]
                self.heard_capped = True
            h = self._heard[call] = Heard(
                call=call, count=0, first_heard=now, last_heard=now, last_snr=0,
                last_grid=None, last_mode="", last_band=None,
            )
        h.count += 1
        h.last_heard, h.last_snr = now, record["snr"]
        h.last_mode, h.last_band = record["mode"], record["band"]
        if record.get("grid"):
            h.last_grid = record["grid"]

    # ------------------------------------------------------------ the tools

    def instances(self) -> list[Instance]:
        with self._lock:
            return list(self._instances.values())

    def decodes(self) -> list[dict[str, Any]]:
        with self._lock:
            out = [d for inst in self._instances.values() for d in inst.decodes]
        return sorted(out, key=lambda d: d["received"])

    def wspr(self) -> list[dict[str, Any]]:
        with self._lock:
            out = [d for inst in self._instances.values() for d in inst.wspr]
        return sorted(out, key=lambda d: d["received"])

    def heard(self) -> list[Heard]:
        with self._lock:
            return list(self._heard.values())

    def counters(self) -> dict[str, Any]:
        with self._lock:
            return {
                "received": self.received,
                "malformed": self.malformed,
                "by_kind": dict(self.by_kind),
                "last_received": self.last_received,
                "instances_refused": self.instances_refused,
                "heard_capped": self.heard_capped,
                "rejected": {
                    "total": self.rejected_total,
                    "senders": sorted(self._rejected),
                    "more_not_listed": self._rejected_capped,
                },
            }

