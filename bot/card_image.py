from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from bot.models import Leaderboard, Period

_PALETTES: dict[Period, tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]] = {
    # bg1, bg2, accent
    Period.SABAH: ((255, 122, 0), (255, 77, 41), (255, 149, 0)),
    Period.OGLEN: ((20, 90, 200), (70, 60, 200), (0, 122, 255)),
    Period.AKSAM: ((70, 40, 140), (120, 50, 180), (175, 82, 222)),
}

_WIDTH = 1080
_HEIGHT = 1400
_ASSETS = Path(__file__).resolve().parent / "assets" / "fonts"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    bundled = []
    if bold:
        bundled += [_ASSETS / "DejaVuSans-Bold.ttf", _ASSETS / "arialbd.ttf"]
    bundled += [_ASSETS / "DejaVuSans.ttf", _ASSETS / "arial.ttf"]
    candidates = [str(p) for p in bundled]
    if bold:
        candidates += [
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    candidates += [
        "C:/Windows/Fonts/arial.ttf",
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


def _rank_badge(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    rank: int,
    font: ImageFont.ImageFont,
) -> None:
    colors = {
        1: ((255, 196, 0), (40, 30, 0)),
        2: ((180, 190, 200), (30, 30, 35)),
        3: ((205, 140, 70), (40, 25, 10)),
    }
    fill, ink = colors.get(rank, ((120, 120, 120), (255, 255, 255)))
    x, y = xy
    r = 28
    draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)
    label = str(rank)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x - tw / 2, y - th / 2 - 2), label, font=font, fill=ink)


def render_leaderboard_card(board: Leaderboard, period: Period) -> bytes:
    c1, c2, accent = _PALETTES[period]
    img = _gradient((_WIDTH, _HEIGHT), c1, c2)
    draw = ImageDraw.Draw(img)

    title_f = _font(56, bold=True)
    sub_f = _font(28, bold=True)
    section_f = _font(26, bold=True)
    name_f = _font(40, bold=True)
    metric_f = _font(34, bold=True)
    small_f = _font(24)
    badge_f = _font(26, bold=True)

    # Header
    draw.text((64, 56), period.title, font=title_f, fill=(255, 255, 255))
    window = board.window_label or period.window_label
    draw.text(
        (64, 130),
        f"{board.date_label}   ·   {window}",
        font=sub_f,
        fill=(255, 255, 255),
    )
    draw.text(
        (64, 175),
        "Top 3  ·  çağrı adedi  ·  toplam konuşma süresi",
        font=small_f,
        fill=(255, 255, 255),
    )

    # White panel
    panel = (40, 230, _WIDTH - 40, _HEIGHT - 48)
    draw.rounded_rectangle(panel, radius=40, fill=(252, 252, 254))

    # Soft inner shadow line
    draw.rounded_rectangle(
        (40, 230, _WIDTH - 40, 238),
        radius=4,
        fill=(0, 0, 0),
    )

    y = 270
    left = 88
    content_w = _WIDTH - left - 88

    def section(title: str, rows: list[tuple[str, str]], accent_color: tuple[int, int, int]) -> int:
        nonlocal y
        # section chip
        draw.rounded_rectangle(
            (left, y, left + 14, y + 34),
            radius=6,
            fill=accent_color,
        )
        draw.text((left + 28, y + 2), title, font=section_f, fill=(40, 40, 45))
        y += 56

        if not rows:
            draw.text((left + 8, y), "Bu dilimde veri yok", font=name_f, fill=(150, 150, 155))
            y += 80
            return y

        for i, (name, metric) in enumerate(rows):
            rank = i + 1
            # row background
            row_top = y - 8
            row_bot = y + 88
            bg = (248, 248, 251) if i % 2 == 0 else (255, 255, 255)
            draw.rounded_rectangle(
                (left - 16, row_top, left + content_w + 16, row_bot),
                radius=18,
                fill=bg,
            )
            _rank_badge(draw, (left + 28, y + 36), rank, badge_f)
            name_txt = _truncate(draw, name, name_f, content_w - 100)
            draw.text((left + 72, y + 8), name_txt, font=name_f, fill=(28, 28, 32))
            draw.text((left + 72, y + 52), metric, font=metric_f, fill=accent_color)
            y = row_bot + 14

        y += 18
        return y

    call_rows = [(a.name, f"{a.call_count} çağrı") for a in board.by_calls]
    talk_rows = [(a.name, a.talk_label) for a in board.by_talk]

    y = section("EN ÇOK ÇAĞRI", call_rows, accent)
    # divider
    draw.line((left, y, left + content_w, y), fill=(230, 230, 235), width=2)
    y += 28
    y = section("EN UZUN TOPLAM KONUŞMA", talk_rows, c2)

    # Footer
    draw.text(
        (left, _HEIGHT - 110),
        "Toplam konuşma = dilim içindeki tüm görüşmelerin süresi",
        font=small_f,
        fill=(120, 120, 130),
    )
    src = "demo" if board.source == "mock" else board.source
    draw.text(
        (left, _HEIGHT - 72),
        f"kaynak: {src}",
        font=small_f,
        fill=(160, 160, 170),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
