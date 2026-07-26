"""Telegram/Toniva olmadan kart + metin + ranking duman testi.

Kullanım:
  python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bot.card_image import render_leaderboard_card
from bot.messages import build_caption
from bot.models import Period
from bot.ranking import build_leaderboard
from bot.toniva_client import (
    MOCK_AGENTS,
    parse_conversations_rows,
    parse_performance_rows,
)


def test_parsers() -> None:
    perf = {
        "rows": [
            {
                "agentName": "Ali Veli",
                "callCount": 10,
                "talkSeconds": 3600,
            },
            {
                "agent_name": "Ayşe",
                "calls": 12,
                "talk_duration": "01:30:00",
            },
        ]
    }
    agents = parse_performance_rows(perf)
    assert len(agents) == 2
    by_name = {a.name: a for a in agents}
    assert by_name["Ali Veli"].call_count == 10
    assert by_name["Ayşe"].talk_seconds == 5400

    conv = {
        "data": [
            {"agentName": "Ali Veli", "duration": 100},
            {"agentName": "Ali Veli", "duration": 50},
            {"user_name": "Ayşe", "talkSeconds": 20},
        ]
    }
    agents2 = parse_conversations_rows(conv)
    by_name2 = {a.name: a for a in agents2}
    assert by_name2["Ali Veli"].call_count == 2
    assert by_name2["Ali Veli"].talk_seconds == 150
    print("OK parsers")


def test_cards_and_messages() -> None:
    out = ROOT / "scripts" / "_smoke_out"
    out.mkdir(parents=True, exist_ok=True)
    board = build_leaderboard(
        MOCK_AGENTS, source="mock", period=Period.OGLEN, day=date.today()
    )
    for period in Period:
        caption = build_caption(board, period)
        assert "çağrı" in caption.lower() or "Çağrı" in caption or board.call_leader
        png = render_leaderboard_card(board, period)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        path = out / f"card_{period.value}.png"
        path.write_bytes(png)
        print(f"OK {period.value}: caption={len(caption)} chars, image={path}")


async def test_service_mock() -> None:
    from bot.service import MotivationService
    from bot.toniva_client import TonivaClient

    svc = MotivationService(TonivaClient("", "", mock_mode=True))
    board, caption, image = await svc.build(Period.SABAH)
    assert board.call_leader is not None
    assert len(image) > 1000
    assert len(caption) > 20
    print("OK service mock")


def main() -> None:
    test_parsers()
    test_cards_and_messages()
    asyncio.run(test_service_mock())
    print("\nTüm smoke testler geçti.")


if __name__ == "__main__":
    main()
