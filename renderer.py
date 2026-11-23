"""
Tekent Instagram-posts (carrousel, 1080x1350) en een Instagram-story (1080x1920)
in de huisstijl van Gemeentebelangen Urk.

Alles wordt met Pillow getekend, zodat er geen browser of andere zware
software op de server nodig is.
"""
import json
import os
import re
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE, "fonts")
ASSET_DIR = os.path.join(BASE, "assets")

POST_SIZE = (1080, 1350)
STORY_SIZE = (1080, 1920)

NAVY_TOP = (10, 31, 68)
NAVY_BOTTOM = (15, 51, 114)
WHITE = (255, 255, 255, 255)
GREEN = (60, 186, 92)
RED = (226, 31, 38)

# Per rol een lijst lettertypen; het eerste bestand dat in /fonts staat wordt gebruikt.
# Zet je eigen Garet- of Lato Black-bestanden in /fonts om nog dichter bij Canva te komen.
FONT_CANDIDATES = {
    "title": ["Lato-Black.ttf", "OpenSans-ExtraBold.ttf"],
    "label": ["Lato-Italic.ttf"],
    "body": ["Garet-Regular.ttf", "Poppins-Regular.ttf"],
    "body_bold": ["Garet-Bold.ttf", "Poppins-Bold.ttf"],
    "table": ["OpenSans-Regular.ttf"],
    "table_bold": ["OpenSans-Bold.ttf"],
}


def load_config():
    with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=64)
def font_path(role):
    for name in FONT_CANDIDATES[role]:
        path = os.path.join(FONT_DIR, name)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"Geen lettertype gevonden voor '{role}' in {FONT_DIR}")


@lru_cache(maxsize=256)
def font(role, size):
    return ImageFont.truetype(font_path(role), int(size))


@lru_cache(maxsize=32)
def charset(path):
    from fontTools.ttLib import TTFont
    return frozenset(TTFont(path, lazy=True).getBestCmap().keys())


@lru_cache(maxsize=64)
def fallback_font(bold, size):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(FONT_DIR, name), int(size))


def runs_for(word, role, size):
    """Splitst een woord in stukken; tekens die het huisstijl-lettertype mist (zoals →) gaan naar DejaVu."""
    chars = charset(font_path(role))
    f = font(role, size)
    fb = fallback_font("bold" in role or role == "title", size * 0.92)
    out = []
    for ch in word:
        use = f if (ord(ch) in chars or ch.isspace()) else fb
        if out and out[-1][1] is use:
            out[-1][0] += ch
        else:
            out.append([ch, use])
    return out


def text_len(word, role, size):
    return sum(f.getlength(t) for t, f in runs_for(word, role, size))


def draw_word(draw, xy, word, role, size, fill=WHITE, anchor="ls"):
    x, y = xy
    for t, f in runs_for(word, role, size):
        draw.text((x, y), t, font=f, fill=fill, anchor=anchor)
        x += f.getlength(t)


@lru_cache(maxsize=8)
def asset(name):
    return Image.open(os.path.join(ASSET_DIR, name)).convert("RGBA")


# --------------------------------------------------------------------------
# Achtergronden
# --------------------------------------------------------------------------

def gradient(w, h, top=NAVY_TOP, bottom=NAVY_BOTTOM):
    g = Image.linear_gradient("L").resize((w, h))
    return ImageOps.colorize(g, top, bottom).convert("RGBA")


def fade_mask(w, h, fade_part=0.5):
    """Alfamasker: bovenaan transparant, vanaf fade_part volledig zichtbaar."""
    col = Image.new("L", (1, h))
    fade_px = max(1, int(h * fade_part))
    for y in range(h):
        t = min(1.0, y / fade_px)
        t = t * t * (3 - 2 * t)  # zachte overgang
        col.putpixel((0, y), int(255 * t))
    return col.resize((w, h))


def focus_crop(img, w, h, fx, fy, target_y):
    """Schaalt img zodat (w,h) gevuld is en snijdt zo uit dat het focuspunt (fx, fy)
    zo dicht mogelijk op hoogte target_y (0-1) van het venster komt.
    Geeft (uitsnede, werkelijke y-positie van het focuspunt 0-1)."""
    iw, ih = img.size
    sc = max(w / iw, h / ih)
    sw, sh = max(w, round(iw * sc)), max(h, round(ih * sc))
    img = img.resize((sw, sh), Image.LANCZOS)
    left = min(max(fx * sw - w / 2, 0), sw - w)
    top = min(max(fy * sh - target_y * h, 0), sh - h)
    crop = img.crop((round(left), round(top), round(left) + w, round(top) + h))
    return crop, (fy * sh - top) / h


