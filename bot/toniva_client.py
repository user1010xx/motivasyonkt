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


class TonivaClient:
    def __init__(self, base_url: str, api_key: str, mock_mode: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.mock_mode = mock_mode

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    async def fetch_agent_stats(
        self, start: date, end: date
    ) -> tuple[list[AgentStats], str]:
        if self.mock_mode or not self.api_key:
            logger.warning("MOCK_MODE aktif — örnek personel verisi kullanılıyor.")
            return list(MOCK_AGENTS), "mock"

        params = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            # 1) performance raporu
            perf_url = f"{self.base_url}/reports/performance"
            try:
                resp = await client.get(perf_url, headers=self._headers(), params=params)
                if resp.status_code == 429:
                    retry = resp.headers.get("Retry-After", "?")
                    raise RuntimeError(f"Toniva rate limit (429). Retry-After: {retry}s")
                resp.raise_for_status()
                agents = parse_performance_rows(resp.json())
                if agents:
                    return agents, "performance"
                logger.warning(
                    "performance raporu boş veya alanlar eşleşmedi; conversations deneniyor."
                )
            except Exception as exc:
                logger.exception("performance raporu alınamadı: %s", exc)

            # 2) yedek: conversations
            conv_url = f"{self.base_url}/reports/conversations"
            resp = await client.get(conv_url, headers=self._headers(), params=params)
            if resp.status_code == 429:
                retry = resp.headers.get("Retry-After", "?")
                raise RuntimeError(f"Toniva rate limit (429). Retry-After: {retry}s")
            resp.raise_for_status()
            agents = parse_conversations_rows(resp.json())
            if not agents:
                raise RuntimeError(
                    "Toniva'dan personel verisi okunamadı. "
                    "API yanıt alanlarını kontrol edin (reports:read)."
                )
            return agents, "conversations"
