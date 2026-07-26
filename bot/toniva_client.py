from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from bot.models import AgentStats, Period

logger = logging.getLogger(__name__)

_NAME_KEYS = (
    "agentName",
    "agent_name",
    "userName",
    "user_name",
    "name",
    "fullName",
    "full_name",
    "displayName",
    "display_name",
    "agent",
    "user",
    "operator",
    "personel",
    "agentFullName",
    "extensionName",
    "extension_name",
    "memberName",
    "staffName",
    "employeeName",
)

# Konuşma süresi — ring/wait/hold YOK (öncelik sırası)
_TALK_DURATION_KEYS = (
    "billsec",
    "billSec",
    "billableSeconds",
    "billable_seconds",
    "billableDuration",
    "billable_duration",
    "talkDuration",
    "talk_duration",
    "talkTime",
    "talk_time",
    "talkSeconds",
    "talk_seconds",
    "talkDurationSeconds",
    "talk_duration_seconds",
    "talkDurationMs",
    "talk_duration_ms",
    "speakingTime",
    "speaking_time",
    "totalTalkTime",
    "total_talk_time",
    "conversationDuration",
    "conversation_duration",
    "connectedDuration",
    "connected_duration",
    "answerDuration",
    "answer_duration",
    "handleTime",
    "handle_time",
    "durationTalk",
    "duration_talk",
    "bridgeDuration",
    "bridge_duration",
    "bridgedSeconds",
    "inCallSeconds",
    "in_call_seconds",
    "konusmaSuresi",
    "konusma_suresi",
    "sure",
    "talk",
)

# Genel duration — ring değilse yedek
_DURATION_FALLBACK_KEYS = (
    "duration",
    "durationSeconds",
    "duration_seconds",
    "durationMs",
    "duration_ms",
    "callDuration",
    "call_duration",
    "totalDuration",
    "total_duration",
    "length",
    "len",
    "seconds",
)

# Bitiş zamanı (süre = end - start)
_END_TIME_KEYS = (
    "endTime",
    "end_time",
    "endedAt",
    "ended_at",
    "hangupTime",
    "hangup_time",
    "hangupAt",
    "hangup_at",
    "finishTime",
    "finish_time",
    "stopTime",
    "stop_time",
    "callEnd",
    "call_end",
)

# Saat içeren alanlar önce; çıplak "date" en sonda ve sadece clock varsa
_TIME_KEYS = (
    "startTime",
    "start_time",
    "startedAt",
    "started_at",
    "callStart",
    "call_start",
    "callStartedAt",
    "call_started_at",
    "beginTime",
    "begin_time",
    "connectedAt",
    "connected_at",
    "answerTime",
    "answer_time",
    "answeredAt",
    "answered_at",
    "timestamp",
    "createdAt",
    "created_at",
    "dateTime",
    "datetime",
    "callDateTime",
    "call_date_time",
    "callDate",
    "call_date",
    "callTime",
    "call_time",
    "time",
)


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    lower_map = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
        lk = key.lower()
        if lk in lower_map and lower_map[lk] not in (None, ""):
            return lower_map[lk]
    return None


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", ".")
    if not text:
        return 0
    if ":" in text and re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", text):
        parts = text.split(":")
        nums = [int(float(p)) for p in parts]
        if len(nums) == 3:
            h, m, s = nums
            return h * 3600 + m * 60 + s
        if len(nums) == 2:
            m, s = nums
            return m * 60 + s
    # "1m 40s" / "1 sa 2 dk"
    lower = text.lower()
    if any(x in lower for x in ("sa", "dk", "sn", "h", "m", "s")):
        total = 0
        for m in re.finditer(r"(\d+)\s*sa", lower):
            total += int(m.group(1)) * 3600
        for m in re.finditer(r"(\d+)\s*h\b", lower):
            total += int(m.group(1)) * 3600
        for m in re.finditer(r"(\d+)\s*dk", lower):
            total += int(m.group(1)) * 60
        for m in re.finditer(r"(\d+)\s*m\b", lower):
            total += int(m.group(1)) * 60
        for m in re.finditer(r"(\d+)\s*sn", lower):
            total += int(m.group(1))
        for m in re.finditer(r"(\d+)\s*s\b", lower):
            total += int(m.group(1))
        if total:
            return total
    try:
        return int(float(text))
    except ValueError:
        return 0


