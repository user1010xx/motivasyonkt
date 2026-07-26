"""Veri dilimi kesimleri (gönderim saatinden ayrı).

Railway env:
  CUTOFF_SABAH=12:00
  CUTOFF_OGLEN=16:00
  CUTOFF_AKSAM=18:10
"""

from __future__ import annotations

from datetime import time

# Varsayılanlar — aksam 18:10
_CUTOFFS: dict[str, time] = {
    "sabah": time(12, 0, 0),
    "oglen": time(16, 0, 0),
    "aksam": time(18, 10, 0),
}


def parse_hhmm(value: str, default: time) -> time:
    value = (value or "").strip()
    if not value:
        return default
    parts = value.split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(parts[2]) if len(parts) > 2 else 0
        return time(h, m, s)
    except (ValueError, IndexError):
        return default


def configure_cutoffs(
    *,
    sabah: str | None = None,
    oglen: str | None = None,
    aksam: str | None = None,
) -> None:
    _CUTOFFS["sabah"] = parse_hhmm(sabah or "", time(12, 0, 0))
    _CUTOFFS["oglen"] = parse_hhmm(oglen or "", time(16, 0, 0))
    _CUTOFFS["aksam"] = parse_hhmm(aksam or "", time(18, 10, 0))


def get_cutoff(period_value: str) -> time:
    return _CUTOFFS.get(period_value, time(23, 59, 59))


def window_label_for(period_value: str) -> str:
    end = get_cutoff(period_value)
    return f"00:00 – {end.strftime('%H:%M')}"
