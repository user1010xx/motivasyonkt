"""
Kutlama kartı üretici.

Stil fikirleri (kullanıcı örnekleri):
  1) Alkışlayan eller — beyaz zemin, alt dekor
  2) Altın script tebrik — şık tipografi
  3) Güneş ışını burst
  4) Suluboya splash + script

Her iletide stil + yerleşim + renk varyasyonu seçilir.
Görselde tarih / Top3 yazılmaz (metinde kalır).
"""

from __future__ import annotations

import hashlib
import io
import math
import random
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from bot.gender import is_female_name
from bot.models import AgentStats, Leaderboard, Period

_WIDTH = 1200
_HEIGHT = 900
_ASSETS = Path(__file__).resolve().parent / "assets"
_FONTS = _ASSETS / "fonts"
_REFS = _ASSETS / "style_refs"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates += [
            _FONTS / "DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/seguiemj.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    candidates += [
        _FONTS / "DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/seguiemj.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
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


def _rng(board: Leaderboard, period: Period) -> random.Random:
    raw = f"{time.time_ns()}|{period.value}|{board.date_label}|{random.random()}"
    return random.Random(int(hashlib.sha256(raw.encode()).hexdigest()[:16], 16))


def _load_ref(name: str) -> Image.Image | None:
    path = _REFS / name
    if not path.exists():
        return None
    try:
        return Image.open(path).convert("RGBA")
    except OSError:
        return None


def _fit_contain(im: Image.Image, max_w: int, max_h: int) -> Image.Image:
    im = im.copy()
    im.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    return im


def _center_text(draw, xy, text, font, fill, stroke_fill=None, stroke_width=0):
    x, y = xy
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    kwargs = {"font": font, "fill": fill}
    if stroke_fill and stroke_width:
        kwargs["stroke_fill"] = stroke_fill
        kwargs["stroke_width"] = stroke_width
    draw.text((x - tw / 2, y), text, **kwargs)


def _fit_text(draw, text, size, max_w, bold=True):
    while size >= 18:
        font = _font(size, bold=bold)
        if draw.textlength(text, font=font) <= max_w:
            return font, text
        size -= 2
    font = _font(18, bold=bold)
    t = text
    while t and draw.textlength(t + "…", font=font) > max_w:
        t = t[:-1]
    return font, (t + "…") if t != text else t


def _rounded_rect(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _draw_trophy(draw, cx, cy, s, gold):
    draw.polygon(
        [
            (cx - 18 * s, cy - 6 * s),
            (cx - 14 * s, cy + 14 * s),
            (cx + 14 * s, cy + 14 * s),
            (cx + 18 * s, cy - 6 * s),
        ],
        fill=gold,
    )
    draw.ellipse((cx - 20 * s, cy - 24 * s, cx + 20 * s, cy - 2 * s), fill=gold)
    draw.rectangle((cx - 5 * s, cy + 14 * s, cx + 5 * s, cy + 26 * s), fill=gold)
    draw.rectangle((cx - 16 * s, cy + 26 * s, cx + 16 * s, cy + 32 * s), fill=gold)


def _winner_pair(board: Leaderboard) -> list[tuple[str, str, str, AgentStats | None]]:
    call = board.call_leader
    talk = board.talk_leader
    return [
        (
            call_royal_label(call.name) if call else "Çağrı adedi",
            _display_name(call.name).upper() if call else "—",
            f"{call.call_count} çağrı" if call else "—",
            call,
        ),
        (
            talk_royal_label(talk.name) if talk else "Konuşma süresi",
            _display_name(talk.name).upper() if talk else "—",
            talk.talk_label if talk else "—",
            talk,
        ),
    ]


def _names_line(board: Leaderboard, rng: random.Random) -> str:
    call, talk = board.call_leader, board.talk_leader
    names = []
    if call:
        names.append(_display_name(call.name))
    if talk and (not call or talk.name.lower() != call.name.lower()):
        names.append(_display_name(talk.name))
    elif talk and call and talk.name.lower() == call.name.lower():
        names = [_display_name(call.name)]
    if not names:
        return "Bugün henüz zirve yok"
    if len(names) == 1:
        return f"{names[0]}!"
    return f"{names[0]}{rng.choice([' & ', '  ·  ', ' ve '])}{names[1]}!"


def _draw_two_cards(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    board: Leaderboard,
    rng: random.Random,
    *,
    card_y: int,
    dark: bool = False,
) -> None:
    slots = _winner_pair(board)
    card_w, card_h, gap = 480, 300, 40
    total = card_w * 2 + gap
    x0 = (_WIDTH - total) // 2
    gold = (212, 160, 40)
    gold_d = (160, 110, 20)

    for i, (title, name, metric, _a) in enumerate(slots):
        x = x0 + i * (card_w + gap)
        y = card_y + (rng.randint(-8, 8) if rng.random() < 0.4 else 0)
        if dark:
            fill, ink, sub = (35, 35, 50), (255, 255, 255), (220, 200, 150)
            border = gold
        else:
            fill, ink, sub = (255, 255, 255), (30, 30, 40), (90, 80, 60)
            border = (230, 230, 235)
        # soft shadow
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle(
            (x + 6, y + 8, x + card_w + 6, y + card_h + 8),
            radius=26,
            fill=(0, 0, 0, 40),
        )
        sh = sh.filter(ImageFilter.GaussianBlur(8))
        img.paste(Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB"))
        draw = ImageDraw.Draw(img)

        _rounded_rect(
            draw,
            (x, y, x + card_w, y + card_h),
            26,
            fill,
            outline=border,
            width=3,
        )
        cx = x + card_w // 2
        # trophy circle
        draw.ellipse((cx - 40, y + 22, cx + 40, y + 102), fill=(255, 250, 235), outline=gold, width=3)
        _draw_trophy(draw, cx, y + 68, 1.0, gold_d)

        _center_text(draw, (cx, y + 120), title, _font(18, bold=True), sub)
        nfont, name = _fit_text(draw, name, 34, card_w - 40, bold=True)
        _center_text(draw, (cx, y + 165), name, nfont, ink)
        _center_text(draw, (cx, y + 220), metric, _font(28, bold=True), gold_d)


# ---------- Styles inspired by user examples ----------

def _style_applause(board: Leaderboard, rng: random.Random) -> Image.Image:
    """Alkışlayan eller (ref4) — beyaz zemin, alt dekor."""
    img = Image.new("RGB", (_WIDTH, _HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    hands = _load_ref("ref4.png")
    if hands:
        hands = _fit_contain(hands, _WIDTH - 80, 320)
        # slight recolor warmth
        hx = (_WIDTH - hands.width) // 2
        hy = _HEIGHT - hands.height - 20
        img.paste(hands, (hx, hy), hands)

    # top greeting
    greet = rng.choice(["Tebrikler!", "Bravo!", "Alkışlar!", "Harika!"])
    _center_text(draw, (_WIDTH // 2, 40), greet, _font(56, bold=True), (30, 30, 40))
    names = _names_line(board, rng)
    nfont, names = _fit_text(draw, names, 48, _WIDTH - 100, bold=True)
    _center_text(draw, (_WIDTH // 2, 115), names, nfont, (20, 90, 160))

    _draw_two_cards(img, draw, board, rng, card_y=200, dark=False)
    return img


def _style_script_gold(board: Leaderboard, rng: random.Random) -> Image.Image:
    """Altın script tebrik (ref3) — üst banner + kartlar."""
    img = Image.new("RGB", (_WIDTH, _HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    banner = _load_ref("ref3.png")
    if banner:
        banner = _fit_contain(banner, _WIDTH - 120, 280)
        bx = (_WIDTH - banner.width) // 2
        img.paste(banner, (bx, 20), banner)
    else:
        _center_text(draw, (_WIDTH // 2, 60), "Tebrikler", _font(60, bold=True), (20, 20, 20))
        # gold underline swoosh
        draw.arc((300, 120, 900, 200), 0, 180, fill=(240, 170, 40), width=6)

    names = _names_line(board, rng)
    nfont, names = _fit_text(draw, names, 44, _WIDTH - 80, bold=True)
    _center_text(draw, (_WIDTH // 2, 300), names, nfont, (30, 30, 40))

    # sparkles
    for _ in range(12):
        x, y = rng.randint(80, _WIDTH - 80), rng.randint(40, 280)
        c = (240, 180, 40)
        draw.line((x - 6, y, x + 6, y), fill=c, width=2)
        draw.line((x, y - 6, x, y + 6), fill=c, width=2)

    _draw_two_cards(img, draw, board, rng, card_y=380, dark=False)
    return img


def _style_sunburst(board: Leaderboard, rng: random.Random) -> Image.Image:
    """Güneş ışını (ref1) — ortada banner, altta kartlar."""
    img = Image.new("RGB", (_WIDTH, _HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    burst = _load_ref("ref1.png")
    if burst:
        burst = _fit_contain(burst, 700, 420)
        # lighten / keep
        bx = (_WIDTH - burst.width) // 2
        img.paste(burst, (bx, 10), burst)
    else:
        # procedural sunburst
        cx, cy = _WIDTH // 2, 200
        for i in range(36):
            ang = 2 * math.pi * i / 36
            x2 = cx + int(math.cos(ang) * 280)
            y2 = cy + int(math.sin(ang) * 180)
            draw.line((cx, cy, x2, y2), fill=(255, 150, 40), width=3)
        _center_text(draw, (cx, 160), "Tebrikler", _font(52, bold=True), (20, 50, 70))

    names = _names_line(board, rng)
    nfont, names = _fit_text(draw, names, 42, _WIDTH - 100, bold=True)
    _center_text(draw, (_WIDTH // 2, 380), names, nfont, (20, 50, 70))

    _draw_two_cards(img, draw, board, rng, card_y=450, dark=False)
    return img


def _style_watercolor(board: Leaderboard, rng: random.Random) -> Image.Image:
    """Suluboya splash (ref2)."""
    img = Image.new("RGB", (_WIDTH, _HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    splash = _load_ref("ref2.png")
    if splash:
        splash = _fit_contain(splash, _WIDTH - 60, 420)
        # soft
        splash = ImageEnhance.Brightness(splash).enhance(1.05)
        sx = (_WIDTH - splash.width) // 2
        img.paste(splash, (sx, 10), splash)
    else:
        # procedural blotches
        ov = Image.new("RGBA", (_WIDTH, _HEIGHT), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        colors = [
            (255, 100, 120, 90),
            (255, 180, 80, 90),
            (120, 180, 255, 90),
            (200, 120, 255, 80),
        ]
        for _ in range(14):
            col = rng.choice(colors)
            cx, cy = rng.randint(100, _WIDTH - 100), rng.randint(50, 350)
            rad = rng.randint(40, 140)
            od.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=col)
        ov = ov.filter(ImageFilter.GaussianBlur(15))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        draw = ImageDraw.Draw(img)
        _center_text(draw, (_WIDTH // 2, 160), "Tebrikler", _font(56, bold=True), (40, 20, 50))

    names = _names_line(board, rng)
    nfont, names = _fit_text(draw, names, 44, _WIDTH - 80, bold=True)
    _center_text(draw, (_WIDTH // 2, 360), names, nfont, (40, 20, 50))

    _draw_two_cards(img, draw, board, rng, card_y=430, dark=False)
    return img


def _style_dark_confetti(board: Leaderboard, rng: random.Random) -> Image.Image:
    """Önceki kutlama stili — koyu arka plan + confetti (ek çeşit)."""
    # soft dark gradient
    img = Image.new("RGB", (_WIDTH, _HEIGHT))
    px = img.load()
    for y in range(_HEIGHT):
        t = y / _HEIGHT
        for x in range(_WIDTH):
            px[x, y] = (
                int(30 + 40 * t),
                int(25 + 20 * (1 - t)),
                int(60 + 50 * (1 - abs(x / _WIDTH - 0.5))),
            )
    draw = ImageDraw.Draw(img)
    # confetti
    for _ in range(70):
        x, y = rng.randint(0, _WIDTH), rng.randint(0, _HEIGHT)
        c = rng.choice([(255, 200, 60), (255, 255, 255), (255, 160, 80)])
        draw.rectangle((x, y, x + rng.randint(4, 12), y + rng.randint(6, 16)), fill=c)

    greet = rng.choice(["Tebrikler", "Bravo", "Zirvede", "Harika!"])
    _center_text(draw, (_WIDTH // 2, 50), greet, _font(54, bold=True), (255, 245, 220))
    names = _names_line(board, rng)
    nfont, names = _fit_text(draw, names, 46, _WIDTH - 80, bold=True)
    _center_text(draw, (_WIDTH // 2, 130), names, nfont, (255, 248, 230))

    _draw_two_cards(img, draw, board, rng, card_y=250, dark=False)
    return img


_STYLES = [
    ("applause", _style_applause),
    ("script_gold", _style_script_gold),
    ("sunburst", _style_sunburst),
    ("watercolor", _style_watercolor),
    ("dark_confetti", _style_dark_confetti),
]


def render_leaderboard_card(board: Leaderboard, period: Period) -> bytes:
    rng = _rng(board, period)

    # Döneme hafif ağırlık, ama her seferinde çeşit
    prefer = {
        Period.SABAH: ["applause", "sunburst", "script_gold"],
        Period.OGLEN: ["watercolor", "script_gold", "applause"],
        Period.AKSAM: ["dark_confetti", "watercolor", "sunburst"],
    }[period]

    if rng.random() < 0.65:
        name = rng.choice(prefer)
        fn = dict(_STYLES)[name]
    else:
        name, fn = rng.choice(_STYLES)

    img = fn(board, rng)

    # Empty state overlay note only if no leaders — already in names line
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
