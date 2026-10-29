"""What a decoded FT8/FT4 message says, read from its text.

WSJT-X's Decode message carries the decoded text as WSJT-X shows it in Band
Activity (``CQ POTA K1ABC FN42``, ``K1ABC W9XYZ -12``). The structure is WSJT-X's
own: the standard 77-bit messages described in the WSJT-X User Guide, "Standard
messages" and "Directed CQ" (KI7MT, 2026-10-29: the WSJT-X project defines the
protocol). Anything that is not one of those shapes is ``other`` and keeps its text.

Nothing here trusts the text. It arrives in a UDP datagram, so it is matched
against fixed patterns and never evaluated, and a token that is not a plausible
callsign is not reported as one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A callsign as it appears in a decode: letters, digits and "/", with at least one
# of each (K1ABC, PJ4/K1ABC, K1ABC/P). WSJT-X shows a hashed call it cannot
# resolve as "<...>" and a resolved one as "<PJ4/K1ABC>".
_CALL = re.compile(r"^(?=.*[A-Z])(?=.*[0-9])[A-Z0-9/]{3,13}$")
_GRID = re.compile(r"^[A-R]{2}[0-9]{2}$")
_REPORT = re.compile(r"^R?[+-][0-9]{2}$")
_SIGNOFF = frozenset({"RRR", "RR73", "73"})

# The directed-CQ words the WSJT-X User Guide names. A modifier not listed here is
# still reported, raw, with cq_type "other": the list helps a caller filter, and
# is not what decides whether a CQ is shown.
_CQ_TYPE = {
    "DX": "dx",
    # Programmes a station is activating.
    "POTA": "activity", "SOTA": "activity", "WWFF": "activity", "IOTA": "activity",
    "BOTA": "activity",
    # Contest exchanges WSJT-X has a mode for (Settings, Advanced, Special operating activity).
    "TEST": "contest", "FD": "contest", "RU": "contest", "WW": "contest", "BU": "contest",
    # Continents and areas.
    "NA": "region", "SA": "region", "EU": "region", "AS": "region", "AF": "region",
    "OC": "region", "AN": "region", "JA": "region",
}
_MODIFIER = re.compile(r"^(?:[0-9]{3}|[A-Z]{1,4})$")

CQ_TYPES = ("plain", "dx", "activity", "contest", "region", "frequency", "other")


@dataclass(frozen=True)
class Reading:
    """One decode's text, read. Fields not present in the message are None."""

    kind: str  # "cq", "directed" or "other"
    from_call: str | None = None
    to_call: str | None = None
    grid: str | None = None
    report: str | None = None
    signoff: str | None = None
    cq_type: str | None = None
    cq_modifier: str | None = None


def _call(token: str) -> str | None:
    """A callsign, or None. "<...>" (a call WSJT-X could not resolve) is None."""
    t = token[1:-1] if token.startswith("<") and token.endswith(">") else token
    return t if _CALL.match(t) else None


def read(text: str) -> Reading:
    """Read one decode's message text."""
    words = text.upper().split()
    if not words:
        return Reading(kind="other")

    if words[0] == "CQ":
        rest = words[1:]
        modifier = None
        # "CQ POTA K1ABC FN42": a modifier only when a callsign follows it, so
        # "CQ K1ABC FN42" is never read as a modifier of "K1ABC".
        if len(rest) >= 2 and _MODIFIER.match(rest[0]) and _call(rest[1]):
            modifier, rest = rest[0], rest[1:]
        caller = _call(rest[0]) if rest else None
        if caller is None:
            return Reading(kind="other")
        has_grid = len(rest) > 1 and _GRID.match(rest[1]) and rest[1] != "RR73"
        grid = rest[1] if has_grid else None
        if modifier is None:
            cq_type = "plain"
        elif modifier.isdigit():
            cq_type = "frequency"
        else:
            cq_type = _CQ_TYPE.get(modifier, "other")
        return Reading(kind="cq", from_call=caller, grid=grid, cq_type=cq_type,
                       cq_modifier=modifier)

    # "TO FROM [GRID|REPORT|RRR|RR73|73]"
    if len(words) in (2, 3):
        to_call, from_call = _call(words[0]), _call(words[1])
        # "<...> W9XYZ -12": the station called could not be resolved, but who is
        # sending is still known, and still heard.
        if from_call and (to_call or words[0] == "<...>"):
            last = words[2] if len(words) == 3 else None
            grid = report = signoff = None
            if last in _SIGNOFF:
                signoff = last
            elif last and _REPORT.match(last):
                report = last
            elif last and _GRID.match(last):
                grid = last
            elif last is not None:
                return Reading(kind="other")
            return Reading(kind="directed", from_call=from_call, to_call=to_call,
                           grid=grid, report=report, signoff=signoff)

    return Reading(kind="other")
