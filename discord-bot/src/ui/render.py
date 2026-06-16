from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import os
from typing import Optional

COLOR_MAP = {
    "kirmizi": (210, 35, 35),
    "sari":    (210, 160, 10),
    "mavi":    (25,  90, 200),
    "siyah":   (30,  30,  30),
}
COLOR_LIGHT = {
    "kirmizi": (255, 120, 100),
    "sari":    (255, 220,  80),
    "mavi":    (100, 160, 255),
    "siyah":   (100, 100, 100),
}
BG_TABLE   = (18, 75, 32)
BG_CARD    = (250, 243, 220)
CARD_BORDER= (180, 158, 100)
SHADOW     = (0, 0, 0, 90)
TEXT_GRAY  = (110, 110, 110)
GOLD       = (200, 160, 0)
JOKER_BG   = (240, 225, 255)
JOKER_COL  = (130, 0, 200)

TAS_W = 58
TAS_H = 80
GAP   = 10
PAD   = 14
TOP   = 44

def _font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()

def _draw_tas(draw: ImageDraw.ImageDraw, x: int, y: int,
              sayi: int, renk: str, is_joker: bool = False, is_okey: bool = False,
              idx: int = None):
    """Tek bir taş çizer — ahşap doku + renk efekti."""

    # Gölge
    draw.rounded_rectangle(
        [x + 4, y + 5, x + TAS_W + 4, y + TAS_H + 5],
        radius=8, fill=(0, 0, 0, 60)
    )

    # Kart zemin
    bg = JOKER_BG if is_joker else BG_CARD
    draw.rounded_rectangle([x, y, x + TAS_W, y + TAS_H], radius=8, fill=bg, outline=CARD_BORDER, width=2)

    # Ahşap çizgi detayı (ince yatay çizgiler)
    for ly in range(y + 8, y + TAS_H - 8, 12):
        draw.line([(x + 6, ly), (x + TAS_W - 6, ly)], fill=(220, 205, 175, 50), width=1)

    # Renk şeridi (üst)
    if not is_joker:
        col = COLOR_MAP.get(renk, (80, 80, 80))
        draw.rounded_rectangle([x + 4, y + 4, x + TAS_W - 4, y + 18], radius=4, fill=col)
        # Parlama efekti
        light = COLOR_LIGHT.get(renk, (180, 180, 180))
        draw.line([(x + 8, y + 6), (x + TAS_W - 10, y + 6)], fill=light, width=2)

    # Sayı / metin
    if is_joker:
        txt = "OK"
        col = JOKER_COL
        font = _font(22, bold=True)
    else:
        txt = str(sayi)
        col = COLOR_MAP.get(renk, (40, 40, 40))
        font = _font(28, bold=True) if sayi < 10 else _font(24, bold=True)

    bbox = draw.textbbox((0, 0), txt, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = x + (TAS_W - tw) // 2
    ty = y + 22 + (TAS_H - 28 - th) // 2

    # Metin gölgesi
    draw.text((tx + 1, ty + 1), txt, fill=(0, 0, 0, 50), font=font)
    draw.text((tx, ty), txt, fill=col, font=font)

    # Okey taşı işareti (altın yıldız)
    if is_okey and not is_joker:
        star_font = _font(12)
        draw.text((x + TAS_W - 14, y + TAS_H - 18), "★", fill=GOLD, font=star_font)

    # Sıra numarası (sol alt köşe)
    if idx is not None:
        num_font = _font(10)
        draw.text((x + 3, y + TAS_H - 15), str(idx), fill=TEXT_GRAY, font=num_font)

    # Renk noktası (sağ alt)
    if not is_joker:
        dot_col = COLOR_MAP.get(renk, (80, 80, 80))
        cx = x + TAS_W - 9
        cy = y + TAS_H - 9
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=dot_col, outline=CARD_BORDER, width=1)


