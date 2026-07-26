from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from bot.card_image import render_leaderboard_card
from bot.dates import today_in_tz
from bot.messages import build_caption
from bot.models import Leaderboard, Period, live_window_label, period_for_clock
from bot.ranking import build_leaderboard
from bot.toniva_client import TonivaClient

logger = logging.getLogger(__name__)


class MotivationService:
    def __init__(self, toniva: TonivaClient, timezone: str = "Europe/Istanbul") -> None:
        self.toniva = toniva
        self.tz = ZoneInfo(timezone)
        self.timezone = timezone

    async def build(
        self,
        period: Period,
        *,
        day: date | None = None,
        until_now: bool = False,
    ) -> tuple[Leaderboard, str, bytes]:
        """
        until_now=True → bugün 00:00–şimdi (/gonder).
        Stil saate göre period_for_clock ile seçilir.
        """
        now = datetime.now(self.tz)
        target_day = day or today_in_tz(self.timezone)

        cutoff_override: time | None = None
        window: str | None = None
        period_label: str | None = None

        if until_now:
            period = period_for_clock(now)
            end = (now + timedelta(seconds=1)).time()
            if now.hour == 23 and end.hour == 0:
                end = time(23, 59, 59)
            cutoff_override = end
            window = live_window_label(now)
            period_label = "Canlı"

        agents, source = await self.toniva.fetch_agent_stats(
            target_day,
            period,
            cutoff_override=cutoff_override,
            window_label=window,
        )
        board = build_leaderboard(
            agents,
            source=source,
            period=period,
            day=target_day,
            window_label=window,
            period_label=period_label,
        )
        caption = build_caption(board, period, now=now)
        if until_now:
            caption = caption.replace(
                f"🏁 <b>{period.title}</b>",
                "🏁 <b>CANLI ZİRVE</b>",
                1,
            )

        image = render_leaderboard_card(board, period)
        logger.info(
            "Leaderboard: period=%s day=%s window=%s until_now=%s source=%s "
            "calls_top=%s talk_top=%s",
            period.value,
            target_day.isoformat(),
            board.window_label,
            until_now,
            source,
            board.call_leader.name if board.call_leader else None,
            board.talk_leader.name if board.talk_leader else None,
        )
        return board, caption, image
