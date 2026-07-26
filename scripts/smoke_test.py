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
    # Gerçek Toniva conversations şeması (debug çıktısından)
    rows = [
        {
            "ExtensionName": "umit",
            "CreateDate": "2026-07-26",
            "CreateTime": "09:15:00",
            "CallTime": 120,
            "RingTime": 12,
            "WaitTime": 0,
        },
        {
            "ExtensionName": "umit",
            "CreateDate": "2026-07-26",
            "CreateTime": "11:50:40",
            "CallTime": 300,
            "RingTime": 5,
            "WaitTime": 0,
        },
        {
            "ExtensionName": "umit",
            "CreateDate": "2026-07-26",
            "CreateTime": "14:00:00",  # öğleden sonra
            "CallTime": 9999,
            "RingTime": 1,
            "WaitTime": 0,
        },
        {
            "CompletedExtensionName": "Elisa",
            "ExtensionName": "queue",
            "CreateDate": "2026-07-26",
            "CreateTime": "10:00:00",
            "CallTime": 300,
            "RingTime": 8,
            "WaitTime": 0,
        },
        {
            "ExtensionName": "Elisa",
            "CreateDate": "2026-07-26",
            "CreateTime": "08:00:00",
            "CallTime": 600,
            "RingTime": 50,
            "WaitTime": 0,
        },
        # Akşam — sabah dilimi dışı
        {
            "ExtensionName": "night",
            "CreateDate": "2026-07-26",
            "CreateTime": "21:58:40",
            "CallTime": 40,
            "RingTime": 12,
            "WaitTime": 0,
        },
        # CallTime=0 epoch sanılmamalı
        {
            "ExtensionName": "zero",
            "CreateDate": "2026-07-26",
            "CreateTime": "09:30:00",
            "CallTime": 0,
            "RingTime": 12,
            "WaitTime": 0,
        },
    ]
    agents, agg = aggregate_conversations_window(
        rows, day=day, cutoff=time(12, 0, 0), timezone="Europe/Istanbul"
    )
    by = {a.name: a for a in agents}
    assert "night" not in by
    assert by["umit"].call_count == 2
    assert by["umit"].talk_seconds == 120 + 300
    assert by["Elisa"].call_count == 2
    assert by["Elisa"].talk_seconds == 300 + 600
    assert by["zero"].call_count == 1
    assert by["zero"].talk_seconds == 0
    assert agg["rows_out_of_window"] == 2  # 14:00 + 21:58
    assert agg["rows_in_window"] == 5

    # CallTime=0 timestamp olmamalı
    assert _talk_seconds_from_row({"CallTime": 0, "RingTime": 12}) == 0
    assert _talk_seconds_from_row({"CallTime": 90, "RingTime": 5}) == 90
    print("OK window aggregate (Toniva schema)")


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
