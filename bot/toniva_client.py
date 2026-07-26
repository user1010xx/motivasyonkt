from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

from bot.models import AgentStats

logger = logging.getLogger(__name__)

# Olası alan adları (API şeması tenant'a göre değişebilir)
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
    "agentLabel",
    "agent_label",
    "memberName",
    "member_name",
    "staffName",
    "staff_name",
    "employeeName",
    "employee_name",
    "firstName",
    "lastName",
)
_CALL_KEYS = (
    "callCount",
    "call_count",
    "calls",
    "totalCalls",
    "total_calls",
    "answeredCalls",
    "answered_calls",
    "connectedCalls",
    "connected_calls",
    "inboundCalls",
    "outboundCalls",
    "call_total",
    "adet",
    "count",
    "total",
    "answered",
    "handled",
    "handledCalls",
    "handled_calls",
    "completedCalls",
    "completed_calls",
)
_TALK_KEYS = (
    "talkDuration",
    "talk_duration",
    "talkTime",
    "talk_time",
    "talkSeconds",
    "talk_seconds",
    "totalTalkTime",
    "total_talk_time",
    "totalTalkDuration",
    "total_talk_duration",
    "billableSeconds",
    "billable_seconds",
    "billsec",
    "duration",
    "durationSeconds",
    "duration_seconds",
    "speakingTime",
    "speaking_time",
    "konusma_suresi",
    "talkDurationSeconds",
    "talk_duration_seconds",
    "totalDuration",
    "total_duration",
    "aht",
    "handleTime",
    "handle_time",
    "talkMin",
    "talk_min",
    "talkMinutes",
    "talk_minutes",
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
    # "01:23:45" veya "1:23" süre formatı
    if ":" in text:
        parts = text.split(":")
        if all(p.strip().replace(".", "", 1).isdigit() for p in parts):
            nums = [int(float(p)) for p in parts]
            if len(nums) == 3:
                h, m, s = nums
                return h * 3600 + m * 60 + s
            if len(nums) == 2:
                m, s = nums
                return m * 60 + s
    # "3 sa 12 dk" kaba parse
    lower = text.lower()
    if "sa" in lower or "dk" in lower or "sn" in lower:
        import re

        h = re.search(r"(\d+)\s*sa", lower)
        m = re.search(r"(\d+)\s*dk", lower)
        s = re.search(r"(\d+)\s*sn", lower)
        total = 0
        if h:
            total += int(h.group(1)) * 3600
        if m:
            total += int(m.group(1)) * 60
        if s:
            total += int(s.group(1))
        if total:
            return total
    try:
        return int(float(text))
    except ValueError:
        return 0


def _as_name(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        nested = _pick(value, _NAME_KEYS)
        if nested is not None and not isinstance(nested, dict):
            text = str(nested).strip()
            if text:
                return text
        # first + last
        first = value.get("firstName") or value.get("first_name") or value.get("ad")
        last = value.get("lastName") or value.get("last_name") or value.get("soyad")
        if first or last:
            return f"{first or ''} {last or ''}".strip() or None
        for k in ("name", "label", "title", "username", "email"):
            if value.get(k):
                return str(value[k]).strip() or None
        return None
    if isinstance(value, (int, float)):
        # Saf id isim değildir
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "undefined", "-"}:
        return None
    return text


def _looks_like_row_list(val: list[Any]) -> bool:
    if not val:
        return True
    return isinstance(val[0], dict)


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    """Toniva rapor gövdesinden satır listesini çıkar (esnek)."""
    if payload is None:
        return []
    if isinstance(payload, list):
        if _looks_like_row_list(payload):
            return [r for r in payload if isinstance(r, dict)]
        return []
    if not isinstance(payload, dict):
        return []

    # Yaygın sarmalayıcılar
    for key in (
        "rows",
        "data",
        "items",
        "results",
        "agents",
        "report",
        "records",
        "payload",
        "content",
        "list",
        "values",
        "performance",
        "conversations",
    ):
        if key not in payload:
            continue
        val = payload[key]
        if isinstance(val, list) and _looks_like_row_list(val):
            return [r for r in val if isinstance(r, dict)]
        if isinstance(val, dict):
            # { "data": { "rows": [...] } }
            nested = _extract_rows(val)
            if nested:
                return nested
            # { "data": { "agentId": { name, calls } } } map formu
            mapped = _rows_from_mapping(val)
            if mapped:
                return mapped

    # columns + rows (matrix)
    if "columns" in payload and "rows" in payload:
        cols = payload["columns"]
        rows = payload["rows"]
        if isinstance(cols, list) and isinstance(rows, list) and rows:
            col_names: list[str] = []
            for c in cols:
                if isinstance(c, str):
                    col_names.append(c)
                elif isinstance(c, dict):
                    col_names.append(
                        str(c.get("key") or c.get("name") or c.get("field") or c)
                    )
                else:
                    col_names.append(str(c))
            out: list[dict[str, Any]] = []
            for r in rows:
                if isinstance(r, dict):
                    out.append(r)
                elif isinstance(r, list):
                    out.append(
                        {
                            col_names[i] if i < len(col_names) else f"c{i}": r[i]
                            for i in range(len(r))
                        }
                    )
            if out:
                return out

    # Herhangi bir dict-list alanı
    for val in payload.values():
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return [r for r in val if isinstance(r, dict)]
        if isinstance(val, dict):
            mapped = _rows_from_mapping(val)
            if mapped:
                return mapped

    # Tek satır gibi duran kök obje (agent alanları doğrudan kökte)
    if any(k in payload for k in _NAME_KEYS) or any(
        "agent" in str(k).lower() for k in payload
    ):
        return [payload]

    return []


def _rows_from_mapping(obj: dict[str, Any]) -> list[dict[str, Any]]:
    """{ id: {metrics...}, id2: {...} } formunu satır listesine çevir."""
    if not obj:
        return []
    # meta benzeri anahtarlar map değildir
    skip = {"meta", "pagination", "page", "total", "count", "success", "status"}
    values = []
    for k, v in obj.items():
        if str(k).lower() in skip:
            continue
        if not isinstance(v, dict):
            return []
        values.append(v)
    if not values:
        return []
    # En az bir value name/metric benzeri alan içermeli
    sample_keys = {str(k).lower() for k in values[0]}
    interesting = any(
        any(x in sk for x in ("name", "agent", "call", "talk", "duration", "user"))
        for sk in sample_keys
    )
    if not interesting:
        return []
    out: list[dict[str, Any]] = []
    for k, v in obj.items():
        if str(k).lower() in skip or not isinstance(v, dict):
            continue
        row = dict(v)
        row.setdefault("_map_key", k)
        out.append(row)
    return out


def _guess_name(row: dict[str, Any]) -> str | None:
    name = _as_name(_pick(row, _NAME_KEYS))
    if name:
        return name

    # firstName + lastName kökte
    first = row.get("firstName") or row.get("first_name") or row.get("ad")
    last = row.get("lastName") or row.get("last_name") or row.get("soyad")
    if first or last:
        return f"{first or ''} {last or ''}".strip() or None

    for k, v in row.items():
        kl = str(k).lower()
        if any(
            x in kl
            for x in (
                "agent",
                "user",
                "operator",
                "personel",
                "staff",
                "member",
                "extension",
                "employee",
            )
        ):
            name = _as_name(v)
            if name:
                return name

    # nested metrics.agent
    for nest_key in ("metrics", "stats", "summary", "agentInfo", "userInfo"):
        nested = row.get(nest_key)
        if isinstance(nested, dict):
            name = _guess_name(nested)
            if name:
                return name

    return None


def _guess_calls_and_talk(row: dict[str, Any]) -> tuple[int, int]:
    # nested metrics
    candidates = [row]
    for nest_key in ("metrics", "stats", "summary", "totals", "data"):
        nested = row.get(nest_key)
        if isinstance(nested, dict):
            candidates.append(nested)

    calls = 0
    talk = 0
    for c in candidates:
        if calls == 0:
            calls = _as_int(_pick(c, _CALL_KEYS))
        if talk == 0:
            talk = _as_int(_pick(c, _TALK_KEYS))
        # dakika alanları
        if talk == 0:
            for k, v in c.items():
                kl = str(k).lower()
                if "minute" in kl or "dakika" in kl:
                    talk = _as_int(v) * 60
                    break

    # Fuzzy: key adında call/talk geçen sayılar
    if calls == 0 or talk == 0:
        for c in candidates:
            for k, v in c.items():
                kl = str(k).lower()
                if calls == 0 and any(
                    x in kl for x in ("call", "cagri", "çağrı", "answered", "handled")
                ):
                    if isinstance(v, (int, float)) or (
                        isinstance(v, str) and v.replace(".", "", 1).isdigit()
                    ):
                        calls = _as_int(v)
                if talk == 0 and any(
                    x in kl
                    for x in (
                        "talk",
                        "duration",
                        "billsec",
                        "speak",
                        "handle_time",
                        "konus",
                    )
                ):
                    talk = _as_int(v)

    return calls, talk


def parse_performance_rows(payload: Any) -> list[AgentStats]:
    """Toniva performance raporunu AgentStats listesine çevirir."""
    rows = _extract_rows(payload)
    agents: dict[str, AgentStats] = {}

    for row in rows:
        name = _guess_name(row)
        if not name:
            continue
        calls, talk = _guess_calls_and_talk(row)
        if name not in agents:
            agents[name] = AgentStats(name=name, call_count=0, talk_seconds=0)
        agents[name].call_count += calls
        agents[name].talk_seconds += talk

    return list(agents.values())


def parse_conversations_rows(payload: Any) -> list[AgentStats]:
    """conversations raporundan agent bazlı toplam üretir (yedek yol)."""
    rows = _extract_rows(payload)
    agents: dict[str, AgentStats] = {}

    for row in rows:
        name = _guess_name(row)
        if not name:
            # agent yoksa yine de atla
            continue
        _, talk = _guess_calls_and_talk(row)
        # conversations satırı genelde 1 çağrı
        calls = _as_int(_pick(row, _CALL_KEYS))
        if calls <= 0:
            calls = 1
        if name not in agents:
            agents[name] = AgentStats(name=name, call_count=0, talk_seconds=0)
        agents[name].call_count += calls
        agents[name].talk_seconds += talk

    return list(agents.values())


def describe_payload(payload: Any) -> str:
    """Log / Telegram debug için kısa özet (PII yok)."""
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
    sample_keys = list(sample.keys())[:30] if isinstance(sample, dict) else []
    # örnek tipler
    types = {
        k: type(sample[k]).__name__
        for k in list(sample.keys())[:12]
        if isinstance(sample, dict)
    }
    return f"satır={len(rows)} üst={top_keys} örnek_alanlar={sample_keys} tipler={types}"


MOCK_AGENTS = [
    AgentStats(name="Ayşe Yılmaz", call_count=52, talk_seconds=3 * 3600 + 18 * 60),
    AgentStats(name="Mehmet Kaya", call_count=47, talk_seconds=3 * 3600 + 42 * 60),
    AgentStats(name="Zeynep Arslan", call_count=61, talk_seconds=2 * 3600 + 55 * 60),
    AgentStats(name="Can Demir", call_count=39, talk_seconds=2 * 3600 + 10 * 60),
    AgentStats(name="Elif Çetin", call_count=44, talk_seconds=2 * 3600 + 48 * 60),
]


class TonivaApiError(RuntimeError):
    """Toniva HTTP / iş kuralı hatası — Telegram'da okunabilir mesaj."""

    def __init__(self, message: str, *, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


def _format_toniva_error(resp: httpx.Response, endpoint: str) -> TonivaApiError:
    status = resp.status_code
    code = None
    message = None
    required_scope = None
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
        "CRM-2091": "API anahtarı geçersiz veya bozuk (tva_... kontrol et).",
        "CRM-2093": "IP whitelist: Railway çıkış IP'si Toniva'da izinli değil.",
        "CRM-2094": "Rate limit aşıldı (100/dk).",
        "CRM-2095": "Tenant pasif veya askıya alınmış.",
        "CRM-2336": "Yetersiz scope — anahtara reports:read ekle.",
        "CRM-4030": "Tenant feature kapalı.",
    }

    if status == 401:
        tip = hints.get(str(code), "Token/key hatalı. TONIVA_API_KEY değerini kontrol et.")
    elif status == 403:
        tip = hints.get(
            str(code),
            "Yetki reddedildi. reports:read scope veya IP whitelist kontrol et.",
        )
    elif status == 429:
        retry = resp.headers.get("Retry-After", "?")
        tip = f"Rate limit. Retry-After: {retry}s"
    else:
        tip = "Toniva isteği başarısız."

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
    def __init__(self, base_url: str, api_key: str, mock_mode: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = (api_key or "").strip()
        self.mock_mode = mock_mode
        # Son başarılı/başarısız yanıt özeti (admin /debug)
        self.last_debug: str = ""

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key,
            "Accept": "application/json",
        }

    async def _get_report(
        self, client: httpx.AsyncClient, slug: str, params: dict[str, str]
    ) -> httpx.Response:
        url = f"{self.base_url}/reports/{slug}"
        return await client.get(url, headers=self._headers(), params=params)

    async def fetch_agent_stats(
        self, start: date, end: date
    ) -> tuple[list[AgentStats], str]:
        """
        Returns (agents, source).
        source: performance | conversations | empty | mock
        Boş gün hata değildir — agents=[] source='empty'.
        """
        if self.mock_mode or not self.api_key:
            logger.warning("MOCK_MODE aktif — örnek personel verisi kullanılıyor.")
            self.last_debug = "mock"
            return list(MOCK_AGENTS), "mock"

        if not self.api_key.startswith("tva_"):
            logger.warning("TONIVA_API_KEY 'tva_' ile başlamıyor — yine de deneniyor.")

        params = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            perf_body: Any = None
            perf_rows: list[dict[str, Any]] = []

            perf = await self._get_report(client, "performance", params)
            if perf.status_code == 200:
                perf_body = perf.json()
                desc = describe_payload(perf_body)
                self.last_debug = f"performance {desc}"
                logger.info("Toniva performance: %s", desc)
                agents = parse_performance_rows(perf_body)
                if agents:
                    return agents, "performance"
                perf_rows = _extract_rows(perf_body)
                if not perf_rows:
                    logger.info("performance satır=0, conversations kontrol ediliyor.")
                else:
                    logger.warning(
                        "performance satır var ama parse edilemedi: %s", desc
                    )
            elif perf.status_code in (401, 403, 429):
                raise _format_toniva_error(perf, "reports/performance")
            else:
                self.last_debug = f"performance HTTP {perf.status_code}"
                logger.warning(
                    "performance HTTP %s — conversations yedeği.", perf.status_code
                )

            conv = await self._get_report(client, "conversations", params)
            if conv.status_code != 200:
                raise _format_toniva_error(conv, "reports/conversations")

            conv_body = conv.json()
            desc = describe_payload(conv_body)
            self.last_debug = (
                f"{self.last_debug} | conversations {desc}"
                if self.last_debug
                else f"conversations {desc}"
            )
            logger.info("Toniva conversations: %s", desc)

            agents = parse_conversations_rows(conv_body)
            if agents:
                return agents, "conversations"

            conv_rows = _extract_rows(conv_body)

            # Her iki taraf da boş satır → gece/veri yok (hata değil)
            if not perf_rows and not conv_rows:
                return [], "empty"

            # Satır var, isim/metric çıkmadı → parse sorunu
            raise TonivaApiError(
                "Toniva satır döndü ama personel alanları okunamadı. "
                f"Özet: {desc}. /debug komutu ile alan adlarını gör."
            )

    async def debug_reports(self, start: date, end: date) -> str:
        """Admin için yapı özeti (PII'siz)."""
        if self.mock_mode or not self.api_key:
            return "MOCK_MODE aktif — gerçek API çağrılmıyor."

        params = {"startDate": start.isoformat(), "endDate": end.isoformat()}
        lines = [f"Tarih: {start} → {end}"]
        async with httpx.AsyncClient(timeout=45.0) as client:
            for slug in ("performance", "conversations"):
                resp = await self._get_report(client, slug, params)
                lines.append(f"\n[{slug}] HTTP {resp.status_code}")
                if resp.status_code != 200:
                    lines.append(str(_format_toniva_error(resp, f"reports/{slug}")))
                    continue
                body = resp.json()
                lines.append(describe_payload(body))
                agents = (
                    parse_performance_rows(body)
                    if slug == "performance"
                    else parse_conversations_rows(body)
                )
                lines.append(f"parse edilen personel: {len(agents)}")
                for a in sorted(agents, key=lambda x: x.call_count, reverse=True)[:5]:
                    lines.append(
                        f"  - {a.name}: calls={a.call_count} talk={a.talk_label}"
                    )
        return "\n".join(lines)
