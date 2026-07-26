"""Telegram/Toniva olmadan duman testi."""

from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bot.card_image import render_leaderboard_card
from bot.gender import is_female_name, royal_title
from bot.messages import build_caption
from bot.models import Period
from bot.ranking import build_leaderboard
from bot.toniva_client import (
    MOCK_AGENTS,
    aggregate_conversations_window,
    _talk_seconds_from_row,
)


def test_dates() -> None:
    from bot.dates import parse_day_arg, today_in_tz

    today = today_in_tz("Europe/Istanbul")
    assert parse_day_arg([], timezone="Europe/Istanbul") == today
    assert parse_day_arg(["dün"], timezone="Europe/Istanbul") == today - timedelta(days=1)
    assert parse_day_arg(["26.07.2026"], timezone="Europe/Istanbul") == date(2026, 7, 26)
    print("OK dates")


def test_gender() -> None:
    assert royal_title("umit") == "kral"
    assert royal_title("Elisa") == "kraliçe"
    assert royal_title("Ayşe Yılmaz") == "kraliçe"
    assert royal_title("Mehmet Kaya") == "kral"
    assert not is_female_name("sergen")
    print("OK gender")


def test_window_aggregate() -> None:
    day = date(2026, 7, 26)
    rows = [
        {
            "agentName": "umit",
            "startTime": "2026-07-26T09:15:00",
            "talkSeconds": 120,
        },
        {
            "agentName": "umit",
            "startTime": "2026-07-26T11:50:00",
            "billsec": 300,
        },
        {
            "agentName": "umit",
            "startTime": "2026-07-26T14:00:00",  # öğleden sonra — sabah dilimine girmez
            "talkSeconds": 9999,
        },
        {
            "agentName": "Elisa",
            "startTime": "2026-07-26T10:00:00",
            "talkDuration": "00:05:00",
        },
        {
            "agentName": "Elisa",
            "startTime": "2026-07-26T08:00:00",
            "ringDuration": 50,  # ring sayılmamalı; talk yoksa 0
            "talkSeconds": 600,
        },
    ]
    agents, agg = aggregate_conversations_window(
        rows, day=day, cutoff=time(12, 0, 0), timezone="Europe/Istanbul"
    )
    by = {a.name: a for a in agents}
    assert by["umit"].call_count == 2
    assert by["umit"].talk_seconds == 120 + 300
    assert by["Elisa"].call_count == 2
    assert by["Elisa"].talk_seconds == 300 + 600
    assert agg["rows_in_window"] == 4
    assert agg["rows_out_of_window"] == 1

    # ring-only row
    assert _talk_seconds_from_row({"ringDuration": 99, "ring_time": 10}) == 0
    print("OK window aggregate")


def test_cards_and_messages() -> None:
    out = ROOT / "scripts" / "_smoke_out"
    out.mkdir(parents=True, exist_ok=True)
    board = build_leaderboard(
        MOCK_AGENTS, source="mock", period=Period.SABAH, day=date(2026, 7, 26)
    )
    assert board.window_label == "00:00 – 12:00"
    for period in Period:
        caption = build_caption(board, period)
        assert "kral/kraliçe" not in caption
        # umit mock listesinde — kral geçmeli
        png = render_leaderboard_card(board, period)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        path = out / f"card_{period.value}.png"
        path.write_bytes(png)
        print(f"OK {period.value}: caption={len(caption)} image={path.name}")


async def test_service_mock() -> None:
    from bot.service import MotivationService
    from bot.toniva_client import TonivaClient

    svc = MotivationService(TonivaClient("", "", mock_mode=True))
    board, caption, image = await svc.build(Period.SABAH, day=date(2026, 7, 26))
    assert board.call_leader is not None
    assert "12:00" in board.window_label or "00:00" in board.window_label
    assert len(image) > 1000
    print("OK service mock")


def main() -> None:
    test_dates()
    test_gender()
    test_window_aggregate()
    test_cards_and_messages()
    asyncio.run(test_service_mock())
    print("\nTüm smoke testler geçti.")


if __name__ == "__main__":
    main()
