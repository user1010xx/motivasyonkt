from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from bot.models import Leaderboard, Period

# Dönem renk paletleri (üst, alt gradient)
_PALETTES: dict[Period, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    Period.SABAH: ((255, 149, 0), (255, 94, 58)),  # turuncu
    Period.OGLEN: ((0, 122, 255), (88, 86, 214)),  # mavi-mor
    Period.AKSAM: ((88, 86, 214), (175, 82, 222)),  # mor
}

_WIDTH = 1080
_HEIGHT = 1350

_ASSETS = Path(__file__).resolve().parent / "assets" / "fonts"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # Önce repodaki fontlar (Railway'de Türkçe glif için şart)
    bundled = []
    if bold:
        bundled += [
            _ASSETS / "DejaVuSans-Bold.ttf",
            _ASSETS / "arialbd.ttf",
        ]
    bundled += [
        _ASSETS / "DejaVuSans.ttf",
        _ASSETS / "arial.ttf",
    ]
    candidates = [str(p) for p in bundled]
    if bold:
        candidates += [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    candidates += [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _gradient(
    size: tuple[int, int], c1: tuple[int, int, int], c2: tuple[int, int, int]
) -> Image.Image:
    w, h = size
    base = Image.new("RGB", size, c1)
    top = Image.new("RGB", size, c2)
    mask = Image.new("L", size)
    md = ImageDraw.Draw(mask)
    for y in range(h):
        md.line([(0, y), (w, y)], fill=int(255 * (y / max(h - 1, 1))))
    base.paste(top, (0, 0), mask)
    return base


def _truncate(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int
) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    ell = "…"
    while text and draw.textlength(text + ell, font=font) > max_w:
        text = text[:-1]
    return text + ell


def render_leaderboard_card(board: Leaderboard, period: Period) -> bytes:
    c1, c2 = _PALETTES[period]
    img = _gradient((_WIDTH, _HEIGHT), c1, c2)
    draw = ImageDraw.Draw(img)

    title_f = _font(64, bold=True)
    sub_f = _font(32, bold=True)
    name_f = _font(44, bold=True)
    metric_f = _font(40, bold=True)
    small_f = _font(28)
    tiny_f = _font(24)

    # Üst başlık
    draw.text((60, 70), period.title, font=title_f, fill=(255, 255, 255))
    draw.text(
        (60, 150),
        f"{board.date_label}  ·  {board.period_label}",
        font=sub_f,
        fill=(255, 255, 255),
    )

    # Kart paneli
    panel = (48, 230, _WIDTH - 48, _HEIGHT - 80)
    draw.rounded_rectangle(panel, radius=36, fill=(255, 255, 255))

    y = 270
    pad_x = 90

    def section(
        title: str, rows: list[tuple[str, str]], accent: tuple[int, int, int]
    ) -> int:
        nonlocal y
        draw.rounded_rectangle(
            (pad_x - 10, y, pad_x + 18, y + 36), radius=8, fill=accent
        )
        draw.text((pad_x + 36, y - 4), title, font=sub_f, fill=(30, 30, 30))
        y += 60
        if not rows:
            draw.text((pad_x, y), "Veri yok", font=name_f, fill=(120, 120, 120))
            y += 70
            return y
        medals = ["🥇", "🥈", "🥉"]
        for i, (name, metric) in enumerate(rows):
            medal = medals[i] if i < len(medals) else "•"
            line = _truncate(
                draw, f"{medal}  {name}", name_f, _WIDTH - 2 * pad_x - 40
            )
            draw.text((pad_x, y), line, font=name_f, fill=(25, 25, 25))
            y += 52
            draw.text((pad_x + 56, y), metric, font=metric_f, fill=accent)
            y += 70
        y += 20
        return y

    call_rows = [(a.name, f"{a.call_count} çağrı") for a in board.by_calls]
    talk_rows = [(a.name, a.talk_label) for a in board.by_talk]

    y = section("EN ÇOK ÇAĞRI", call_rows, c1)
    draw.line((pad_x, y, _WIDTH - pad_x, y), fill=(230, 230, 230), width=3)
    y += 36
    y = section("EN UZUN KONUŞMA", talk_rows, c2)

    slogan = {
        Period.SABAH: "Güne liderlikle başla.",
        Period.OGLEN: "Bar yükseldi — ikinci yarı senin.",
        Period.AKSAM: "Bugünün efsanesi oldun.",
    }[period]
    draw.text((pad_x, _HEIGHT - 160), slogan, font=small_f, fill=(90, 90, 90))
    src = "demo veri" if board.source == "mock" else f"kaynak: {board.source}"
    draw.text((pad_x, _HEIGHT - 120), src, font=tiny_f, fill=(150, 150, 150))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
