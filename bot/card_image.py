from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bot.models import Leaderboard, Period

# bg1, bg2, accent, accent2
_PALETTES: dict[
    Period, tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]
] = {
    Period.SABAH: (
        (255, 95, 20),
        (255, 60, 70),
        (255, 200, 60),
        (255, 255, 255),
    ),
    Period.OGLEN: (
        (15, 80, 210),
        (90, 40, 200),
        (80, 220, 255),
        (255, 255, 255),
    ),
    Period.AKSAM: (
        (55, 25, 110),
        (140, 40, 160),
        (255, 170, 80),
        (255, 255, 255),
    ),
}

_WIDTH = 1080
_HEIGHT = 1480
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


def _display_name(name: str) -> str:
    parts = []
    for w in str(name).replace("_", " ").split():
        if not w:
            continue
        parts.append(w[0].upper() + w[1:].lower() if len(w) > 1 else w.upper())
    return " ".join(parts)


def _gradient(
    size: tuple[int, int], c1: tuple[int, int, int], c2: tuple[int, int, int]
) -> Image.Image:
    w, h = size
    base = Image.new("RGB", size, c1)
    px = base.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        # hafif diagonal
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        for x in range(w):
            # soft noise-free diagonal blend
            u = (x / max(w - 1, 1)) * 0.15
            tt = min(1.0, max(0.0, t + u - 0.08))
            px[x, y] = (
                int(c1[0] * (1 - tt) + c2[0] * tt),
                int(c1[1] * (1 - tt) + c2[1] * tt),
                int(c1[2] * (1 - tt) + c2[2] * tt),
            )
    return base


