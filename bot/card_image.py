from __future__ import annotations

import colorsys
import hashlib
import io
import math
import random
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bot.gender import is_female_name
from bot.models import AgentStats, Leaderboard, Period

_WIDTH = 1200
_HEIGHT = 900
_ASSETS = Path(__file__).resolve().parent / "assets" / "fonts"

# Döneme göre ana renk aileleri (H 0-1)
_PERIOD_HUE: dict[Period, float] = {
    Period.SABAH: 0.08,   # turuncu-altın
    Period.OGLEN: 0.58,   # mavi
    Period.AKSAM: 0.78,   # mor
}


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


def call_royal_label(name: str) -> str:
    if is_female_name(name):
        return "Çağrı adedi kraliçesi"
    return "Çağrı adedi kralı"


def talk_royal_label(name: str) -> str:
    if is_female_name(name):
        return "Konuşma süresi kraliçesi"
    return "Konuşma süresi kralı"


def _hsv(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0, min(1, s)), max(0, min(1, v)))
    return int(r * 255), int(g * 255), int(b * 255)


def _rng_for(board: Leaderboard, period: Period) -> random.Random:
    """Her iletide farklı: zaman + liderler + dönem."""
    raw = (
        f"{board.date_label}|{period.value}|"
        f"{board.call_leader.name if board.call_leader else ''}|"
        f"{board.talk_leader.name if board.talk_leader else ''}|"
        f"{time.time_ns()}"
    )
    seed = int(hashlib.sha256(raw.encode()).hexdigest()[:16], 16)
    return random.Random(seed)


def _gradient_bg(
    rng: random.Random, period: Period
) -> Image.Image:
    base_h = _PERIOD_HUE[period] + rng.uniform(-0.04, 0.04)
    style = rng.randint(0, 3)
    img = Image.new("RGB", (_WIDTH, _HEIGHT))
    px = img.load()

    if style == 0:
        # soft office blue-violet blur feel
        c1 = _hsv(base_h, 0.35, 0.28)
        c2 = _hsv(base_h + 0.08, 0.45, 0.45)
    elif style == 1:
        c1 = _hsv(base_h, 0.55, 0.22)
        c2 = _hsv(base_h - 0.1, 0.4, 0.5)
    elif style == 2:
        c1 = _hsv(base_h + 0.05, 0.25, 0.35)
        c2 = _hsv(base_h + 0.15, 0.5, 0.25)
    else:
        c1 = _hsv(base_h, 0.4, 0.2)
        c2 = _hsv(base_h + 0.12, 0.55, 0.4)

    for y in range(_HEIGHT):
        t = y / max(_HEIGHT - 1, 1)
        for x in range(_WIDTH):
            u = x / max(_WIDTH - 1, 1)
            tt = min(1.0, max(0.0, t * 0.7 + u * 0.3 + rng.random() * 0.0))
            # deterministic-ish without per-pixel rng: use x,y wave
            wave = 0.08 * math.sin(x * 0.01 + y * 0.008)
            tt = min(1.0, max(0.0, tt + wave))
            r = int(c1[0] * (1 - tt) + c2[0] * tt)
            g = int(c1[1] * (1 - tt) + c2[1] * tt)
            b = int(c1[2] * (1 - tt) + c2[2] * tt)
            px[x, y] = (r, g, b)

    # light blobs (bokeh)
    overlay = Image.new("RGBA", (_WIDTH, _HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for _ in range(rng.randint(5, 10)):
        cx = rng.randint(0, _WIDTH)
        cy = rng.randint(0, _HEIGHT)
        rad = rng.randint(40, 160)
        col = (*_hsv(base_h + rng.uniform(-0.1, 0.1), 0.2, 0.9), rng.randint(25, 55))
        od.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=col)
    overlay = overlay.filter(ImageFilter.GaussianBlur(rng.randint(18, 35)))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    return img


def _draw_confetti(draw: ImageDraw.ImageDraw, rng: random.Random, gold: tuple[int, int, int]) -> None:
    for _ in range(rng.randint(45, 80)):
        x = rng.randint(0, _WIDTH)
        y = rng.randint(0, _HEIGHT)
        kind = rng.randint(0, 3)
        col = gold if rng.random() < 0.55 else (
            255,
            255,
            rng.randint(180, 255),
        )
        if kind == 0:
            # rect confetti
            w, h = rng.randint(6, 16), rng.randint(10, 22)
            draw.rectangle((x, y, x + w, y + h), fill=col)
        elif kind == 1:
            r = rng.randint(3, 7)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=col)
        elif kind == 2:
            # star-ish
            r = rng.randint(4, 10)
            draw.polygon(
                [
                    (x, y - r),
                    (x + r * 0.3, y - r * 0.3),
                    (x + r, y),
                    (x + r * 0.3, y + r * 0.3),
                    (x, y + r),
                    (x - r * 0.3, y + r * 0.3),
                    (x - r, y),
                    (x - r * 0.3, y - r * 0.3),
                ],
                fill=col,
            )
        else:
            # ribbon strip
            draw.line(
                (x, y, x + rng.randint(-20, 20), y + rng.randint(15, 40)),
                fill=col,
                width=rng.randint(2, 4),
            )


