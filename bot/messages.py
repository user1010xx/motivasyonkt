from __future__ import annotations

import random
from datetime import datetime

from bot.gender import royal_title, talk_royal_title
from bot.models import Leaderboard, Period

# {name}, {title}, {talk_title}, {calls}, {talk}, {date}, {period}, {window}
_CALL_TEMPLATES: dict[Period, list[str]] = {
    Period.SABAH: [
        "🔥 {period} ateşi yakıldı! <i>({window})</i>\n\n"
        "📞 Çağrı <b>{title}</b>: <b>{name}</b>\n"
        "Bu dilimde <b>{calls} çağrı</b>.\n\n"
        "Sabah temposu günü belirler — bar yükseldi. Kim yetişecek?",
        "⚡ Sabah diliminin zirvesi: <b>{name}</b> ({title})\n"
        "<b>{calls}</b> görüşme · {window}\n\n"
        "Odak, hız, disiplin. Devam!",
    ],
    Period.OGLEN: [
        "🏆 <b>Öğle zirvesi — çağrı</b> <i>({window})</i>\n\n"
        "Çağrı <b>{title}</b>: <b>{name}</b> — <b>{calls}</b>\n\n"
        "İkinci yarı açık. Kim barı kıracak?",
        "💥 Öğlen skoru!\n"
        "En çok arayan <b>{title}</b>: <b>{name}</b> ({calls})\n"
        "Dilimi: {window}",
    ],
    Period.AKSAM: [
        "👑 <b>Akşam tacı — çağrı</b> <i>({window})</i>\n\n"
        "Çağrı <b>{title}</b>: <b>{name}</b> — <b>{calls}</b>\n\n"
        "Bugünün standardı bu. Yarın yeni rekor!",
        "🏁 Çağrı <b>{title}</b>: <b>{name}</b> ({calls})\n"
        "Tüm gün ({window}) emeği görünür oldu.",
    ],
}

_TALK_TEMPLATES: dict[Period, list[str]] = {
    Period.SABAH: [
        "⏱ Konuşma süresi <b>{talk_title}</b>: <b>{name}</b>\n"
        "Toplam ({window}): <b>{talk}</b>\n\n"
        "Sayı da önemli, toplam süre = güven + değer.",
        "🎧 Sabahın en uzun soluğu: <b>{name}</b>\n"
        "Toplam konuşma: <b>{talk}</b> · {window}",
    ],
    Period.OGLEN: [
        "🎙 Konuşma <b>{talk_title}</b>: <b>{name}</b>\n"
        "Toplam süre: <b>{talk}</b> ({window})",
        "💬 <b>{name}</b> bu dilimde <b>{talk}</b> konuştu.\n"
        "Süre {talk_title} tahtta.",
    ],
    Period.AKSAM: [
        "🏅 Konuşma <b>{talk_title}</b>: <b>{name}</b>\n"
        "Gün boyu toplam: <b>{talk}</b>",
        "🌙 En çok dinleyen ses: <b>{name}</b> — <b>{talk}</b>",
    ],
}

_TEAM_CLOSING = [
    "\n\n💪 Ekip: bar yükseldi. Birlikte daha yükseğe!",
    "\n\n🔥 Bu tempo bulaşıcı — yanındaki arkadaşı da ateşle!",
    "\n\n✨ Bugün efsane gün olabilir. Seçim sizin.",
    "\n\n👏 Emek görünür. Devam!",
]


def _medal(i: int) -> str:
    return {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, "•")


def _top_block(board: Leaderboard) -> str:
    lines = [f"\n\n📊 <b>Sıralama (Top 3)</b> · <i>{board.window_label}</i>"]
    lines.append("📞 <b>Çağrı adedi</b>")
    if not board.by_calls:
        lines.append("  veri yok")
    else:
        for i, a in enumerate(board.by_calls):
            lines.append(f"  {_medal(i)} {a.name} — <b>{a.call_count}</b>")
    lines.append("⏱ <b>Toplam konuşma süresi</b>")
    if not board.by_talk:
        lines.append("  veri yok")
    else:
        for i, a in enumerate(board.by_talk):
            lines.append(f"  {_medal(i)} {a.name} — <b>{a.talk_label}</b>")
    return "\n".join(lines)


def build_caption(board: Leaderboard, period: Period, *, now: datetime | None = None) -> str:
    now = now or datetime.now()
    call = board.call_leader
    talk = board.talk_leader
    window = board.window_label or period.window_label

    if not call and not talk:
        return (
            f"📭 <b>{period.title}</b> · {board.date_label}\n"
            f"Dilimi: <b>{window}</b>\n\n"
            "Bu zaman aralığında çağrı / konuşma skoru yok.\n"
            "Mesai başlayınca veya doğru tarihi deneyince tablo dolar."
        )

    parts: list[str] = [
        f"🏁 <b>{period.title}</b> · {board.date_label}\n"
        f"⏱ Dilim: <b>{window}</b>"
    ]

    if call:
        tpl = random.choice(_CALL_TEMPLATES[period])
        parts.append(
            "\n\n"
            + tpl.format(
                name=call.name,
                title=royal_title(call.name),
                talk_title=talk_royal_title(call.name),
                calls=call.call_count,
                talk=call.talk_label,
                date=board.date_label,
                period=period.label,
                window=window,
            )
        )

    if talk and (not call or talk.name != call.name):
        tpl = random.choice(_TALK_TEMPLATES[period])
        parts.append(
            "\n\n"
            + tpl.format(
                name=talk.name,
                title=royal_title(talk.name),
                talk_title=talk_royal_title(talk.name),
                calls=talk.call_count,
                talk=talk.talk_label,
                date=board.date_label,
                period=period.label,
                window=window,
            )
        )
    elif talk and call and talk.name == call.name:
        t = royal_title(call.name)
        parts.append(
            f"\n\n👑 <b>Duble taç!</b> {call.name} hem çağrı hem "
            f"konuşma süresinde {t}."
        )

    parts.append(_top_block(board))
    parts.append(random.choice(_TEAM_CLOSING))

    if board.source == "mock":
        parts.append("\n\n<i>🧪 MOCK veri</i>")
    elif "window" in board.source:
        parts.append(f"\n\n<i>kaynak: {board.source}</i>")

    return "".join(parts)