def _draw_orbs(img: Image.Image, accent: tuple[int, int, int]) -> None:
    """Arka plan ışık lekeleri."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    w, h = img.size
    blobs = [
        (int(w * 0.85), int(h * 0.12), 180, 50),
        (int(w * 0.1), int(h * 0.25), 140, 40),
        (int(w * 0.7), int(h * 0.9), 200, 35),
    ]
    for cx, cy, rad, alpha in blobs:
        d.ellipse(
            (cx - rad, cy - rad, cx + rad, cy + rad),
            fill=(*accent, alpha),
        )
    blurred = overlay.filter(ImageFilter.GaussianBlur(40))
    base = img.convert("RGBA")
    img_out = Image.alpha_composite(base, blurred)
    img.paste(img_out.convert("RGB"))


def _truncate(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int
) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    ell = "…"
    while text and draw.textlength(text + ell, font=font) > max_w:
        text = text[:-1]
    return text + ell


def _rank_colors(rank: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    return {
        1: ((255, 205, 40), (50, 35, 0)),
        2: ((200, 210, 220), (40, 45, 55)),
        3: ((220, 150, 80), (50, 30, 10)),
    }.get(rank, ((140, 140, 150), (255, 255, 255)))


def _draw_rank_badge(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    rank: int,
    font: ImageFont.ImageFont,
) -> None:
    fill, ink = _rank_colors(rank)
    x, y = center
    r = 30
    # outer ring
    draw.ellipse((x - r - 3, y - r - 3, x + r + 3, y + r + 3), fill=(255, 255, 255))
    draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)
    label = str(rank)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x - tw / 2, y - th / 2 - 2), label, font=font, fill=ink)


def render_leaderboard_card(board: Leaderboard, period: Period) -> bytes:
    c1, c2, accent, _ = _PALETTES[period]
    img = _gradient((_WIDTH, _HEIGHT), c1, c2)
    try:
        _draw_orbs(img, accent)
    except Exception:
        pass
    draw = ImageDraw.Draw(img)

    title_f = _font(58, bold=True)
    sub_f = _font(26, bold=True)
    section_f = _font(24, bold=True)
    name_f = _font(38, bold=True)
    metric_f = _font(32, bold=True)
    small_f = _font(22)
    badge_f = _font(28, bold=True)
    hero_f = _font(34, bold=True)

    window = board.window_label or period.window_label

    # Header
    draw.text((56, 48), period.title, font=title_f, fill=(255, 255, 255))
    draw.text(
        (56, 120),
        f"{board.date_label}    ·    {window}",
        font=sub_f,
        fill=(255, 255, 255),
    )

    # Hero strip — zirve isimleri
    hero_y = 175
    call = board.call_leader
    talk = board.talk_leader
    hero_box = (40, hero_y, _WIDTH - 40, hero_y + 150)
    draw.rounded_rectangle(hero_box, radius=28, fill=(0, 0, 0, 0))
    # semi-transparent dark glass
    glass = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glass)
    gd.rounded_rectangle(hero_box, radius=28, fill=(20, 15, 30, 90))
    img = Image.alpha_composite(img.convert("RGBA"), glass).convert("RGB")
    draw = ImageDraw.Draw(img)

    if call or talk:
        line1 = ""
        if call:
            line1 = (
                f"ÇAĞRI  ·  {_display_name(call.name).upper()}  ·  {call.call_count}"
            )
        line2 = ""
        if talk:
            line2 = (
                f"SÜRE  ·  {_display_name(talk.name).upper()}  ·  {talk.talk_label}"
            )
        if line1:
            draw.text((64, hero_y + 32), _truncate(draw, line1, hero_f, _WIDTH - 140), font=hero_f, fill=(255, 255, 255))
        if line2:
            draw.text((64, hero_y + 88), _truncate(draw, line2, hero_f, _WIDTH - 140), font=hero_f, fill=accent)
    else:
        draw.text((64, hero_y + 55), "Bu dilimde henüz veri yok", font=hero_f, fill=(255, 255, 255))

    # White panel
    panel_top = 360
    panel = (36, panel_top, _WIDTH - 36, _HEIGHT - 40)
    draw.rounded_rectangle(panel, radius=36, fill=(250, 250, 252))
    # top accent bar on panel
    draw.rounded_rectangle(
        (36, panel_top, _WIDTH - 36, panel_top + 10),
        radius=6,
        fill=accent,
    )

    y = panel_top + 48
    left = 80
    content_w = _WIDTH - left - 80

    def section(
        title: str,
        rows: list[tuple[str, str]],
        accent_color: tuple[int, int, int],
    ) -> int:
        nonlocal y
        # chip
        draw.rounded_rectangle((left, y, left + 12, y + 32), radius=5, fill=accent_color)
        draw.text((left + 26, y + 2), title, font=section_f, fill=(45, 45, 55))
        y += 52

        if not rows:
            draw.text(
                (left + 8, y),
                "Bu dilimde veri yok",
                font=name_f,
                fill=(160, 160, 170),
            )
            y += 72
            return y

        for i, (name, metric) in enumerate(rows):
            rank = i + 1
            row_h = 96
            row_top = y
            row_bot = y + row_h
            # alternating soft rows
            bg = (245, 246, 250) if i % 2 == 0 else (255, 255, 255)
            # gold tint for #1
            if rank == 1:
                bg = (255, 248, 230)
            draw.rounded_rectangle(
                (left - 20, row_top, left + content_w + 20, row_bot),
                radius=20,
                fill=bg,
            )
            # left accent
            if rank == 1:
                draw.rounded_rectangle(
                    (left - 20, row_top + 12, left - 12, row_bot - 12),
                    radius=4,
                    fill=accent_color,
                )

            _draw_rank_badge(draw, (left + 32, row_top + row_h // 2), rank, badge_f)
            name_txt = _truncate(
                draw, _display_name(name), name_f, content_w - 120
            )
            draw.text(
                (left + 78, row_top + 18),
                name_txt,
                font=name_f,
                fill=(25, 25, 35),
            )
            draw.text(
                (left + 78, row_top + 56),
                metric,
                font=metric_f,
                fill=accent_color if rank == 1 else (90, 90, 110),
            )
            y = row_bot + 12

        y += 16
        return y

    call_rows = [
        (_display_name(a.name), f"{a.call_count} çağrı") for a in board.by_calls
    ]
    talk_rows = [(_display_name(a.name), a.talk_label) for a in board.by_talk]

    y = section("EN ÇOK ÇAĞRI", call_rows, c1)
    draw.line((left, y, left + content_w, y), fill=(230, 230, 236), width=2)
    y += 28
    y = section("EN UZUN TOPLAM KONUŞMA", talk_rows, c2)

    # Footer slogan
    slogans = {
        Period.SABAH: "Kimler zirveyi hedefliyor?",
        Period.OGLEN: "Bar yükseldi — devam!",
        Period.AKSAM: "Bugünün efsaneleri bunlar.",
    }
    draw.text(
        (left, _HEIGHT - 100),
        slogans[period],
        font=sub_f,
        fill=(100, 100, 115),
    )
    draw.text(
        (left, _HEIGHT - 62),
        f"Top 3  ·  {window}",
        font=small_f,
        fill=(150, 150, 160),
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