def _draw_rays(draw: ImageDraw.ImageDraw, rng: random.Random, gold: tuple[int, int, int]) -> None:
    cx, cy = _WIDTH // 2, 80
    for i in range(rng.randint(10, 16)):
        ang = (i / 16) * math.pi + rng.uniform(-0.05, 0.05)
        length = rng.randint(120, 220)
        x2 = cx + int(math.cos(ang) * length)
        y2 = cy + int(math.sin(ang) * length * 0.45)
        draw.line((cx, cy, x2, y2), fill=(*gold, ), width=2)


def _draw_trophy(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    scale: float,
    gold: tuple[int, int, int],
) -> None:
    """Basit kupa ikonu."""
    s = scale
    cup = [
        (cx - 22 * s, cy - 8 * s),
        (cx - 18 * s, cy + 18 * s),
        (cx + 18 * s, cy + 18 * s),
        (cx + 22 * s, cy - 8 * s),
    ]
    draw.polygon(cup, fill=gold)
    draw.ellipse(
        (cx - 24 * s, cy - 28 * s, cx + 24 * s, cy - 4 * s),
        fill=gold,
    )
    # handles
    draw.arc(
        (cx - 38 * s, cy - 22 * s, cx - 10 * s, cy + 10 * s),
        90,
        270,
        fill=gold,
        width=max(2, int(4 * s)),
    )
    draw.arc(
        (cx + 10 * s, cy - 22 * s, cx + 38 * s, cy + 10 * s),
        270,
        90,
        fill=gold,
        width=max(2, int(4 * s)),
    )
    # stem + base
    draw.rectangle(
        (cx - 6 * s, cy + 18 * s, cx + 6 * s, cy + 32 * s),
        fill=gold,
    )
    draw.rectangle(
        (cx - 20 * s, cy + 32 * s, cx + 20 * s, cy + 40 * s),
        fill=gold,
    )


def _rounded_glass(
    base: Image.Image,
    box: tuple[int, int, int, int],
    rng: random.Random,
) -> None:
    """Yarı saydam cam kart."""
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    alpha = rng.randint(150, 190)
    od.rounded_rectangle(box, radius=28, fill=(255, 255, 255, alpha))
    # border
    od.rounded_rectangle(box, radius=28, outline=(255, 255, 255, 220), width=2)
    composed = Image.alpha_composite(base.convert("RGBA"), overlay)
    base.paste(composed.convert("RGB"))


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_size: int,
    max_w: int,
    bold: bool = True,
) -> tuple[ImageFont.ImageFont, str]:
    size = font_size
    while size >= 22:
        font = _font(size, bold=bold)
        if draw.textlength(text, font=font) <= max_w:
            return font, text
        size -= 2
    font = _font(22, bold=bold)
    # truncate
    t = text
    while t and draw.textlength(t + "…", font=font) > max_w:
        t = t[:-1]
    return font, (t + "…") if t != text else t


def _center_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((x - tw / 2, y), text, font=font, fill=fill)