def render_el(tas_listesi, okey_tas=None, title: str = "Elinizdeki Taşlar") -> io.BytesIO:
    if not tas_listesi:
        tas_listesi = []

    cols = min(len(tas_listesi), 8)
    if cols == 0:
        cols = 1
    rows = max(1, (len(tas_listesi) + cols - 1) // cols)

    img_w = PAD + cols * (TAS_W + GAP) + PAD + 10
    img_h = TOP + rows * (TAS_H + GAP) + PAD + 10

    # Ana zemin
    img = Image.new("RGBA", (img_w, img_h), BG_TABLE)
    draw = ImageDraw.Draw(img, "RGBA")

    # Çerçeve
    draw.rounded_rectangle([3, 3, img_w - 3, img_h - 3], radius=14, outline=(255, 255, 255, 40), width=1)

    # Başlık
    tfont = _font(14, bold=True)
    draw.text((PAD, 12), title, fill=(255, 255, 255), font=tfont)

    # Okey taşı bilgisi
    if okey_tas:
        renk_emoji_map = {"kirmizi": "🔴", "sari": "🟡", "mavi": "🔵", "siyah": "⚫"}
        re = renk_emoji_map.get(okey_tas.renk, "?")
        ofont = _font(11)
        draw.text((img_w - 120, 14), f"Okey: {re}{okey_tas.sayi}", fill=(255, 215, 0), font=ofont)

    # Taşları çiz
    for i, tas in enumerate(tas_listesi):
        col = i % cols
        row = i // cols
        x = PAD + col * (TAS_W + GAP) + 5
        y = TOP + row * (TAS_H + GAP)

        is_joker = tas.okey
        is_ok_marker = False
        if okey_tas and not tas.okey:
            is_ok_marker = (tas.renk == okey_tas.renk and tas.sayi == okey_tas.sayi)

        _draw_tas(draw, x, y, tas.sayi, tas.renk, is_joker=is_joker, is_okey=is_ok_marker, idx=i + 1)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def render_profil(oyuncu: dict) -> io.BytesIO:
    img_w = 520
    img_h = 300

    img = Image.new("RGBA", (img_w, img_h), (12, 18, 35))
    draw = ImageDraw.Draw(img, "RGBA")

    # Başlık bandı
    draw.rounded_rectangle([0, 0, img_w, 72], radius=14, fill=(18, 88, 52))
    draw.rectangle([0, 58, img_w, 72], fill=(18, 88, 52))

    # Alt kart zemin
    draw.rounded_rectangle([8, 68, img_w - 8, img_h - 8], radius=10, fill=(22, 32, 58), outline=(50, 75, 110), width=1)

    f_xl = _font(20, bold=True)
    f_lg = _font(15, bold=True)
    f_md = _font(13)
    f_sm = _font(11)

    ad = oyuncu.get("ad", "Bilinmiyor")
    seviye = oyuncu.get("seviye", 1)
    draw.text((18, 16), f"🎯  {ad}", fill=(255, 255, 255), font=f_xl)
    draw.text((img_w - 90, 22), f"Sv. {seviye}", fill=(255, 215, 0), font=f_lg)

    cip        = oyuncu.get("cip", 0)
    galibiyet  = oyuncu.get("galibiyet", 0)
    yenilgi    = oyuncu.get("yenilgi", 0)
    beraberlik = oyuncu.get("beraberlik", 0)
    toplam     = oyuncu.get("toplam_mac", 0)
    oran = f"{(galibiyet / toplam * 100):.1f}%" if toplam > 0 else "0%"

    stats = [
        ("🪙  Çip",          f"{cip:,}",       (255, 215, 0)),
        ("🏆  Galibiyet",    str(galibiyet),   (50, 210, 70)),
        ("🟡  Beraberlik",   str(beraberlik),  (200, 170, 0)),
        ("💀  Yenilgi",      str(yenilgi),     (220, 50, 50)),
        ("🎮  Toplam Maç",   str(toplam),      (135, 200, 235)),
        ("📊  Kazanma %",    oran,             (255, 165, 0)),
    ]

    for i, (label, val, color) in enumerate(stats):
        col = i % 3
        row = i // 3
        x = 16 + col * 168
        y = 82 + row * 62
        draw.rounded_rectangle([x, y, x + 156, y + 52], radius=8, fill=(28, 40, 65), outline=(55, 80, 120), width=1)
        draw.text((x + 8, y + 6), label, fill=(150, 170, 200), font=f_sm)
        draw.text((x + 8, y + 24), val, fill=color, font=f_lg)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def render_son_tas(tas, title="Son Atılan Taş") -> io.BytesIO:
    """Tablodaki tek taşı büyük gösterir."""
    img_w = 120
    img_h = 130
    img = Image.new("RGBA", (img_w, img_h), BG_TABLE)
    draw = ImageDraw.Draw(img, "RGBA")
    tfont = _font(11)
    draw.text((8, 8), title, fill=(255, 255, 255), font=tfont)
    _draw_tas(draw, (img_w - TAS_W) // 2, 30, tas.sayi, tas.renk, is_joker=tas.okey)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