def build_background(size, stijl, foto=None, standaard="haven", focus=None, content_bottom=None):
    """
    stijl: 'onder' (foto onderin, vervaagt naar boven) of 'achtergrond' (hele vlak, blauw getint).
    focus: (x, y) tussen 0 en 1 – waar de hoofden/het belangrijkste deel van de foto zit.
           Dat punt komt altijd in het heldere, niet-vervaagde deel van de foto.
    content_bottom: onderkant van de tekst op deze slide. Bij 'onder' begint de foto pas
           daaronder, zodat hoofden niet achter tekst of de stemtabel verdwijnen.
    """
    w, h = size
    bg = gradient(w, h)
    fx, fy = focus or (0.5, 0.4)
    eigen_foto = foto is not None

    if foto is None and standaard == "golf":
        golf = asset("golf.png")
        gw = w
        gh = int(golf.height * gw / golf.width)
        if h > 1500:  # story: golf iets groter
            gh = int(gh * 1.25)
            gw = int(golf.width * gh / golf.height)
        golf = golf.resize((gw, gh), Image.LANCZOS)
        a = golf.getchannel("A").point(lambda v: int(v * 0.55))
        golf.putalpha(a)
        bg.alpha_composite(golf, ((w - gw) // 2, h - gh))
        return bg

    if foto is None and standaard == "leeg":
        return bg
    if foto is None:
        foto = asset("haven.png")
        fx, fy = 0.5, 0.6
    foto = ImageOps.exif_transpose(foto).convert("RGB")

    if stijl == "achtergrond":
        # Hele achtergrond: blauw getint maar duidelijk doorschijnend, zodat gezichten zichtbaar blijven.
        p, _ = focus_crop(foto, w, h, fx, fy, 0.42)
        p = ImageEnhance.Color(p).enhance(0.5)
        p = Image.blend(p, gradient(w, h, (16, 38, 96), (20, 50, 122)).convert("RGB"), 0.55)
        bg = p.convert("RGBA")
        # alleen bovenin (achter het logo) iets donkerder
        top_h = int(h * 0.22)
        top = Image.new("RGBA", (w, top_h), NAVY_TOP + (0,))
        top.putalpha(fade_mask(w, top_h, 1.0).transpose(Image.FLIP_TOP_BOTTOM).point(lambda v: int(v * 0.45)))
        bg.alpha_composite(top, (0, 0))
        return bg

    # 'onder': foto onderin, bovenkant loopt zacht over in het blauw.
    ph = int(w * 0.66) if h < 1500 else int(h * 0.45)
    if content_bottom is not None:
        room = h - content_bottom + int(ph * 0.12)  # het vervaagde randje mag achter de tekst
        ph = min(ph, room)
        if ph < h * 0.24:
            # Te weinig ruimte onderin (bijv. titelslide met stemtabel).
            if eigen_foto:
                # eigen foto dan over de hele slide, doorzichtig blauw getint
                return build_background(size, "achtergrond", foto, standaard, focus)
            return build_background(size, stijl, None, standaard if standaard == "golf" else "leeg")
    p, fpos = focus_crop(foto, w, ph, fx, fy, 0.62)
    # Het vervaagde deel mag nooit over het focuspunt (de hoofden) heen lopen.
    fade = max(0.12, min(0.45, fpos - 0.2))
    p = Image.blend(p, Image.new("RGB", p.size, (14, 40, 95)), 0.2)
    p = ImageEnhance.Brightness(p).enhance(0.9)
    p = p.convert("RGBA")
    p.putalpha(fade_mask(w, ph, fade))
    bg.alpha_composite(p, (0, h - ph))
    return bg


def paste_logo(img, y, width=384):
    logo = asset("logo.png")
    lh = int(logo.height * width / logo.width)
    logo = logo.resize((width, lh), Image.LANCZOS)
    img.alpha_composite(logo, ((img.width - width) // 2, y))
    return y + lh


def add_text_layer(img, layer):
    """
    Zet de tekstlaag op de achtergrond en zorgt dat tekst altijd leesbaar is:
    alleen waar de achtergrond achter de tekst te licht is, komt een zachte, deels
    doorzichtige donkerblauwe gloed. Op het gewone blauw verandert er niets.
    """
    w, h = img.size
    alpha = layer.getchannel("A")

    # gloed rond de tekst (op kleine schaal berekend, voor snelheid)
    k = 4
    small = alpha.resize((w // k, h // k), Image.BILINEAR)
    halo = small.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(6))
    halo = np.asarray(halo, dtype=np.float32) / 255.0
    halo = np.clip(halo * 1.6, 0, 1)

    # hoe licht is de achtergrond daar? (luminantie, vervaagd zodat het rustig blijft)
    lum = np.asarray(img.convert("L").resize((w // k, h // k), Image.BILINEAR)
                     .filter(ImageFilter.GaussianBlur(5)), dtype=np.float32)
    target = 70.0  # gewenste maximale helderheid achter witte tekst
    need = np.clip(1.0 - target / np.maximum(lum, 1.0), 0.0, 0.8)
    scrim_a = (halo * need * 255).astype(np.uint8)
    scrim_a = Image.fromarray(scrim_a).resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4))
    scrim = Image.new("RGBA", (w, h), (8, 24, 62, 0))
    scrim.putalpha(scrim_a)
    img.alpha_composite(scrim)

    # zachte slagschaduw direct onder de letters
    shadow = Image.new("RGBA", img.size, (0, 10, 35, 0))
    shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.6)))
    img.alpha_composite(shadow, (0, 2))
    img.alpha_composite(layer)


# --------------------------------------------------------------------------
# Tekst
# --------------------------------------------------------------------------

def rich_tokens(text):
    """'**vet**' wordt vet. Geeft ('w', [(stuk, vet), ...]) per woord en ('nl',) voor een harde regelovergang."""
    out, word, bold = [], [], False

    def flush():
        if word:
            out.append(("w", list(word)))
            word.clear()

    i = 0
    while i < len(text):
        if text.startswith("**", i):
            bold = not bold
            i += 2
            continue
        ch = text[i]
        if ch == "\n":
            flush()
            out.append(("nl",))
        elif ch.isspace():
            flush()
        elif word and word[-1][1] == bold:
            word[-1] = (word[-1][0] + ch, bold)
        else:
            word.append((ch, bold))
        i += 1
    flush()
    return out


def word_len(word, size, reg, bold_role):
    return sum(text_len(t, bold_role if b else reg, size) for t, b in word)


def wrap(text, size, maxw, reg="body", bold_role="body_bold"):
    """Breekt (rijke) tekst af. Geeft lijst regels; regel = lijst woorden; woord = lijst (tekst, vet)."""
    space = font(reg, size).getlength(" ")
    lines, cur, curw = [], [], 0.0
    for tok in rich_tokens(text):
        if tok[0] == "nl":
            lines.append(cur)
            cur, curw = [], 0.0
            continue
        word = tok[1]
        ww = word_len(word, size, reg, bold_role)
        add = ww if not cur else space + ww
        if cur and curw + add > maxw:
            lines.append(cur)
            cur, curw = [word], ww
        else:
            cur.append(word)
            curw += add
    if cur:
        lines.append(cur)
    return lines


def line_width(line, size, reg="body", bold_role="body_bold"):
    if not line:
        return 0
    return sum(word_len(w, size, reg, bold_role) for w in line) + font(reg, size).getlength(" ") * (len(line) - 1)


def draw_line(draw, line, x, baseline, size, align="center", reg="body", bold_role="body_bold", fill=WHITE):
    space = font(reg, size).getlength(" ")
    if align == "center":
        x = x - line_width(line, size, reg, bold_role) / 2
    for word in line:
        for t, b in word:
            role = bold_role if b else reg
            draw_word(draw, (x, baseline), t, role, size, fill)
            x += text_len(t, role, size)
        x += space


# --------------------------------------------------------------------------
# Inhoud omzetten naar blokken
# --------------------------------------------------------------------------

ITEM_RE = re.compile(r"^\s*(\d+)\s*[.)]\s*(.*)$")
BULLET_RE = re.compile(r"^\s*[-•*]\s+(.*)$")


def parse_blocks(text):
    """
    Spelregels voor de tekstvakken:
      lege regel        -> nieuwe alinea
      ## Kopje          -> nieuwe slide met kopje
      ---               -> forceer nieuwe slide
      1. tekst          -> genummerd punt (links uitgelijnd)
      - tekst / • tekst -> opsommingsteken (gecentreerd)
      **tekst**         -> vet
    """
    blocks = []
    para = []

    def flush():
        if para:
            blocks.append(("p", "\n".join(para)))
            para.clear()

    for raw in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line:
            flush()
            continue
        if line == "---":
            flush()
            blocks.append(("break",))
            continue
        if line.startswith("#"):
            flush()
            blocks.append(("h", line.lstrip("#").strip()))
            continue
        m = ITEM_RE.match(line)
        if m:
            flush()
            blocks.append(("item", m.group(1) + ".", m.group(2)))
            continue
        m = BULLET_RE.match(line)
        if m:
            flush()
            blocks.append(("bullet", "• " + m.group(1)))
            continue
        # vervolgregel van een genummerd punt (bijv. geplakt uit een pdf)
        if not para and blocks and blocks[-1][0] == "item":
            n, t = blocks[-1][1], blocks[-1][2]
            blocks[-1] = ("item", n, t + " " + line)
            continue
        para.append(line)
    flush()
    return blocks


def list_items(text):
    """Lijstveld: één punt per regel, nummering mag wel of niet getypt zijn."""
    items = []
    blocks = parse_blocks(text)
    n = 0
    for b in blocks:
        if b[0] == "item":
            items.append(b)
            n = int(b[1][:-1])
        elif b[0] in ("p", "bullet"):
            for line in b[1].split("\n"):
                line = line.lstrip("• ").strip()
                if line:
                    n += 1
                    items.append(("item", f"{n}.", line))
    return items


# --------------------------------------------------------------------------
# Opmaak van blokken (meten en tekenen)
# --------------------------------------------------------------------------

class Layout:
    """Maten voor één formaat (post of story)."""

    def __init__(self, size):
        self.w, self.h = size
        self.story = self.h > 1500
        self.textw = 840
        if self.story:
            self.logo_y, self.logo_w = 230, 400
            self.top, self.bottom = 470, 1560
        else:
            self.logo_y, self.logo_w = 138, 384
            self.top, self.bottom = 310, 960
        self.body = 31
        self.heading = 52
        self.closing = 33


def measure_block(block, L, list_size):
    """Geeft lijst 'regels' (dict) met hoogte; alinea's mogen over slides verdeeld worden."""
    kind = block[0]
    rows = []
    if kind == "h":
        size = L.heading
        lh = size * 1.32
        for ln in wrap(block[1], size, L.textw, "body_bold", "body_bold"):
            rows.append(dict(t="text", line=ln, size=size, h=lh, role=("body_bold", "body_bold"), align="center"))
    elif kind in ("p", "bullet", "closing"):
        size = L.closing if kind == "closing" else L.body
        lh = size * 1.42
        for ln in wrap(block[1], size, L.textw):
            rows.append(dict(t="text", line=ln, size=size, h=lh, role=("body", "body_bold"), align="center"))
    elif kind == "item":
        size = list_size
        lh = size * 1.38
        num = block[1]
        indent = font("body", size).getlength(num) + size * 0.4
        lines = wrap(block[2], size, L.textw - indent)
        for i, ln in enumerate(lines):
            rows.append(dict(t="item", num=num if i == 0 else None, line=ln, size=size, h=lh,
                             indent=indent, role=("body", "body_bold")))
    return rows


def gap_before(prev_kind, kind, L, list_size):
    if prev_kind is None:
        return 0
    if prev_kind == "h":
        return L.heading * 0.35
    if kind == "item" and prev_kind == "item":
        return list_size * 0.75
    if kind == "bullet" and prev_kind == "bullet":
        return L.body * 0.35
    return L.body * 1.0


def section_rows(blocks, L, list_size):
    """Zet een reeks blokken om naar regels met tussenruimte."""
    out = []
    prev = None
    for b in blocks:
        rows = measure_block(b, L, list_size)
        if not rows:
            continue
        g = gap_before(prev, b[0], L, list_size)
        for i, r in enumerate(rows):
            r["gap"] = g if i == 0 else 0
            r["kind"] = b[0]
            r["first"] = i == 0
            r["nlines"] = len(rows)
            r["idx"] = i
        out.extend(rows)
        prev = b[0]
    return out


def rows_height(rows):
    return sum(r["gap"] + r["h"] for r in rows)


def paginate(rows, avail):
    """Verdeelt regels over pagina's. Alinea's, koppen en punten blijven zo veel mogelijk heel."""
    # 1. regels groeperen per blok
    blocks, i = [], 0
    while i < len(rows):
        j = i + 1
        while j < len(rows) and not rows[j]["first"]:
            j += 1
        blocks.append(rows[i:j])
        i = j
    # 2. kop altijd samen met het blok erna
    groups, k = [], 0
    while k < len(blocks):
        g = blocks[k]
        if g[0]["kind"] == "h" and k + 1 < len(blocks):
            g = g + blocks[k + 1]
            k += 1
        groups.append(g)
        k += 1
    # 3. te lange groepen alsnog per regel opdelen
    units = []
    for g in groups:
        if rows_height(g) - g[0]["gap"] > avail:
            units.extend([[r] for r in g])
        else:
            units.append(g)
    # 4. vullen
    pages, cur, used = [], [], 0.0
    for g in units:
        gh = rows_height(g) - (g[0]["gap"] if not cur else 0)
        if cur and used + gh > avail:
            pages.append(cur)
            cur, used = [], 0.0
            gh = rows_height(g) - g[0]["gap"]
        if not cur:
            g = [dict(g[0], gap=0)] + g[1:]
        cur.extend(g)
        used += gh
    if cur:
        pages.append(cur)
    return pages


def draw_rows(draw, rows, L, y):
    cx = L.w / 2
    items = [r for r in rows if r["t"] == "item"]
    blockw = max((r["indent"] + line_width(r["line"], r["size"]) for r in items), default=L.textw)
    left = (L.w - min(blockw, L.textw)) / 2
    for r in rows:
        y += r["gap"]
        size = r["size"]
        asc = font(r["role"][0], size).getmetrics()[0]
        base = y + (r["h"] - size * 1.2) / 2 + asc
        if r["t"] == "text":
            draw_line(draw, r["line"], cx, base, size, "center", *r["role"])
        else:
            if r["num"]:
                draw.text((left, base), r["num"], font=font("body", size), fill=WHITE, anchor="ls")
            draw_line(draw, r["line"], left + r["indent"], base, size, "left", *r["role"])
        y += r["h"]
    return y


# --------------------------------------------------------------------------
# Slides
# --------------------------------------------------------------------------

def new_slide(L):
    layer = Image.new("RGBA", (L.w, L.h), (0, 0, 0, 0))
    return layer, ImageDraw.Draw(layer)


def content_bottom(layer):
    box = layer.getbbox()
    return box[3] if box else None


def finish_slide(L, bg, layer):
    """bg is een functie (size, onderkant_tekst) -> achtergrond."""
    img = bg(L.w, L.h, content_bottom(layer)).copy()
    paste_logo(layer, L.logo_y, L.logo_w)  # logo krijgt dezelfde leesbaarheids-gloed als tekst
    add_text_layer(img, layer)
    return img


def fit_title(title, maxw, max_size, min_size, max_lines, maxh):
    size = max_size
    while size >= min_size:
        lines = wrap(title, size, maxw, "title", "title")
        if len(lines) <= max_lines and len(lines) * size * 1.08 <= maxh:
            return size, lines
        size -= 2
    return min_size, wrap(title, min_size, maxw, "title", "title")


def vote_columns(data):
    """Kolommen voor de stemtabel. Staat alles in één kolom en is die lang, dan in tweeën."""
    cols = [(c, k) for c, k in ((data["voor"], "voor"), (data["tegen"], "tegen")) if c]
    if len(cols) == 1 and len(cols[0][0]) > 4:
        c, k = cols[0]
        half = (len(c) + 1) // 2
        cols = [(c[:half], k), (c[half:], k + "_2")]
    return cols


def vote_table_height(data, L, row_h):
    if not data:
        return 0
    rows = max(len(c) for c, _ in vote_columns(data)) if vote_columns(data) else 0
    return 58 * 1.3 + 40 + rows * row_h


def draw_vote_table(draw, layer, data, L, y, row_h):
    cols = vote_columns(data)
    if not cols:
        return y
    icon = int(min(62, row_h * 0.66))
    name_size = int(min(40, row_h * 0.43))
    seat_size = int(name_size * 1.1)
    f_name, f_seat = font("table", name_size), font("table_bold", seat_size)
    name_w = max(f_name.getlength(p["naam"]) for c, _ in cols for p in c)
    seat_w = max(f_seat.getlength(str(p["zetels"])) for c, _ in cols for p in c)
    colw = icon + 24 + max(name_w, f_name.getlength("HVU")) + 48 + seat_w
    gap = 85
    total = colw * len(cols) + gap * (len(cols) - 1)
    x0 = (L.w - total) / 2

    hsize = 58
    f_head = font("table_bold", hsize)
    gesplitst = len(cols) == 2 and cols[1][1].endswith("_2")
    for ci, (c, kind) in enumerate(cols):
        x = x0 + ci * (colw + gap)
        kop = "Voor" if kind.startswith("voor") else "Tegen"
        if gesplitst:
            if ci == 0:
                draw.text((L.w / 2, y + hsize), kop, font=f_head, fill=WHITE, anchor="ms")
        else:
            draw.text((x + colw / 2, y + hsize), kop, font=f_head, fill=WHITE, anchor="ms")
        ry = y + hsize * 1.3 + 40
        for p in c:
            cy = ry + row_h / 2
            draw_icon(layer, int(x), int(cy - icon / 2), icon, kind.startswith("voor"))
            draw.text((x + icon + 24, cy), p["naam"], font=f_name, fill=WHITE, anchor="lm")
            draw.text((x + colw, cy), str(p["zetels"]), font=f_seat, fill=WHITE, anchor="rm")
            ry += row_h
    return y + vote_table_height(data, L, row_h)


def draw_icon(layer, x, y, d, ok):
    s = 4
    big = Image.new("RGBA", (d * s, d * s), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    g.ellipse((0, 0, d * s - 1, d * s - 1), fill=GREEN if ok else RED)
    lw = int(d * s * 0.11)
    D = d * s
    if ok:
        g.line([(D * 0.27, D * 0.52), (D * 0.43, D * 0.67), (D * 0.73, D * 0.36)], fill="white", width=lw, joint="curve")
        for px, py in [(D * 0.27, D * 0.52), (D * 0.73, D * 0.36)]:
            g.ellipse((px - lw / 2, py - lw / 2, px + lw / 2, py + lw / 2), fill="white")
    else:
        for a, b in [((0.32, 0.32), (0.68, 0.68)), ((0.68, 0.32), (0.32, 0.68))]:
            g.line([(D * a[0], D * a[1]), (D * b[0], D * b[1])], fill="white", width=lw)
            for px, py in (a, b):
                g.ellipse((D * px - lw / 2, D * py - lw / 2, D * px + lw / 2, D * py + lw / 2), fill="white")
    small = big.resize((d, d), Image.LANCZOS)
    layer.alpha_composite(small, (x, y))


def cover_elements(data, L, story=False):
    """Bouwt de lijst elementen voor de titelslide/story. Elk element: (hoogte, tekenfunctie)."""
    els = []
    maxh_title = 330 if not story else 420

    label = data.get("label", "").strip()
    if label:
        size = 66 if not story else 72
        f = font("label", size)

        def d_label(draw, layer, y, f=f, size=size):
            draw.text((L.w / 2, y + size * 0.95), label, font=f, fill=WHITE, anchor="ms")
        els.append((size * 1.25, d_label, 4))

    has_vote = data.get("toon_stemming")
    tsize_max = 84 if not has_vote else 66
    if story:
        tsize_max += 8
    tsize, tlines = fit_title(data["titel"], 900, tsize_max, 48, 5, maxh_title)

    def d_title(draw, layer, y, tsize=tsize, tlines=tlines):
        f = font("title", tsize)
        asc = f.getmetrics()[0]
        for i, ln in enumerate(tlines):
            draw_line(draw, ln, L.w / 2, y + asc + i * tsize * 1.08, tsize, "center", "title", "title")
    els.append((len(tlines) * tsize * 1.08 + 6, d_title, 26))

    sub = data.get("ondertitel", "").strip()
    if sub:
        size = 30 if not story else 34
        lines = wrap(sub, size, 860)

        def d_sub(draw, layer, y, lines=lines, size=size):
            asc = font("body", size).getmetrics()[0]
            for i, ln in enumerate(lines):
                draw_line(draw, ln, L.w / 2, y + asc + i * size * 1.35, size)
        els.append((len(lines) * size * 1.35, d_sub, 22))

    if data.get("uitslag"):
        size = 66 if not story else 72
        f = font("label", size)
        txt = data["uitslag"]

        def d_res(draw, layer, y, f=f, size=size, txt=txt):
            draw.text((L.w / 2, y + size * 0.95), txt, font=f, fill=WHITE, anchor="ms")
        els.append((size * 1.25, d_res, 30))

    if has_vote:
        rows = max([len(c) for c, _ in vote_columns(data["stemming"])] + [1])
        used = sum(e[0] + e[2] for e in els)
        limit = (L.h - 70 if not story else 1540) - L.top
        avail = limit - used - (58 * 1.3 + 40) - 20
        row_h = max(44, min(95, avail / rows))

        def d_vote(draw, layer, y, row_h=row_h):
            draw_vote_table(draw, layer, data["stemming"], L, y, row_h)
        els.append((vote_table_height(data["stemming"], L, row_h), d_vote, 10))

    return els


def stack_height(els):
    return sum(h for h, _, _ in els) + sum(g for _, _, g in els[1:])


def draw_stack(draw, layer, els, y):
    for i, (h, fn, g) in enumerate(els):
        if i > 0:
            y += g
        fn(draw, layer, y)
        y += h
    return y


def build_post(data, bg):
    L = Layout(POST_SIZE)
    slides = []

    # 1. titelslide
    layer, draw = new_slide(L)
    els = cover_elements(data, L)
    h = stack_height(els)
    if data.get("toon_stemming"):
        y = L.top
    else:
        y = max(L.top, L.top + (L.bottom - L.top - h) / 2 - 20)
    draw_stack(draw, layer, els, y)
    slides.append(finish_slide(L, bg, layer))

    # 2. secties opbouwen
    sections = []  # lijst van (blokken, is_lijst)
    cur = []
    if data.get("kop"):
        cur.append(("h", data["kop"]))
    tekst_blocks = parse_blocks(data.get("tekst", ""))
    for b in tekst_blocks:
        if b[0] == "break":
            if cur:
                sections.append(cur)
            cur = []
        elif b[0] == "h" and cur and any(x[0] != "h" for x in cur):
            sections.append(cur)
            cur = [b]
        else:
            cur.append(b)

    items = list_items(data.get("lijst", ""))
    has_text = any(b[0] in ("p", "bullet", "item") for b in tekst_blocks)
    if items:
        if has_text:
            if cur:
                sections.append(cur)
            cur = []
            if data.get("lijst_kop"):
                cur.append(("h", data["lijst_kop"]))
        cur.extend(items)
    if cur:
        sections.append(cur)

    avail = L.bottom - L.top
    for sec in sections:
        if not any(b[0] != "h" for b in sec):
            continue
        has_items = any(b[0] == "item" for b in sec)
        pages = None
        if has_items:
            for ls in range(30, 25, -1):
                rows = section_rows(sec, L, ls)
                if rows_height(rows) <= avail:
                    pages = [rows]
                    break
        if pages is None:
            rows = section_rows(sec, L, 29)
            pages = paginate(rows, avail)
        for rows in pages:
            layer, draw = new_slide(L)
            hgt = rows_height(rows)
            y = L.top + max(0, (avail - hgt) / 2 - 15) if len(pages) == 1 else L.top
            draw_rows(draw, rows, L, y)
            slides.append(finish_slide(L, bg, layer))

    # 3. slotslide
    slot = (data.get("slot") or "").strip()
    if slot:
        blocks = [("closing", p[1]) if p[0] == "p" else p for p in parse_blocks(slot) if p[0] != "break"]
        rows = section_rows(blocks, L, 27)
        for page in paginate(rows, avail):
            layer, draw = new_slide(L)
            hgt = rows_height(page)
            y = L.top + max(0, (avail - hgt) / 2 - 60)
            draw_rows(draw, page, L, y)
            slides.append(finish_slide(L, bg, layer))

    return slides


def strip_markup(text):
    blocks = parse_blocks(text)
    for b in blocks:
        if b[0] == "p":
            return b[1].replace("**", "").replace("\n", " ")
    for b in blocks:
        if b[0] in ("bullet", "item"):
            return b[-1].replace("**", "")
    return ""


def build_story(data, bg):
    L = Layout(STORY_SIZE)
    layer, draw = new_slide(L)
    els = cover_elements(data, L, story=True)

    # Zonder stemming: korte samenvatting onder de titel
    if not data.get("toon_stemming"):
        teaser = data.get("story_tekst") or strip_markup(data.get("tekst", "")) or strip_markup(data.get("lijst", ""))
        if teaser and not data.get("ondertitel"):
            size = 34
            lines = wrap(teaser, size, 860)
            used = stack_height(els)
            max_lines = int(max(0, (1420 - L.top - used - 40) // (size * 1.42)))
            max_lines = min(max_lines, 8)
            if max_lines >= 2:
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                    last = list(lines[-1])
                    while len(last) > 1 and line_width(last + [[("…", False)]], size) > 860:
                        last.pop()
                    t, b = last[-1][-1]
                    last[-1] = last[-1][:-1] + [(t.rstrip(".,;:") + "…", b)]
                    lines[-1] = last

                def d_teaser(draw, layer, y, lines=lines, size=size):
                    asc = font("body", size).getmetrics()[0]
                    for i, ln in enumerate(lines):
                        draw_line(draw, ln, L.w / 2, y + asc + i * size * 1.42, size)
                els.append((len(lines) * size * 1.42, d_teaser, 44))

    h = stack_height(els)
    if data.get("toon_stemming"):
        y = L.top
    else:
        y = L.top + max(0, (1450 - L.top - h) / 2)
    draw_stack(draw, layer, els, y)

    # oproep-knop: onder de inhoud, maar binnen het veilige deel van de story
    oproep = data.get("story_oproep", "").strip()
    if oproep:
        size = 34
        f = font("body_bold", size)
        tw = f.getlength(oproep)
        pw, ph = tw + 90, 92
        bottom = content_bottom(layer) or 1400
        x0, y0 = (L.w - pw) / 2, min(1640, bottom + 70)
        s = 3
        pill = Image.new("RGBA", (int(pw * s), int(ph * s)), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle((0, 0, pw * s - 1, ph * s - 1), radius=ph * s / 2,
                                               fill=(255, 255, 255, 245))
        pill = pill.resize((int(pw), int(ph)), Image.LANCZOS)
        layer.alpha_composite(pill, (int(x0), int(y0)))
        draw.text((L.w / 2, y0 + ph / 2), oproep, font=f, fill=(12, 38, 86, 255), anchor="mm")
    return finish_slide(L, bg, layer)


def render_all(data, foto=None):
    """
    data: dict met soort, label, titel, ondertitel, kop, tekst, lijst_kop, lijst, slot,
          uitslag, stemming {voor:[{naam,zetels}], tegen:[...]}, foto_stijl, story_oproep
    foto: PIL.Image of None
    Geeft (lijst post-slides, story) als RGB-afbeeldingen.
    """
    cfg = load_config()
    soort = cfg["soorten"].get(data.get("soort"), {})
    standaard = soort.get("achtergrond", "haven")
    stijl = data.get("foto_stijl") or soort.get("foto_stijl", "onder")

    stem = data.get("stemming") or {}
    data["toon_stemming"] = bool(soort.get("stemming")) and bool(stem.get("voor") or stem.get("tegen")) \
        and data.get("uitslag") not in ("Aangehouden", "Ingetrokken")
    if not soort.get("stemming"):
        data["uitslag"] = ""

    focus = None
    try:
        focus = (min(max(float(data.get("focus_x")), 0), 1), min(max(float(data.get("focus_y")), 0), 1))
    except (TypeError, ValueError):
        pass
    if foto is not None:
        foto = ImageOps.exif_transpose(foto).convert("RGB")
        foto.thumbnail((2400, 2400))
    cache = {}

    def bg(w, h, bottom):
        # op 20 px afronden zodat vergelijkbare slides dezelfde achtergrond delen
        key = (w, h, None if bottom is None else bottom // 20)
        if key not in cache:
            cache[key] = build_background((w, h), stijl, foto, standaard, focus,
                                          None if bottom is None else key[2] * 20 + 20)
        return cache[key]

    slides = [s.convert("RGB") for s in build_post(data, bg)]
    story = build_story(data, bg).convert("RGB")
    return slides, story
