from __future__ import annotations

import hashlib
import random
from datetime import datetime

from bot.models import Leaderboard, Period


def _display_name(name: str) -> str:
    """Kart/metin için isim: baş harfler büyük, Türkçe uyumlu."""
    if not name:
        return ""
    # Basit title; TR karakterler için casefold yerine capitalize kelime kelime
    parts = []
    for w in str(name).replace("_", " ").split():
        if not w:
            continue
        parts.append(w[0].upper() + w[1:].lower() if len(w) > 1 else w.upper())
    return " ".join(parts)


def _seeded_rng(board: Leaderboard, period: Period) -> random.Random:
    """Aynı gün+dönem+liderlerde tutarlı; gün değişince metin değişir."""
    key = (
        f"{board.date_label}|{period.value}|"
        f"{board.call_leader.name if board.call_leader else ''}|"
        f"{board.talk_leader.name if board.talk_leader else ''}"
    )
    seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], 16)
    return random.Random(seed)


# Dönem başlık altı kısa sloganlar
_HEADERS: dict[Period, list[str]] = {
    Period.SABAH: [
        "Sabah ateşi yakıldı",
        "Günün ilk zirvesi belli",
        "Sabah temposu konuşuyor",
        "Kahveyle birlikte liderlik",
        "İlk yarıda öne çıkanlar",
    ],
    Period.OGLEN: [
        "Öğle skoru açıklandı",
        "Günün ortasında bar yükseldi",
        "Öğle zirvesi netleşti",
        "Tempo düşmedi, lider değişti mi?",
        "İkinci yarıya ateşli giriş",
    ],
    Period.AKSAM: [
        "Akşam tacı sahiplerini buldu",
        "Gün biterken efsaneler",
        "Bugünün son skoru",
        "Kapanışta alkışlar",
        "Yarına taşınacak isimler",
    ],
}

_CALL_LINES: dict[Period, list[str]] = {
    Period.SABAH: [
        "⚡️ Sabah diliminin zirvesi: <b>{name}</b>",
        "📞 Çağrıda önde giden: <b>{name}</b>",
        "🚀 En çok arayan: <b>{name}</b>",
        "🔥 Sabahın çağrı yıldızı: <b>{name}</b>",
        "👑 Çağrı tahtında: <b>{name}</b>",
    ],
    Period.OGLEN: [
        "⚡️ Öğle diliminin zirvesi: <b>{name}</b>",
        "📞 Çağrıda bir numara: <b>{name}</b>",
        "🚀 Tempo kralı/kraliçesi: <b>{name}</b>",
        "🔥 Öğlenin çağrı yıldızı: <b>{name}</b>",
    ],
    Period.AKSAM: [
        "⚡️ Günün çağrı zirvesi: <b>{name}</b>",
        "📞 En çok görüşen: <b>{name}</b>",
        "👑 Akşamın çağrı efsanesi: <b>{name}</b>",
        "🏁 Çağrıda bayrağı alan: <b>{name}</b>",
    ],
}

_TALK_LINES: dict[Period, list[str]] = {
    Period.SABAH: [
        "🎧 Sabahın en uzun soluğu: <b>{name}</b>",
        "⏱ Toplam konuşmada zirve: <b>{name}</b>",
        "🎙 En çok dinlenen ses: <b>{name}</b>",
        "💬 Konuşma süresinde önde: <b>{name}</b>",
    ],
    Period.OGLEN: [
        "🎧 Öğlenin en uzun soluğu: <b>{name}</b>",
        "⏱ Konuşmada zirve: <b>{name}</b>",
        "🎙 Müşteriyle en uzun bağ: <b>{name}</b>",
        "💬 Süre tahtında: <b>{name}</b>",
    ],
    Period.AKSAM: [
        "🎧 Günün en uzun soluğu: <b>{name}</b>",
        "⏱ Toplam konuşma zirvesi: <b>{name}</b>",
        "🎙 Akşamın sesi: <b>{name}</b>",
        "💬 Konuşmada efsane: <b>{name}</b>",
    ],
}

