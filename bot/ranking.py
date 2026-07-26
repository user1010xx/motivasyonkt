from __future__ import annotations

from datetime import date

from bot.models import AgentStats, Leaderboard, Period


def build_leaderboard(
    agents: list[AgentStats],
    *,
    source: str,
    period: Period,
    day: date,
    top_n: int = 3,
) -> Leaderboard:
    active = [a for a in agents if a.call_count > 0 or a.talk_seconds > 0]

    by_calls = sorted(
        active,
        key=lambda a: (a.call_count, a.talk_seconds, a.name.lower()),
        reverse=True,
    )[:top_n]

    by_talk = sorted(
        active,
        key=lambda a: (a.talk_seconds, a.call_count, a.name.lower()),
        reverse=True,
    )[:top_n]

    return Leaderboard(
        by_calls=by_calls,
        by_talk=by_talk,
        source=source,
        period_label=period.label,
        date_label=day.strftime("%d.%m.%Y"),
        window_label=period.window_label,
    )
