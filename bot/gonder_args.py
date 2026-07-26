""" /gonder argüman parse.

Örnekler:
  /gonder
  /gonder sabah
  /gonder 26.07.2026 aksam
  /gonder aksam 26.07.2026
  /gonder dün oglen
  /gonder 26.07.2026 öğlen
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from bot.dates import DateParseError, parse_day_arg, today_in_tz
from bot.models import Period

_PERIOD_ALIASES = {
    "sabah": Period.SABAH,
    "oglen": Period.OGLEN,
    "öğlen": Period.OGLEN,
    "ogle": Period.OGLEN,
    "aksam": Period.AKSAM,
    "akşam": Period.AKSAM,
    "aksm": Period.AKSAM,
}


def _norm(token: str) -> str:
    t = token.strip().lower()
    return (
        t.replace("ü", "u")
        .replace("ö", "o")
        .replace("ş", "s")
        .replace("ı", "i")
        .replace("ğ", "g")
        .replace("ç", "c")
    )


@dataclass
class GonderRequest:
    """until_now=True → bugün 00:00–şimdi; aksi halde day+period sabit dilim."""

    day: date
    period: Period
    until_now: bool
    label: str  # kullanıcıya özet


def parse_gonder_args(
    args: list[str] | None,
    *,
    timezone: str = "Europe/Istanbul",
) -> GonderRequest:
    tokens = list(args or [])
    if not tokens:
        day = today_in_tz(timezone)
        # stil için period_for_clock service tarafında
        return GonderRequest(
            day=day,
            period=Period.SABAH,
            until_now=True,
            label=f"canlı · {day.strftime('%d.%m.%Y')} · 00:00–şimdi",
        )

    period: Period | None = None
    date_tokens: list[str] = []
    for tok in tokens:
        key = _norm(tok)
        # alias tablosu hem orijinal hem norm ile
        if tok.strip().lower() in _PERIOD_ALIASES:
            period = _PERIOD_ALIASES[tok.strip().lower()]
            continue
        if key in {"sabah", "oglen", "ogle", "aksam", "aksm"}:
            period = {
                "sabah": Period.SABAH,
                "oglen": Period.OGLEN,
                "ogle": Period.OGLEN,
                "aksam": Period.AKSAM,
                "aksm": Period.AKSAM,
            }[key]
            continue
        date_tokens.append(tok)

    try:
        day = (
            parse_day_arg(date_tokens, timezone=timezone)
            if date_tokens
            else today_in_tz(timezone)
        )
    except DateParseError:
        raise

    if period is None:
        # Sadece tarih: bugünse canlı, geçmişse o günün akşam dilimi (tam iş günü)
        today = today_in_tz(timezone)
        if day == today:
            return GonderRequest(
                day=day,
                period=Period.SABAH,
                until_now=True,
                label=f"canlı · {day.strftime('%d.%m.%Y')} · 00:00–şimdi",
            )
        period = Period.AKSAM
        return GonderRequest(
            day=day,
            period=period,
            until_now=False,
            label=f"{period.label} · {day.strftime('%d.%m.%Y')} · {period.window_label}",
        )

    return GonderRequest(
        day=day,
        period=period,
        until_now=False,
        label=f"{period.label} · {day.strftime('%d.%m.%Y')} · {period.window_label}",
    )