_APPLAUSE: list[str] = [
    "Sizler birer öncüsünüz, tüm ekip sizleri kutluyor 👏",
    "Bu tempo ilham veriyor — ekipçe alkış 👏🔥",
    "Öncü isimler belli, kutluyoruz 👏",
    "Siz fark yaratıyorsunuz; tüm ekip gurur duyuyor 👏",
    "Zirve sizin, alkışlar sizin 👏✨",
    "Bu enerji bulaşıcı — tebrikler öncüler 👏💪",
]

_CLOSINGS: list[str] = [
    "Kimler zirveyi hedefliyor?",
    "Sıradaki isim kim olacak?",
    "Bar yükseldi — kim yaklaşacak?",
    "Rekabet kızıştı, hazır mısınız?",
    "Yarın yeni sayfa; bugün kim iz bıraktı?",
    "Zirve boş değil — kovalamaca devam 🔥",
    "Ekipçe yukarı — sıradaki rekor kimin?",
]


def _medal(i: int) -> str:
    return {0: "🥇", 1: "🥈", 2: "🥉"}.get(i, "•")


def _top_block(board: Leaderboard) -> str:
    window = board.window_label or ""
    lines = [f"📊 <b>Sıralama (Top 3)</b> · {window}"]
    lines.append("📞 <b>Çağrı adedi</b>")
    if not board.by_calls:
        lines.append("  veri yok")
    else:
        for i, a in enumerate(board.by_calls):
            lines.append(
                f"  {_medal(i)} {_display_name(a.name)} — <b>{a.call_count}</b>"
            )
    lines.append("⏱ <b>Toplam konuşma süresi</b>")
    if not board.by_talk:
        lines.append("  veri yok")
    else:
        for i, a in enumerate(board.by_talk):
            lines.append(
                f"  {_medal(i)} {_display_name(a.name)} — <b>{a.talk_label}</b>"
            )
    return "\n".join(lines)


def build_caption(board: Leaderboard, period: Period, *, now: datetime | None = None) -> str:
    """Kısa, dikkat çekici, gün/dönem bazlı değişken metin."""
    rng = _seeded_rng(board, period)
    call = board.call_leader
    talk = board.talk_leader
    window = board.window_label or period.window_label

    if not call and not talk:
        return (
            f"🏁 <b>{period.title}</b>\n"
            f"⏱ Dilim: {window} · {board.date_label}\n\n"
            "Bu dilimde henüz skor yok.\n"
            "Çağrılar gelince liderlik tablosu dolacak."
        )

    header_sub = rng.choice(_HEADERS[period])
    parts: list[str] = [
        f"🏁 <b>{period.title}</b>",
        f"<i>{header_sub}</i>",
        f"📅 {board.date_label} · ⏱ {window}",
        "",
    ]

    from bot.gender import is_female_name

    def _call_title(n: str) -> str:
        return "Çağrı adedi kraliçesi" if is_female_name(n) else "Çağrı adedi kralı"

    def _talk_title(n: str) -> str:
        return (
            "Konuşma süresi kraliçesi"
            if is_female_name(n)
            else "Konuşma süresi kralı"
        )

    if call:
        parts.append(
            f"⚡️ <b>{_call_title(call.name)}</b>: "
            f"<b>{_display_name(call.name).upper()}</b>"
        )
        parts.append(f"<b>{call.call_count}</b> görüşme")

    if talk:
        parts.append("")
        if call and talk.name.lower() == call.name.lower():
            parts.append(
                f"👑 <b>Duble zirve!</b> {_display_name(talk.name).upper()} "
                f"hem çağrı hem konuşmada · <b>{talk.talk_label}</b>"
            )
        else:
            parts.append(
                f"🎧 <b>{_talk_title(talk.name)}</b>: "
                f"<b>{_display_name(talk.name).upper()}</b>"
            )
            parts.append(f"Toplam: <b>{talk.talk_label}</b>")

    parts.append("")
    parts.append(rng.choice(_APPLAUSE))
    parts.append("")
    parts.append(_top_block(board))
    parts.append("")
    parts.append(rng.choice(_CLOSINGS))

    if board.source == "mock":
        parts.append("\n<i>🧪 MOCK</i>")

    text = "\n".join(parts)
    # Telegram caption ~1024
    if len(text) > 1000:
        text = text[:997] + "…"
    return text
