from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from bot.card_image import render_leaderboard_card
from bot.messages import build_caption
from bot.models import Leaderboard, Period
from bot.ranking import build_leaderboard
from bot.toniva_client import TonivaClient

logger = logging.getLogger(__name__)


class MotivationService:
    def __init__(self, toniva: TonivaClient, timezone: str = "Europe/Istanbul") -> None:
        self.toniva = toniva
        self.tz = ZoneInfo(timezone)

    async def build(self, period: Period) -> tuple[Leaderboard, str, bytes]:
        now = datetime.now(self.tz)
        day = now.date()
        agents, source = await self.toniva.fetch_agent_stats(day, day)
        board = build_leaderboard(agents, source=source, period=period, day=day)
        caption = build_caption(board, period, now=now)
        image = render_leaderboard_card(board, period)
        logger.info(
            "Leaderboard hazır: period=%s source=%s calls_top=%s talk_top=%s",
            period.value,
            source,
            board.call_leader.name if board.call_leader else None,
            board.talk_leader.name if board.talk_leader else None,
        )
        return board, caption, image
