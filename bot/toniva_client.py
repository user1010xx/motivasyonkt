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
    "call_total",
    "adet",
    "count",
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
    "duration",
    "durationSeconds",
    "duration_seconds",
    "speakingTime",
    "speaking_time",
    "konusma_suresi",
    "talkDurationSeconds",
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
    # "01:23:45" süre formatı
    if ":" in text and all(p.isdigit() for p in text.split(":")):
        parts = [int(p) for p in text.split(":")]
        if len(parts) == 3:
            h, m, s = parts
            return h * 3600 + m * 60 + s
        if len(parts) == 2:
            m, s = parts
            return m * 60 + s
    try:
        return int(float(text))
    except ValueError:
        return 0


def _as_name(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        nested = _pick(value, _NAME_KEYS)
        if nested:
            return str(nested).strip() or None
        for k in ("name", "label", "title"):
            if value.get(k):
                return str(value[k]).strip() or None
        return None
    text = str(value).strip()
    return text or None


def _extract_rows(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("rows", "data", "items", "results", "agents", "report", "records"):
        val = payload.get(key)
        if isinstance(val, list):
            return [r for r in val if isinstance(r, dict)]
        if isinstance(val, dict):
            nested = _extract_rows(val)
            if nested:
                return nested
    # Bazen { meta, ... } dışında tek liste alanı olur
    for val in payload.values():
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return [r for r in val if isinstance(r, dict)]
    return []


def parse_performance_rows(payload: Any) -> list[AgentStats]:
    """Toniva performance raporunu AgentStats listesine çevirir."""
    rows = _extract_rows(payload)
    agents: dict[str, AgentStats] = {}

    for row in rows:
        name = _as_name(_pick(row, _NAME_KEYS))
        if not name:
            # conversations benzeri satır: agent alanı farklı olabilir
            for k, v in row.items():
                if "agent" in str(k).lower() or "user" in str(k).lower():
                    name = _as_name(v)
                    if name:
                        break
        if not name:
            continue

        calls = _as_int(_pick(row, _CALL_KEYS))
        talk = _as_int(_pick(row, _TALK_KEYS))

        # Konuşma dakikası gelmiş olabilir (küçük sayılar + calls varsa saniye varsay)
        # Eğer talk < 300 ve calls > 0 ve alan adında minute varsa çarp
        talk_raw_key = None
        for k in row:
            if any(x in str(k).lower() for x in ("minute", "dakika")):
                talk_raw_key = k
                break
        if talk_raw_key is not None:
            talk = _as_int(row.get(talk_raw_key)) * 60

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
        name = _as_name(_pick(row, _NAME_KEYS))
        if not name:
            continue
        duration = _as_int(
            _pick(
                row,
                (
                    "talkDuration",
                    "talk_duration",
                    "duration",
                    "billsec",
                    "billableSeconds",
                    "talkSeconds",
                    "durationSeconds",
                ),
            )
        )
        if name not in agents:
            agents[name] = AgentStats(name=name, call_count=0, talk_seconds=0)
        agents[name].call_count += 1
        agents[name].talk_seconds += duration

    return list(agents.values())


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

    # Bilinen CRM kodları (dokümantasyon)
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

    parts = [
        f"Toniva {status} ({endpoint})",
    ]
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

    def _headers(self) -> dict[str, str]:
        # Dokümantasyon: Authorization: Bearer tva_... (önerilen)
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Key": self.api_key,
            "Accept": "application/json",
        }

    async def _get_report(
        self, client: httpx.AsyncClient, slug: str, params: dict[str, str]
    ) -> httpx.Response:
        url = f"{self.base_url}/reports/{slug}"
        resp = await client.get(url, headers=self._headers(), params=params)
        return resp

    async def fetch_agent_stats(
        self, start: date, end: date
    ) -> tuple[list[AgentStats], str]:
        if self.mock_mode or not self.api_key:
            logger.warning("MOCK_MODE aktif — örnek personel verisi kullanılıyor.")
            return list(MOCK_AGENTS), "mock"

        if not self.api_key.startswith("tva_"):
            logger.warning(
                "TONIVA_API_KEY 'tva_' ile başlamıyor — yine de deneniyor."
            )

        params = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            # 1) performance raporu
            perf = await self._get_report(client, "performance", params)
            if perf.status_code == 200:
                perf_body = perf.json()
                agents = parse_performance_rows(perf_body)
                if agents:
                    return agents, "performance"
                logger.warning(
                    "performance 200 ama satır/alan eşleşmedi; conversations deneniyor. "
                    "body_keys=%s",
                    list(perf_body.keys()) if isinstance(perf_body, dict) else type(perf_body),
                )
            elif perf.status_code in (401, 403):
                # Auth hatası — ikinci endpoint de aynı key ile fail olur
                raise _format_toniva_error(perf, "reports/performance")
            elif perf.status_code == 429:
                raise _format_toniva_error(perf, "reports/performance")
            else:
                logger.warning(
                    "performance HTTP %s — conversations yedeği deneniyor.",
                    perf.status_code,
                )

            # 2) yedek: conversations
            conv = await self._get_report(client, "conversations", params)
            if conv.status_code != 200:
                raise _format_toniva_error(conv, "reports/conversations")

            agents = parse_conversations_rows(conv.json())
            if not agents:
                raise TonivaApiError(
                    "Toniva yanıt verdi ama personel satırı çıkmadı. "
                    "Rapor alan adları eşleşmiyor olabilir (reports:read OK görünüyor)."
                )
            return agents, "conversations"
