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
    return "Çağrı adedi kraliçesi" if is_female_name(name) else "Çağrı adedi kralı"


def talk_royal_label(name: str) -> str:
    return (
        "Konuşma süresi kraliçesi"
        if is_female_name(name)
        else "Konuşma süresi kralı"
    )


def _hsv(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0, min(1, s)), max(0, min(1, v)))
    return int(r * 255), int(g * 255), int(b * 255)


def _rng(board: Leaderboard, period: Period) -> random.Random:
    raw = f"{time.time_ns()}|{period.value}|{board.date_label}|{random.random()}"
    return random.Random(int(hashlib.sha256(raw.encode()).hexdigest()[:16], 16))


# --- Background styles (görsel olarak belirgin fark) ---

def _bg_blur_office(rng: random.Random) -> Image.Image:
    """Ofis hissi: mavi-gri bokeh (örnek görsele yakın)."""
    img = Image.new("RGB", (_WIDTH, _HEIGHT), (40, 55, 85))
    overlay = Image.new("RGBA", (_WIDTH, _HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for _ in range(18):
        cx, cy = rng.randint(0, _WIDTH), rng.randint(0, _HEIGHT)
        rad = rng.randint(50, 200)
        col = (
            rng.randint(60, 120),
            rng.randint(80, 140),
            rng.randint(120, 200),
            rng.randint(40, 90),
        )
        od.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=col)
    # window light
    od.ellipse((200, -100, 900, 400), fill=(255, 240, 200, 35))
    overlay = overlay.filter(ImageFilter.GaussianBlur(rng.randint(25, 45)))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _bg_night_gold(rng: random.Random) -> Image.Image:
    img = Image.new("RGB", (_WIDTH, _HEIGHT))
    px = img.load()
    for y in range(_HEIGHT):
        t = y / _HEIGHT
        for x in range(_WIDTH):
            u = x / _WIDTH
            r = int(20 + 40 * t + 30 * u)
            g = int(10 + 20 * t)
            b = int(40 + 50 * (1 - t))
            px[x, y] = (r, g, b)
    ov = Image.new("RGBA", (_WIDTH, _HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse((400, -80, 800, 280), fill=(255, 200, 80, 50))
    ov = ov.filter(ImageFilter.GaussianBlur(40))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def _bg_warm_sunrise(rng: random.Random) -> Image.Image:
    img = Image.new("RGB", (_WIDTH, _HEIGHT))
    px = img.load()
    for y in range(_HEIGHT):
        t = y / _HEIGHT
        for x in range(_WIDTH):
            r = int(255 * (0.5 + 0.4 * (1 - t)))
            g = int(120 + 80 * (1 - t) + 20 * (x / _WIDTH))
            b = int(60 + 40 * t)
            px[x, y] = (min(255, r), min(255, g), min(255, b))
    ov = Image.new("RGBA", (_WIDTH, _HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for _ in range(12):
        cx, cy = rng.randint(0, _WIDTH), rng.randint(0, _HEIGHT // 2)
        rad = rng.randint(30, 120)
        od.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=(255, 255, 200, 40))
    ov = ov.filter(ImageFilter.GaussianBlur(30))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def _bg_purple_stage(rng: random.Random) -> Image.Image:
    img = Image.new("RGB", (_WIDTH, _HEIGHT))
    px = img.load()
    for y in range(_HEIGHT):
        t = y / _HEIGHT
        for x in range(_WIDTH):
            u = abs(x / _WIDTH - 0.5) * 2
            r = int(60 + 80 * t)
            g = int(20 + 30 * (1 - u))
            b = int(100 + 100 * (1 - t))
            px[x, y] = (r, g, b)
    return img


def _bg_teal_fresh(rng: random.Random) -> Image.Image:
    img = Image.new("RGB", (_WIDTH, _HEIGHT))
    px = img.load()
    for y in range(_HEIGHT):
        t = y / _HEIGHT
        for x in range(_WIDTH):
            r = int(20 + 40 * t)
            g = int(90 + 80 * (1 - t))
            b = int(100 + 60 * t + 20 * (x / _WIDTH))
            px[x, y] = (r, g, b)
    ov = Image.new("RGBA", (_WIDTH, _HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse((-100, 400, 500, 1000), fill=(0, 255, 200, 30))
    od.ellipse((700, -50, 1400, 500), fill=(100, 200, 255, 35))
    ov = ov.filter(ImageFilter.GaussianBlur(50))
    return Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")


def _make_bg(rng: random.Random, period: Period) -> tuple[Image.Image, str]:
    # Döneme ağırlık + tam rastgele stil
    pool = [
        ("office", _bg_blur_office),
        ("night", _bg_night_gold),
        ("sunrise", _bg_warm_sunrise),
        ("purple", _bg_purple_stage),
        ("teal", _bg_teal_fresh),
    ]
    # dönem tercihi
    prefer = {
        Period.SABAH: ["sunrise", "office"],
        Period.OGLEN: ["office", "teal"],
        Period.AKSAM: ["night", "purple"],
    }[period]
    if rng.random() < 0.55:
        name = rng.choice(prefer)
        fn = dict(pool)[name]
    else:
        name, fn = rng.choice(pool)
    return fn(rng), name


def _draw_confetti(draw: ImageDraw.ImageDraw, rng: random.Random, gold: tuple[int, int, int]) -> None:
    colors = [
        gold,
        (255, 220, 100),
        (255, 255, 255),
        (255, 180, 60),
        (200, 230, 255),
    ]
    for _ in range(rng.randint(50, 100)):
        x, y = rng.randint(0, _WIDTH), rng.randint(0, _HEIGHT)
        col = rng.choice(colors)
        k = rng.randint(0, 4)
        if k == 0:
            w, h = rng.randint(5, 14), rng.randint(8, 20)
            # rotated rect approx
            draw.rectangle((x, y, x + w, y + h), fill=col)
        elif k == 1:
            r = rng.randint(2, 6)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=col)
        elif k == 2:
            draw.line((x, y, x + rng.randint(-25, 25), y + rng.randint(10, 35)), fill=col, width=3)
        elif k == 3:
            r = rng.randint(5, 12)
            draw.polygon(
                [(x, y - r), (x + r * 0.4, y), (x, y + r), (x - r * 0.4, y)],
                fill=col,
            )
        else:
            # small sparkle +
            draw.line((x - 6, y, x + 6, y), fill=col, width=2)
            draw.line((x, y - 6, x, y + 6), fill=col, width=2)


def _draw_rays(draw: ImageDraw.ImageDraw, rng: random.Random, gold: tuple[int, int, int]) -> None:
    cx, cy = _WIDTH // 2, 60
    for i in range(rng.randint(12, 20)):
        ang = (2 * math.pi * i / 18) + rng.uniform(-0.1, 0.1)
        length = rng.randint(100, 260)
        x2 = cx + int(math.cos(ang) * length)
        y2 = cy + int(math.sin(ang) * length * 0.5)
        draw.line((cx, cy, x2, y2), fill=gold, width=rng.randint(1, 3))


def _draw_sparkles(draw: ImageDraw.ImageDraw, rng: random.Random) -> None:
    for _ in range(rng.randint(20, 40)):
        x, y = rng.randint(40, _WIDTH - 40), rng.randint(40, _HEIGHT - 40)
        col = (255, 255, 230)
        s = rng.randint(4, 10)
        draw.line((x - s, y, x + s, y), fill=col, width=2)
        draw.line((x, y - s, x, y + s), fill=col, width=2)


def _draw_trophy(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, scale: float, gold: tuple[int, int, int]
) -> None:
    s = scale
    draw.polygon(
        [
            (cx - 22 * s, cy - 8 * s),
            (cx - 18 * s, cy + 18 * s),
            (cx + 18 * s, cy + 18 * s),
            (cx + 22 * s, cy - 8 * s),
        ],
        fill=gold,
    )
    draw.ellipse((cx - 24 * s, cy - 28 * s, cx + 24 * s, cy - 4 * s), fill=gold)
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
    draw.rectangle((cx - 6 * s, cy + 18 * s, cx + 6 * s, cy + 32 * s), fill=gold)
    draw.rectangle((cx - 20 * s, cy + 32 * s, cx + 20 * s, cy + 40 * s), fill=gold)


def _glass(base: Image.Image, box: tuple[int, int, int, int], rng: random.Random, style: int) -> None:
    ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    if style == 0:
        fill = (255, 255, 255, rng.randint(155, 195))
        outline = (255, 255, 255, 230)
    elif style == 1:
        fill = (20, 20, 35, rng.randint(140, 180))
        outline = (255, 215, 120, 200)
    else:
        fill = (255, 250, 240, rng.randint(160, 200))
        outline = (255, 200, 80, 220)
    od.rounded_rectangle(box, radius=rng.choice([22, 28, 34]), fill=fill, outline=outline, width=2)
    base.paste(Image.alpha_composite(base.convert("RGBA"), ov).convert("RGB"))


def _fit_text(draw, text, font_size, max_w, bold=True):
    size = font_size
    while size >= 20:
        font = _font(size, bold=bold)
        if draw.textlength(text, font=font) <= max_w:
            return font, text
        size -= 2
    font = _font(20, bold=bold)
    t = text
    while t and draw.textlength(t + "…", font=font) > max_w:
        t = t[:-1]
    return font, (t + "…") if t != text else t


def _center_text(draw, xy, text, font, fill):
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((x - tw / 2, y), text, font=font, fill=fill)


def render_leaderboard_card(board: Leaderboard, period: Period) -> bytes:
    """2 zirve kutlama kartı.

    Görselde YOK: tarih, top3 yazısı.
    Her iletide: arka plan stili, layout, dekor, cam stili değişir.
    """
    rng = _rng(board, period)
    img, bg_name = _make_bg(rng, period)
    draw = ImageDraw.Draw(img)

    gold = _hsv(0.12 + rng.uniform(-0.03, 0.03), 0.5 + rng.random() * 0.2, 0.92)
    gold_dark = _hsv(0.11, 0.7, 0.72)
    cream = (255, 248, 230)
    dark_text = (28, 28, 38)
    light_text = (255, 255, 255)

    # Dekor seti
    decor = rng.choice(["confetti_rays", "confetti", "rays_sparkle", "sparkle", "heavy_confetti"])
    if "rays" in decor:
        _draw_rays(draw, rng, gold)
    if "confetti" in decor:
        _draw_confetti(draw, rng, gold)
    if "sparkle" in decor:
        _draw_sparkles(draw, rng)
    if decor == "heavy_confetti":
        _draw_confetti(draw, rng, gold)

    call = board.call_leader
    talk = board.talk_leader

    # --- Başlık (tarih YOK) ---
    greet = rng.choice(["Tebrikler", "Bravo", "Harika!", "Zirvede", "Alkışlar"])
    greet_font = _font(rng.choice([48, 52, 56]), bold=True)
    title_color = cream if bg_name in ("night", "purple", "office", "teal") else dark_text
    if bg_name == "sunrise":
        title_color = (60, 30, 10)

    _center_text(draw, (_WIDTH // 2, 70), greet, greet_font, title_color)

    # İsim satırı
    names: list[str] = []
    if call:
        names.append(_display_name(call.name))
    if talk and (not call or talk.name.lower() != call.name.lower()):
        names.append(_display_name(talk.name))
    elif talk and call and talk.name.lower() == call.name.lower():
        names = [_display_name(call.name)]

    if not names:
        name_line = "Bugün henüz zirve yok"
    elif len(names) == 1:
        name_line = f"{names[0]}!"
    else:
        joiner = rng.choice([" & ", "  ·  ", "  ✦  ", " ve "])
        name_line = f"{names[0]}{joiner}{names[1]}!"

    name_font, name_line = _fit_text(draw, name_line, rng.choice([48, 52, 56]), _WIDTH - 80, bold=True)
    _center_text(draw, (_WIDTH // 2, 145), name_line, name_font, title_color)

    # Layout varyasyonları
    layout = rng.choice(["side", "side", "side_offset", "wide", "compact"])
    glass_style = rng.randint(0, 2)

    if layout == "wide":
        card_w, card_h, gap = 520, 340, 30
    elif layout == "compact":
        card_w, card_h, gap = 440, 300, 50
    else:
        card_w, card_h, gap = 480, 320, 40

    total_w = card_w * 2 + gap
    start_x = (_WIDTH - total_w) // 2
    card_y = 250 if layout != "compact" else 270

    y_off = [0, 0]
    if layout == "side_offset":
        y_off = [rng.randint(-20, 10), rng.randint(-10, 20)]

    slots: list[tuple[str, str, AgentStats | None]] = [
        (
            call_royal_label(call.name) if call else "Çağrı adedi",
            f"{call.call_count} çağrı" if call else "—",
            call,
        ),
        (
            talk_royal_label(talk.name) if talk else "Konuşma süresi",
            talk.talk_label if talk else "—",
            talk,
        ),
    ]

    # metrik rengi cam stiline göre
    metric_color = gold_dark if glass_style != 1 else gold
    label_color = (80, 70, 50) if glass_style != 1 else (220, 210, 180)
    name_color = dark_text if glass_style != 1 else light_text

    for i, (title, metric, agent) in enumerate(slots):
        x0 = start_x + i * (card_w + gap)
        y0 = card_y + y_off[i]
        box = (x0, y0, x0 + card_w, y0 + card_h)
        _glass(img, box, rng, glass_style)
        draw = ImageDraw.Draw(img)

        cx = x0 + card_w // 2
        cy = y0 + 68

        # kupa arka daire stili
        circle_style = rng.randint(0, 2)
        if circle_style == 0:
            draw.ellipse((cx - 44, cy - 44, cx + 44, cy + 44), fill=(255, 255, 255))
            draw.ellipse((cx - 40, cy - 40, cx + 40, cy + 40), fill=(255, 250, 235))
        elif circle_style == 1:
            draw.ellipse((cx - 44, cy - 44, cx + 44, cy + 44), fill=gold)
            draw.ellipse((cx - 36, cy - 36, cx + 36, cy + 36), fill=(255, 255, 255))
        else:
            draw.ellipse((cx - 44, cy - 44, cx + 44, cy + 44), outline=gold, width=4)
            draw.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), fill=(255, 252, 240))

        _draw_trophy(draw, cx, cy + 2, rng.uniform(0.9, 1.15), gold_dark)

        tfont = _font(18, bold=True)
        _center_text(draw, (cx, y0 + 125), title, tfont, label_color)

        aname = _display_name(agent.name).upper() if agent else "—"
        nfont, aname = _fit_text(draw, aname, 34, card_w - 36, bold=True)
        _center_text(draw, (cx, y0 + 168), aname, nfont, name_color)

        mfont = _font(28, bold=True)
        _center_text(draw, (cx, y0 + 225), metric, mfont, metric_color)

    # Alt kutlama (tarih / top3 YOK)
    draw = ImageDraw.Draw(img)
    foot = rng.choice(
        [
            "Tüm ekip sizleri kutluyor",
            "Öncüler burada",
            "Alkışlar sizin",
            "Bu tempo ilham veriyor",
            "Emek görünür oldu",
            "Zirve sizin",
            "Bravo ekip!",
        ]
    )
    foot_color = cream if bg_name in ("night", "purple", "office", "teal") else (50, 40, 30)
    _center_text(draw, (_WIDTH // 2, _HEIGHT - 55), foot, _font(26, bold=True), foot_color)

    # ön plan confetti
    if rng.random() < 0.75:
        _draw_confetti(draw, rng, gold)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
