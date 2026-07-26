from __future__ import annotations

import random
from datetime import datetime

from bot.models import Leaderboard, Period

# Her dönem + metrik için orijinal şablonlar. {name}, {calls}, {talk}, {date}, {period}
_CALL_TEMPLATES: dict[Period, list[str]] = {
    Period.SABAH: [
        "🔥 {period} ateşi yakıldı!\n\n"
        "📞 <b>Çağrı kralı/kraliçesi: {name}</b>\n"
        "Bugün şimdiye kadar <b>{calls} çağrı</b>.\n\n"
        "Sabah temposu günü belirler — bar yükseldi. Kim yetişecek?",
        "⚡ Güne sprint ile başlayan: <b>{name}</b>\n"
        "<b>{calls}</b> görüşme, henüz günün başı.\n\n"
        "Bu ritim rastgele değil. Odak, hız, disiplin. Devam!",
        "🚀 {date} sabah lideri: <b>{name}</b>\n"
        "Çağrı sayacı: <b>{calls}</b>\n\n"
        "Kahve soğumadan zirveye oturdu. Ekip, tempoyu yakalayın!",
    ],
    Period.OGLEN: [
        "🏆 <b>Öğle zirvesi — çağrı</b>\n\n"
        "<b>{name}</b> şimdiye kadar <b>{calls} çağrı</b> ile önde.\n\n"
        "Öğleden sonra yeni sayfa; liderlik hâlâ açık. Kim barı kıracak?",
        "💥 Öğlen skoru açıklandı!\n"
        "En çok arayan: <b>{name}</b> — <b>{calls}</b>\n\n"
        "Bu tempo sahayı ısıtır. İkinci yarı sizin!",
        "🎯 Hedef avcısı: <b>{name}</b>\n"
        "Günün ortasında <b>{calls} çağrı</b>.\n\n"
        "Sayılar yalan söylemez. Alkış + bir tık daha!",
    ],
    Period.AKSAM: [
        "👑 <b>Akşam tacı — en çok çağrı</b>\n\n"
        "<b>{name}</b> günü <b>{calls} çağrı</b> ile kapattı (şimdiye kadar).\n\n"
        "Bu bir şans değil; bugünün standardı bu. Yarın yeni rekor!",
        "🏁 Bayrak indi, çağrı şampiyonu: <b>{name}</b>\n"
        "Toplam: <b>{calls}</b>\n\n"
        "Bugün ektiğin her arama, yarının güveni. Tebrikler!",
        "🌟 Günün çağrı efsanesi: <b>{name}</b> ({calls})\n\n"
        "Emek görünür oldu. Ekipçe gurur — yarın da aynı ateş!",
    ],
}

_TALK_TEMPLATES: dict[Period, list[str]] = {
    Period.SABAH: [
        "⏱ <b>Konuşmanın mimarı (sabah): {name}</b>\n"
        "Toplam temas: <b>{talk}</b>\n\n"
        "Sayı da önemli ama süre = güven + dinleme + değer. Güçlü başlangıç!",
        "🎧 Sabahın en uzun soluklusu: <b>{name}</b>\n"
        "<b>{talk}</b> müşteriyle gerçek bağ.\n\n"
        "Kaliteli konuşma günü taşır. Böyle devam!",
    ],
    Period.OGLEN: [
        "🎙 <b>Öğle — en uzun konuşma: {name}</b>\n"
        "Süre: <b>{talk}</b>\n\n"
        "Her saniye bir fırsat. İkna, empati, netlik — bu işin sanatı.",
        "💬 Kelimelerin ağırlığı var: <b>{name}</b>\n"
        "Bugün <b>{talk}</b> sahada.\n\n"
        "Süre kralı/kraliçesi tahtta. İkinci yarıda kim yaklaşır?",
    ],
    Period.AKSAM: [
        "🏅 <b>Akşam — konuşma süresi şampiyonu: {name}</b>\n"
        "Toplam: <b>{talk}</b>\n\n"
        "Müşteri sesini en çok duyan sen oldun. Bu, güven inşa eder.",
        "🌙 Günü kapatan ses: <b>{name}</b> — <b>{talk}</b>\n\n"
        "Uzun konuşma = derin ilişki. Alkışlar senin!",
    ],
}

_TEAM_CLOSING = [
    "\n\n💪 Ekip: bar yükseldi. Birlikte daha yükseğe!",
    "\n\n🔥 Bu tempo bulaşıcı — yanındaki arkadaşı da ateşle!",
    "\n\n✨ Bugün efsane gün olabilir. Seçim sizin.",
    "\n\n👏 Emek görünür. Devam, mola sonra!",
]


def _medal(i: int) -> str:
    return {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, "•")


def _top_block(board: Leaderboard) -> str:
    lines = ["\n\n📊 <b>Sıralama (Top 3)</b>"]
    lines.append("📞 <b>Çağrı</b>")
    if not board.by_calls:
        lines.append("  veri yok")
    else:
        for i, a in enumerate(board.by_calls):
            lines.append(f"  {_medal(i)} {a.name} — <b>{a.call_count}</b>")
    lines.append("⏱ <b>Konuşma</b>")
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

    if not call and not talk:
        return (
            f"⚠️ <b>{period.label} motivasyon</b> ({board.date_label})\n\n"
            "Bugün için henüz personel performansı bulunamadı.\n"
            "Toniva verisi gelince liderlik tablosu dolacak."
        )

    parts: list[str] = []
    header = f"🏁 <b>{period.title}</b> · {board.date_label} · {now.strftime('%H:%M')}"
    parts.append(header)

    if call:
        tpl = random.choice(_CALL_TEMPLATES[period])
        parts.append(
            tpl.format(
                name=call.name,
                calls=call.call_count,
                talk=call.talk_label,
                date=board.date_label,
                period=period.label,
            )
        )

    if talk and (not call or talk.name != call.name or talk.talk_seconds != call.talk_seconds):
        tpl = random.choice(_TALK_TEMPLATES[period])
        parts.append(
            "\n\n" + tpl.format(
                name=talk.name,
                calls=talk.call_count,
                talk=talk.talk_label,
                date=board.date_label,
                period=period.label,
            )
        )
    elif talk and call and talk.name == call.name:
        parts.append(
            f"\n\n👑 <b>Duble taç!</b> {call.name} hem çağrı hem konuşma süresinde zirvede."
        )

    parts.append(_top_block(board))
    parts.append(random.choice(_TEAM_CLOSING))

    if board.source == "mock":
        parts.append("\n\n<i>🧪 MOCK veri — gerçek Toniva anahtarı ile canlıya geçer.</i>")

    return "".join(parts)