def _to_seconds(value: Any, *, key: str = "") -> int:
    """Sayı/ms/dk → saniye."""
    sec = _as_int(value)
    if sec <= 0:
        return 0
    kl = key.lower()
    if "ms" in kl or "millis" in kl:
        return max(0, sec // 1000)
    if "minute" in kl or kl.endswith("_min") or kl.endswith("min"):
        return sec * 60
    # Ham sayı çok büyükse ms olabilir (1 günden uzun tek çağrı nadir)
    if sec > 24 * 3600 and "ms" not in kl:
        # 90_000 → muhtemel 90 sn ms
        if sec > 100_000:
            return sec // 1000
    return sec


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """İç içe dict'i düz anahtarlara çevir (a.b.c)."""
    out: dict[str, Any] = {}
    if not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
            out[str(k)] = v  # kısa ad da erişilebilir
    return out


def _text_has_clock(text: str) -> bool:
    """Tarih string'inde saat bileşeni var mı? (sadece gün değil)."""
    t = text.strip()
    if re.search(r"T\d{1,2}:\d{2}", t):
        return True
    if re.search(r"\s\d{1,2}:\d{2}", t):
        return True
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", t):
        return True
    # sadece 2026-07-26 veya 26.07.2026
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        return False
    if re.fullmatch(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", t):
        return False
    return bool(re.search(r"\d{1,2}:\d{2}", t))


def _as_name(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        first = value.get("firstName") or value.get("first_name") or value.get("ad")
        last = value.get("lastName") or value.get("last_name") or value.get("soyad")
        if first or last:
            return f"{first or ''} {last or ''}".strip() or None
        for k in ("name", "fullName", "full_name", "displayName", "label", "title", "username"):
            if value.get(k):
                return str(value[k]).strip() or None
        nested = _pick(value, _NAME_KEYS)
        if nested is not None and not isinstance(nested, dict):
            text = str(nested).strip()
            if text:
                return text
        return None
    if isinstance(value, (int, float)):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "undefined", "-"}:
        return None
    return text


def _guess_name(row: dict[str, Any]) -> str | None:
    name = _as_name(_pick(row, _NAME_KEYS))
    if name:
        return name
    first = row.get("firstName") or row.get("first_name")
    last = row.get("lastName") or row.get("last_name")
    if first or last:
        return f"{first or ''} {last or ''}".strip() or None
    for k, v in row.items():
        kl = str(k).lower()
        if any(
            x in kl
            for x in ("agent", "user", "operator", "personel", "staff", "member", "extension")
        ):
            name = _as_name(v)
            if name:
                return name
    for nest_key in ("metrics", "stats", "summary", "agentInfo", "userInfo"):
        nested = row.get(nest_key)
        if isinstance(nested, dict):
            name = _guess_name(nested)
            if name:
                return name
    return None


def _is_ring_or_wait_key(key: str) -> bool:
    kl = key.lower()
    return any(
        x in kl
        for x in (
            "ring",
            "wait",
            "hold",
            "queue",
            "ivr",
            "idle",
            "wrap",
            "acw",
            "mute",
        )
    )


def _talk_seconds_from_row(row: dict[str, Any]) -> int:
    """Tek görüşmenin konuşma süresi (saniye). Ring/wait hariç."""
    flat = _flatten(row)
    candidates = [row, flat]
    for nest in ("metrics", "stats", "summary", "data", "cdr", "call", "recording"):
        v = row.get(nest)
        if isinstance(v, dict):
            candidates.append(v)

    def _scan_keys(keys: tuple[str, ...]) -> int:
        for c in candidates:
            for key in keys:
                if _is_ring_or_wait_key(key):
                    continue
                val = _pick(c, (key,)) if isinstance(c, dict) else None
                if val is None and isinstance(c, dict):
                    # flatten kısa ad
                    val = c.get(key)
                if val is not None and val != "":
                    sec = _to_seconds(val, key=key)
                    if sec > 0:
                        return sec
        return 0

    sec = _scan_keys(_TALK_DURATION_KEYS)
    if sec > 0:
        return sec

    # Fuzzy: talk/bill/speak/sure/konus
    for c in candidates:
        if not isinstance(c, dict):
            continue
        for k, v in c.items():
            kl = str(k).lower()
            if _is_ring_or_wait_key(kl):
                continue
            if any(
                x in kl
                for x in (
                    "talk",
                    "billsec",
                    "bill_sec",
                    "billable",
                    "speak",
                    "bridge",
                    "konus",
                    "sure",
                )
            ):
                sec = _to_seconds(v, key=str(k))
                if sec > 0:
                    return sec

    sec = _scan_keys(_DURATION_FALLBACK_KEYS)
    if sec > 0:
        return sec

    for c in candidates:
        if not isinstance(c, dict):
            continue
        for k, v in c.items():
            kl = str(k).lower()
            if _is_ring_or_wait_key(kl):
                continue
            if "duration" in kl or kl in {"length", "len", "seconds"}:
                sec = _to_seconds(v, key=str(k))
                if sec > 0:
                    return sec

    # end - start farkı
    tz = ZoneInfo("Europe/Istanbul")
    day = date.today()
    start = _row_datetime(row, tz=tz, default_day=day, require_clock=True)
    end = None
    for key in _END_TIME_KEYS:
        val = _pick(row, (key,))
        if val is not None:
            end = _parse_dt(val, tz=tz, default_day=day, require_clock=True)
            if end:
                break
    if start and end and end > start:
        diff = int((end - start).total_seconds())
        if 0 < diff < 24 * 3600:
            return diff

    return 0


def _parse_dt(
    value: Any,
    *,
    tz: ZoneInfo,
    default_day: date,
    require_clock: bool = True,
) -> datetime | None:
    """
    require_clock=True: sadece GÜN içeren (2026-07-26) değerleri reddet.
    Aksi halde tüm gün 00:00'a düşüp sabah dilimine yanlış girer.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=tz)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, datetime):
        # naive midnight from date-only may still appear; allow if not require
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz)
        else:
            value = value.astimezone(tz)
        if require_clock and value.hour == 0 and value.minute == 0 and value.second == 0:
            # datetime objesinde clock yok sayılabilir; epoch dışı bilinçli 00:00 nadir
            # string yolundan gelmediyse kabul et (gerçek gece yarısı çağrısı)
            return value
        return value

    text = str(value).strip()
    if not text:
        return None

    if require_clock and not _text_has_clock(text):
        return None

    # ISO
    try:
        iso = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt.astimezone(tz)
    except ValueError:
        pass

    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%H:%M:%S",
        "%H:%M",
    )
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            if fmt in ("%H:%M:%S", "%H:%M"):
                dt = datetime.combine(default_day, dt.time())
            return dt.replace(tzinfo=tz)
        except ValueError:
            continue
    return None


def _row_datetime(
    row: dict[str, Any],
    *,
    tz: ZoneInfo,
    default_day: date,
    require_clock: bool = True,
) -> datetime | None:
    flat = _flatten(row)
    search_spaces = [row, flat]

    for space in search_spaces:
        for key in _TIME_KEYS:
            val = space.get(key)
            if val is None:
                val = _pick(space, (key,))
            if val is not None:
                dt = _parse_dt(
                    val, tz=tz, default_day=default_day, require_clock=require_clock
                )
                if dt:
                    return dt

    # date + time ayrı alanlar
    for space in search_spaces:
        date_val = None
        time_val = None
        for k, v in space.items():
            kl = str(k).lower().rsplit(".", 1)[-1]
            if kl in {"date", "calldate", "call_date", "gun", "day"}:
                date_val = v
            if kl in {"time", "calltime", "call_time", "saat"}:
                time_val = v
        if date_val is not None and time_val is not None:
            combined = f"{date_val} {time_val}"
            dt = _parse_dt(combined, tz=tz, default_day=default_day, require_clock=True)
            if dt:
                return dt

    # fuzzy — çıplak date (clock yok) require_clock ile elenir
    for space in search_spaces:
        for k, v in space.items():
            kl = str(k).lower()
            if _is_ring_or_wait_key(kl):
                continue
            if any(
                x in kl
                for x in ("start", "time", "created", "begin", "connect", "answer")
            ):
                dt = _parse_dt(
                    v, tz=tz, default_day=default_day, require_clock=require_clock
                )
                if dt:
                    return dt
    return None


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for key in (
        "rows",
        "data",
        "items",
        "results",
        "agents",
        "report",
        "records",
        "conversations",
        "payload",
        "content",
        "list",
    ):
        if key not in payload:
            continue
        val = payload[key]
        if isinstance(val, list) and (not val or isinstance(val[0], dict)):
            return [r for r in val if isinstance(r, dict)]
        if isinstance(val, dict):
            nested = _extract_rows(val)
            if nested:
                return nested
    for val in payload.values():
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return [r for r in val if isinstance(r, dict)]
    return []


def aggregate_conversations_window(
    rows: list[dict[str, Any]],
    *,
    day: date,
    cutoff: time,
    timezone: str = "Europe/Istanbul",
) -> tuple[list[AgentStats], dict[str, int]]:
    """00:00 <= call_time < cutoff (aksam: 23:59:59 dahil) topla."""
    tz = ZoneInfo(timezone)
    start = datetime.combine(day, time(0, 0, 0), tzinfo=tz)
    if cutoff.hour == 23 and cutoff.minute == 59:
        end = datetime.combine(day, time(23, 59, 59), tzinfo=tz) + timedelta(seconds=1)
    else:
        end = datetime.combine(day, cutoff, tzinfo=tz)

    agents: dict[str, AgentStats] = {}
    stats = {
        "rows_total": len(rows),
        "rows_in_window": 0,
        "rows_no_name": 0,
        "rows_no_time": 0,
        "rows_out_of_window": 0,
        "rows_with_talk": 0,
        "talk_sum": 0,
    }

    for row in rows:
        name = _guess_name(row)
        if not name:
            stats["rows_no_name"] += 1
            continue

        # SAAT bilgisiz tarih (sadece gün) → dilime alma (yoksa tüm gün 00:00 sanılır)
        dt = _row_datetime(row, tz=tz, default_day=day, require_clock=True)
        if dt is None:
            stats["rows_no_time"] += 1
            continue

        if not (start <= dt < end):
            stats["rows_out_of_window"] += 1
            continue

        talk = _talk_seconds_from_row(row)
        stats["rows_in_window"] += 1
        stats["talk_sum"] += talk
        if talk > 0:
            stats["rows_with_talk"] += 1

        if name not in agents:
            agents[name] = AgentStats(name=name, call_count=0, talk_seconds=0)
        agents[name].call_count += 1
        agents[name].talk_seconds += talk

    return list(agents.values()), stats


def sample_row_debug(row: dict[str, Any], *, day: date, timezone: str) -> str:
    """Tek satırdan alan özeti (PII: isim kısaltılır)."""
    tz = ZoneInfo(timezone)
    name = _guess_name(row) or "?"
    safe_name = (name[:2] + "***") if len(name) > 2 else "***"
    dt = _row_datetime(row, tz=tz, default_day=day, require_clock=True)
    talk = _talk_seconds_from_row(row)
    keys = list(row.keys())
    # süre/zaman adayları + örnek değer (kısaltılmış)
    interesting = []
    flat = _flatten(row)
    for k, v in list(flat.items())[:80]:
        kl = str(k).lower()
        if any(
            x in kl
            for x in (
                "time",
                "date",
                "dur",
                "talk",
                "bill",
                "sec",
                "start",
                "end",
                "agent",
                "user",
                "sure",
                "konus",
            )
        ):
            vs = str(v)
            if len(vs) > 40:
                vs = vs[:40] + "…"
            interesting.append(f"{k}={vs}")
    return (
        f"name={safe_name} dt={dt} talk_sec={talk} "
        f"keys={keys[:25]} | {interesting[:20]}"
    )


def describe_payload(payload: Any) -> str:
    rows = _extract_rows(payload)
    if isinstance(payload, dict):
        top_keys = list(payload.keys())[:20]
    elif isinstance(payload, list):
        top_keys = [f"list[{len(payload)}]"]
    else:
        top_keys = [type(payload).__name__]
    if not rows:
        return f"satır=0 üst_alanlar={top_keys}"
    sample = rows[0]
    sample_keys = list(sample.keys())[:30]
    types = {k: type(sample[k]).__name__ for k in list(sample.keys())[:12]}
    return f"satır={len(rows)} üst={top_keys} örnek_alanlar={sample_keys} tipler={types}"


MOCK_AGENTS = [
    AgentStats(name="Ayşe Yılmaz", call_count=52, talk_seconds=3 * 3600 + 18 * 60),
    AgentStats(name="Mehmet Kaya", call_count=47, talk_seconds=3 * 3600 + 42 * 60),
    AgentStats(name="Zeynep Arslan", call_count=61, talk_seconds=2 * 3600 + 55 * 60),
    AgentStats(name="Can Demir", call_count=39, talk_seconds=2 * 3600 + 10 * 60),
    AgentStats(name="Elif Çetin", call_count=44, talk_seconds=2 * 3600 + 48 * 60),
    AgentStats(name="umit", call_count=40, talk_seconds=1 * 3600 + 5 * 60),
    AgentStats(name="Elisa", call_count=28, talk_seconds=2 * 3600 + 20 * 60),
]


class TonivaApiError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


def _format_toniva_error(resp: httpx.Response, endpoint: str) -> TonivaApiError:
    status = resp.status_code
    code = message = required_scope = None
    try:
        body = resp.json()
        if isinstance(body, dict):
            code = body.get("code") or body.get("error_code")
            message = body.get("message") or body.get("error")
            required_scope = body.get("required_scope")
    except Exception:
        message = (resp.text or "")[:200]

    hints = {
        "CRM-2090": "API anahtarı header'da yok.",
        "CRM-2091": "API anahtarı geçersiz.",
        "CRM-2093": "IP whitelist (Railway IP).",
        "CRM-2094": "Rate limit.",
        "CRM-2095": "Tenant pasif.",
        "CRM-2336": "Yetersiz scope — reports:read ekle.",
    }
    tip = hints.get(str(code), f"HTTP {status}")
    parts = [f"Toniva {status} ({endpoint})"]
    if code:
        parts.append(f"kod: {code}")
    if message:
        parts.append(str(message))
    if required_scope:
        parts.append(f"gerekli scope: {required_scope}")
    parts.append(tip)
    return TonivaApiError(" | ".join(parts), status=status, code=str(code) if code else None)


class TonivaClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        mock_mode: bool = False,
        timezone: str = "Europe/Istanbul",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = (api_key or "").strip()
        self.mock_mode = mock_mode
        self.timezone = timezone
        self.last_debug: str = ""

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key,
            "Accept": "application/json",
        }

    async def _get_report(
        self,
        client: httpx.AsyncClient,
        slug: str,
        params: dict[str, Any],
    ) -> httpx.Response:
        url = f"{self.base_url}/reports/{slug}"
        return await client.get(url, headers=self._headers(), params=params)

    async def _fetch_all_conversations(
        self, client: httpx.AsyncClient, day: date
    ) -> list[dict[str, Any]]:
        """conversations raporunu sayfalayarak çek (max ~50 sayfa)."""
        all_rows: list[dict[str, Any]] = []
        page = 1
        page_size = 5000
        max_pages = 40

        while page <= max_pages:
            params: dict[str, Any] = {
                "startDate": day.isoformat(),
                "endDate": day.isoformat(),
                "pageSize": page_size,
                "page": page,
            }
            resp = await self._get_report(client, "conversations", params)
            if resp.status_code != 200:
                if page == 1:
                    raise _format_toniva_error(resp, "reports/conversations")
                logger.warning("conversations page %s HTTP %s — duruluyor", page, resp.status_code)
                break

            body = resp.json()
            rows = _extract_rows(body)
            all_rows.extend(rows)

            meta = body.get("meta") if isinstance(body, dict) else None
            meta = meta if isinstance(meta, dict) else {}
            truncated = bool(meta.get("truncated"))
            total = meta.get("total_count") or meta.get("total") or meta.get("totalCount")

            logger.info(
                "conversations page=%s rows=%s total_meta=%s truncated=%s",
                page,
                len(rows),
                total,
                truncated,
            )

            if not rows:
                break
            if not truncated and len(rows) < page_size:
                break
            if total is not None:
                try:
                    if len(all_rows) >= int(total):
                        break
                except (TypeError, ValueError):
                    pass
            # truncated=true ama page ile devam
            if not truncated and page > 1 and len(rows) == 0:
                break
            page += 1

        self.last_debug = f"conversations_raw_rows={len(all_rows)}"
        return all_rows

    async def fetch_agent_stats(
        self,
        day: date,
        period: Period,
    ) -> tuple[list[AgentStats], str]:
        """
        Dönem dilimine göre agent istatistiği:
          sabah 00:00–12:00, öğlen 00:00–16:00, akşam 00:00–23:59
        Kaynak: conversations (çağrı bazlı toplam).
        """
        if self.mock_mode or not self.api_key:
            logger.warning("MOCK_MODE — örnek veri (dilim simülasyonu yok).")
            self.last_debug = "mock"
            return list(MOCK_AGENTS), "mock"

        cutoff = period.cutoff
        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                rows = await self._fetch_all_conversations(client, day)
            except TonivaApiError:
                raise
            except Exception as exc:
                logger.exception("conversations çekilemedi: %s", exc)
                raise TonivaApiError(f"conversations alınamadı: {exc}") from exc

            agents, agg = aggregate_conversations_window(
                rows,
                day=day,
                cutoff=cutoff,
                timezone=self.timezone,
            )
            self.last_debug = (
                f"day={day} period={period.value} window={period.window_label} "
                f"raw={agg['rows_total']} in_window={agg['rows_in_window']} "
                f"no_time={agg['rows_no_time']} out={agg['rows_out_of_window']} "
                f"no_name={agg['rows_no_name']} agents={len(agents)} talk_sum={agg['talk_sum']}"
            )
            logger.info("aggregate: %s", self.last_debug)

            if agents:
                # Konuşma hep 0 ise alan map sorunu — yine de döndür ama kaynağa işaret koy
                if agg["talk_sum"] == 0 and agg["rows_in_window"] > 0:
                    logger.warning(
                        "Dilimde %s çağrı var ama talk_sum=0 — süre alanı eşleşmiyor.",
                        agg["rows_in_window"],
                    )
                    return agents, f"conversations[{period.window_label};talk=0?]"
                return agents, f"conversations[{period.window_label}]"

            if agg["rows_total"] == 0:
                return [], "empty"

            # Saat alanı yoksa tam gün fallback YAPMA — yanlış 779 gibi rakamlar üretir
            if agg["rows_no_time"] > 0 and agg["rows_in_window"] == 0:
                raise TonivaApiError(
                    "Çağrı satırlarında saat bilgisi okunamadı; dilim filtresi uygulanamıyor. "
                    f"no_time={agg['rows_no_time']} total={agg['rows_total']}. "
                    "/debug sabah TARIH ile örnek alanları gönderin."
                )

            return [], "empty"

    async def debug_reports(self, day: date, period: Period | None = None) -> str:
        if self.mock_mode or not self.api_key:
            return "MOCK_MODE aktif."

        period = period or Period.SABAH
        lines = [
            f"Tarih: {day}",
            f"Dönem: {period.value} dilim={period.window_label}",
        ]
        async with httpx.AsyncClient(timeout=90.0) as client:
            rows = await self._fetch_all_conversations(client, day)
            lines.append(f"conversations satır: {len(rows)}")
            for i, sample in enumerate(rows[:3]):
                lines.append(f"--- satır[{i}] ---")
                lines.append(sample_row_debug(sample, day=day, timezone=self.timezone))

            agents, agg = aggregate_conversations_window(
                rows, day=day, cutoff=period.cutoff, timezone=self.timezone
            )
            lines.append(f"aggregate: {agg}")
            lines.append(f"personel: {len(agents)}")
            for a in sorted(agents, key=lambda x: x.call_count, reverse=True)[:8]:
                lines.append(f"  - {a.name}: calls={a.call_count} talk={a.talk_label}")
        return "\n".join(lines)