def render_leaderboard_card(board: Leaderboard, period: Period) -> bytes:
    """2 zirve kutlama kartı — her iletide görsel varyasyon."""
    rng = _rng_for(board, period)
    img = _gradient_bg(rng, period)
    draw = ImageDraw.Draw(img)

    gold = _hsv(0.12 + rng.uniform(-0.02, 0.02), 0.55, 0.95)
    gold_dark = _hsv(0.11, 0.65, 0.75)
    cream = (255, 248, 230)
    white = (255, 255, 255)

    # ışınlar + confetti (bazen arkada)
    if rng.random() < 0.85:
        _draw_rays(draw, rng, gold)
    _draw_confetti(draw, rng, gold)

    call = board.call_leader
    talk = board.talk_leader
    window = board.window_label or period.window_label

    # Başlık
    title_font = _font(42, bold=True)
    sub_font = _font(24, bold=True)
    period_titles = {
        Period.SABAH: "Sabah Zirvesi",
        Period.OGLEN: "Öğle Zirvesi",
        Period.AKSAM: "Akşam Zirvesi",
    }
    _center_text(draw, (_WIDTH // 2, 36), period_titles[period].upper(), sub_font, gold)
    _center_text(
        draw,
        (_WIDTH // 2, 70),
        f"{board.date_label}  ·  {window}",
        _font(20),
        (220, 220, 230),
    )

    # TEBRİKLER satırı
    tebrik_font = _font(52, bold=True)
    _center_text(draw, (_WIDTH // 2, 120), "Tebrikler", tebrik_font, cream)

    # İsimler satırı: Name & Name  veya tek isim
    names: list[str] = []
    if call:
        names.append(_display_name(call.name))
    if talk and (not call or talk.name.lower() != call.name.lower()):
        names.append(_display_name(talk.name))
    elif talk and call and talk.name.lower() == call.name.lower():
        # aynı kişi duble
        names = [_display_name(call.name)]

    if not names:
        name_line = "Bugün henüz zirve yok"
    elif len(names) == 1:
        name_line = f"{names[0]}!"
    else:
        joiner = rng.choice([" & ", "  ·  ", "  ✦  "])
        name_line = f"{names[0]}{joiner}{names[1]}!"

    name_font, name_line = _fit_text(draw, name_line, 56, _WIDTH - 100, bold=True)
    _center_text(draw, (_WIDTH // 2, 190), name_line, name_font, cream)

    # İki cam kart
    card_w, card_h = 480, 320
    gap = 40
    total_w = card_w * 2 + gap
    start_x = (_WIDTH - total_w) // 2
    card_y = 320

    slots: list[tuple[str, str, str, AgentStats | None]] = [
        (
            "1",
            call_royal_label(call.name) if call else "Çağrı adedi",
            f"{call.call_count} çağrı" if call else "—",
            call,
        ),
        (
            "2",
            talk_royal_label(talk.name) if talk else "Konuşma süresi",
            talk.talk_label if talk else "—",
            talk,
        ),
    ]

    # layout varyasyonu: yan yana (default) veya hafif offset
    y_offsets = [0, 0]
    if rng.random() < 0.35:
        y_offsets = [rng.randint(-12, 12), rng.randint(-12, 12)]

    for i, (_num, title, metric, agent) in enumerate(slots):
        x0 = start_x + i * (card_w + gap)
        y0 = card_y + y_offsets[i]
        box = (x0, y0, x0 + card_w, y0 + card_h)
        _rounded_glass(img, box, rng)
        draw = ImageDraw.Draw(img)

        # kupa dairesi
        cx = x0 + card_w // 2
        cy = y0 + 70
        draw.ellipse((cx - 42, cy - 42, cx + 42, cy + 42), fill=(255, 255, 255))
        draw.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), fill=(255, 250, 235))
        _draw_trophy(draw, cx, cy + 4, 1.0, gold_dark)

        # unvan
        tfont = _font(20, bold=True)
        _center_text(draw, (cx, y0 + 130), title, tfont, (80, 70, 50))

        # isim
        aname = _display_name(agent.name).upper() if agent else "—"
        nfont, aname = _fit_text(draw, aname, 36, card_w - 40, bold=True)
        _center_text(draw, (cx, y0 + 175), aname, nfont, (30, 30, 40))

        # metrik
        mfont = _font(28, bold=True)
        _center_text(draw, (cx, y0 + 230), metric, mfont, gold_dark)

        # küçük alt etiket
        _center_text(
            draw,
            (cx, y0 + 275),
            "ZİRVE" if i == 0 else "ZİRVE",
            _font(16, bold=True),
            (140, 130, 110),
        )

    # alt alkış satırı
    draw = ImageDraw.Draw(img)
    foot = rng.choice(
        [
            "Tüm ekip sizleri kutluyor  ",
            "Öncüler burada  ",
            "Alkışlar sizin  ",
            "Bu tempo ilham veriyor  ",
        ]
    )
    _center_text(draw, (_WIDTH // 2, _HEIGHT - 70), foot, _font(24, bold=True), cream)
    _center_text(
        draw,
        (_WIDTH // 2, _HEIGHT - 38),
        "Top 3 detayı metinde",
        _font(18),
        (200, 200, 210),
    )

    # üst confetti biraz daha (öne)
    if rng.random() < 0.7:
        _draw_confetti(draw, rng, gold)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
