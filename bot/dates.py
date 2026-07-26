from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


class DateParseError(ValueError):
    pass


def today_in_tz(timezone: str = "Europe/Istanbul") -> date:
    return datetime.now(ZoneInfo(timezone)).date()


def parse_day_arg(
    args: list[str] | None,
    *,
    timezone: str = "Europe/Istanbul",
) -> date:
    """Komut argümanından gün parse et.

    Desteklenenler:
      (boş)           -> bugün (TZ)
      dün / dun / yesterday
      26.07.2026
      26.07.26
      26/07/2026
      2026-07-26
    """
    today = today_in_tz(timezone)
    if not args:
        return today

    raw = " ".join(args).strip().lower()
    # Türkçe karakterleri sadeleştir
    raw = (
        raw.replace("ü", "u")
        .replace("ö", "o")
        .replace("ş", "s")
        .replace("ı", "i")
        .replace("ğ", "g")
        .replace("ç", "c")
    )

    if raw in {"dun", "yesterday", "dunun", "onceki"}:
        return today - timedelta(days=1)
    if raw in {"bugun", "today", "bugün"}:
        return today

    # 2026-07-26
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if m:
        y, mo, d = map(int, m.groups())
        return _safe_date(y, mo, d)

    # 26.07.2026 | 26.07.26 | 26/07/2026
    m = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", raw)
    if m:
        d, mo, y = map(int, m.groups())
        if y < 100:
            y += 2000
        return _safe_date(y, mo, d)

    raise DateParseError(
        f"Tarih anlaşılamadı: {args!r}. "
        "Örnek: /sabah 26.07.2026  veya  /sabah dün"
    )


def _safe_date(y: int, m: int, d: int) -> date:
    try:
        return date(y, m, d)
    except ValueError as exc:
        raise DateParseError(f"Geçersiz tarih: {d:02d}.{m:02d}.{y}") from exc
