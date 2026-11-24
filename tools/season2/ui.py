"""Chat UI: phone panel, notification banner, lock-screen hook, typography."""
import math, re
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

FD = "/usr/share/fonts/opentype/inter/"
F_REG, F_MED, F_SEMI, F_BOLD, F_XB = FD + "Inter-Regular.otf", FD + "Inter-Medium.otf", FD + "Inter-SemiBold.otf", FD + "Inter-Bold.otf", FD + "Inter-ExtraBold.otf"
ITALIC = "/usr/share/texmf/fonts/opentype/public/lm/lmroman12-italic.otf"
EMOJI_TTF = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
_fc = {}


def font(p, s):
    k = (p, int(s))
    if k not in _fc:
        _fc[k] = ImageFont.truetype(p, int(s))
    return _fc[k]


EMOJI_RE = re.compile("([\U0001F300-\U0001FAFF❤☀-➿]️?)")
_ec = {}


def emoji_img(e, size):
    k = (e, size)
    if k not in _ec:
        im = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((0, 0), e, font=ImageFont.truetype(EMOJI_TTF, 109), embedded_color=True)
        bb = im.getbbox()
        im = im.crop(bb) if bb else im
        sc = size / max(im.size)
        _ec[k] = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
    return _ec[k]


def tokens(text):
    out = []
    for part in EMOJI_RE.split(text):
        if not part:
            continue
        if EMOJI_RE.fullmatch(part):
            out.append(("e", part))
        else:
            for i, w in enumerate(part.split(" ")):
                if w:
                    out.append(("w", w))
    return out


def layout(text, f, maxw, esize):
    sp = f.getlength(" ")
    lines, cur, cw = [], [], 0
    for kind, v in tokens(text):
        w = f.getlength(v) if kind == "w" else esize
        add = w + (sp if cur else 0)
        if cw + add > maxw and cur:
            lines.append((cur, cw)); cur, cw = [(kind, v, w)], w
        else:
            cur.append((kind, v, w)); cw += add
    lines.append((cur, cw))
    return lines


def draw_line(im, d, x, y, line, f, fill, esize, sp):
    cx = x
    for kind, v, w in line:
        if kind == "w":
            d.text((cx, y), v, font=f, fill=fill, anchor="la")
        else:
            e = emoji_img(v, esize)
            im.alpha_composite(e, (int(cx), int(y + (f.size * 1.0 - esize) / 2 + f.size * .05)))
        cx += w + sp


PW, PH, PAD = 420, 650, 30
BUBBLE_ME = (116, 84, 250)
BUBBLE_OT = (54, 56, 64)
_pc = {}


def avatar_circle(img, d):
    im = img.convert("RGBA").resize((d, d), Image.LANCZOS)
    m = Image.new("L", (d, d), 0)
    ImageDraw.Draw(m).ellipse([0, 0, d - 1, d - 1], fill=255)
    out = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    out.paste(im, (0, 0), m)
    return out


def phone_img(key, name, avatar, msgs, me, nvis, dots, input_txt, caret, seen, time_label, newa=1.0):
    """msgs: list of (who,text). me: index of the phone's owner. returns RGBA (PW+2PAD, PH+2PAD)"""
    newa = round(newa * 4) / 4
    k = (key, nvis, dots is not None, input_txt, caret, seen, newa)
    if dots is not None:
        k = k + (round(dots * 6) % 6,)
    if k in _pc:
        return _pc[k]
    s = 2
    im = Image.new("RGBA", ((PW + 2 * PAD) * s, (PH + 2 * PAD) * s), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([PAD * s, (PAD + 16) * s, (PAD + PW) * s, (PAD + PH + 16) * s], 58 * s, fill=(0, 0, 0, 170))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(16 * s)))
    d = ImageDraw.Draw(im)

    def X(v): return (PAD + v) * s

    def RR(x0, y0, x1, y1, r, fill, **kw):
        d.rounded_rectangle([X(x0), X(y0), X(x1), X(y1)], radius=r * s, fill=fill, **kw)

    RR(0, 0, PW, PH, 58, (12, 12, 15))
    RR(7, 7, PW - 7, PH - 7, 51, (20, 20, 25))
    RR(PW / 2 - 52, 18, PW / 2 + 52, 40, 11, (4, 4, 6))
    # header
    if avatar is not None:
        im.alpha_composite(avatar_circle(avatar, 56 * s), (int(X(26)), int(X(56))))
    d.text((X(94), X(72)), name, font=font(F_BOLD, 26 * s), fill=(246, 246, 250), anchor="lm")
    st = "typing…" if dots is not None else "Active now"
    col = (150, 160, 255) if dots is not None else (150, 152, 162)
    if dots is None:
        d.ellipse([X(94), X(92), X(104), X(102)], fill=(70, 210, 120))
        d.text((X(110), X(97)), st, font=font(F_REG, 17 * s), fill=col, anchor="lm")
    else:
        d.text((X(94), X(97)), st, font=font(F_MED, 17 * s), fill=col, anchor="lm")
    d.line([X(18), X(128), X(PW - 18), X(128)], fill=(44, 44, 54), width=2 * s)
    # chat layer
    chat = Image.new("RGBA", im.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(chat)
    fm = font(F_REG, 26 * s)
    esz = 28 * s
    maxw = 268 * s
    sp = fm.getlength(" ")
    items = []
    for i, (who, text) in enumerate(msgs[:nvis]):
        lines = layout(text, fm, maxw, esz)
        w_ = max(l[1] for l in lines)
        bh = len(lines) * 35 * s + 22 * s
        items.append((who == me, lines, w_, bh, i))
    if dots is not None:
        items.append((False, None, 66 * s, 48 * s, -1))
    y = (PH - 112) * s
    last_mine = max([b[4] for b in items if b[0]] or [-9])
    first = True
    for (mine, lines, w_, bh, idx) in reversed(items):
        if mine and idx == last_mine and seen and dots is None and first:
            cd.text(((PAD + PW - 28) * s, y - 2 * s), "Seen just now", font=font(F_REG, 15 * s), fill=(128, 130, 142), anchor="rb")
            y -= 24 * s
        first = False
        y0 = y - bh
        isnew = (idx == nvis - 1 and idx >= 0 and newa < 1.0)
        if isnew:
            y0 += int((1 - newa) * 26 * s); y += int((1 - newa) * 26 * s)
        bw = w_ + 40 * s
        if mine:
            x1 = (PAD + PW - 22) * s
            x0 = x1 - bw
            col = BUBBLE_ME
        else:
            x0 = (PAD + 22) * s
            x1 = x0 + bw
            col = BUBBLE_OT
        fa = newa if isnew else 1.0
        col = tuple(int(20 + (c_ - 20) * fa) for c_ in col)
        cd.rounded_rectangle([x0, y0, x1, y], radius=26 * s, fill=col)
        if lines is None:
            for q in range(3):
                a = 0.5 + 0.5 * math.sin((dots * 2 * math.pi) - q * 0.9)
                v = int(120 + 120 * a)
                cxk = x0 + 22 * s + q * 20 * s + 6 * s
                cd.ellipse([cxk - 6 * s, y - 24 * s - 6 * s, cxk + 6 * s, y - 24 * s + 6 * s], fill=(v, v, v + 8))
        else:
            for li, ln in enumerate(lines):
                draw_line(chat, cd, x0 + 20 * s, y0 + 11 * s + li * 35 * s, ln[0], fm, (int(20 + 235 * fa),) * 3, esz, sp)
        y = y0 - 11 * s - (int((1 - newa) * 26 * s) if isnew else 0)
        if y < 120 * s:
            break
    # time label
    if time_label:
        cd.text(((PAD + PW / 2) * s, (PAD + 150) * s), time_label, font=font(F_MED, 15 * s), fill=(120, 122, 136), anchor="mm")
    mk = Image.new("L", im.size, 0)
    md = ImageDraw.Draw(mk)
    yt, yb = int(X(132)), int(X(PH - 104))
    md.rectangle([0, yt, im.size[0], yb], fill=255)
    for i in range(48 * s):
        md.line([0, yt + i, im.size[0], yt + i], fill=int(255 * i / (48 * s)))
    chat.putalpha(ImageChops.multiply(chat.getchannel("A"), mk))
    im.alpha_composite(chat)
    # input bar
    RR(18, PH - 98, PW - 18, PH - 36, 31, (42, 42, 52))
    fi = font(F_REG, 24 * s)
    if input_txt:
        tx = input_txt
        while fi.getlength(tx) > (PW - 150) * s and len(tx) > 3:
            tx = tx[1:]
        d.text((X(42), X(PH - 67)), tx + ("|" if caret else ""), font=fi, fill=(244, 244, 250), anchor="lm")
    else:
        d.text((X(42), X(PH - 67)), "Message" + ("|" if caret else "…"), font=fi, fill=(116, 118, 132), anchor="lm")
    d.ellipse([X(PW - 78), X(PH - 90), X(PW - 30), X(PH - 44)], fill=BUBBLE_ME if input_txt else (62, 62, 74))
    d.polygon([(X(PW - 62), X(PH - 62)), (X(PW - 54), X(PH - 77)), (X(PW - 46), X(PH - 62))], fill=(255, 255, 255))
    out = im.resize((PW + 2 * PAD, PH + 2 * PAD), Image.LANCZOS)
    _pc[k] = out
    return out


_bc = {}


def banner_img(name, text, avatar):
    k = (name, text)
    if k in _bc:
        return _bc[k]
    s = 2
    w, h = 640, 112
    im = Image.new("RGBA", ((w + 40) * s, (h + 40) * s), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([20 * s, 30 * s, (20 + w) * s, (30 + h) * s], 34 * s, fill=(0, 0, 0, 150))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10 * s)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([20 * s, 20 * s, (20 + w) * s, (20 + h) * s], 34 * s, fill=(36, 36, 44, 238), outline=(255, 255, 255, 40), width=2)
    d.rounded_rectangle([40 * s, 40 * s, 112 * s, 100 * s], 16 * s, fill=(70, 210, 120))
    d.text((76 * s, 70 * s), "💬" if False else "", font=font(F_BOLD, 20 * s), fill=(255, 255, 255), anchor="mm")
    if avatar is not None:
        im.alpha_composite(avatar_circle(avatar, 64 * s), (int(46 * s), int(38 * s)))
    d.text((132 * s, 54 * s), name, font=font(F_BOLD, 25 * s), fill=(255, 255, 255), anchor="lm")
    d.text(((20 + w - 24) * s, 54 * s), "now", font=font(F_REG, 20 * s), fill=(170, 172, 182), anchor="rm")
    f = font(F_REG, 24 * s)
    tx = text
    while f.getlength(tx) > (w - 130) * s and len(tx) > 4:
        tx = tx[:-2]
    if tx != text:
        tx = tx.rstrip() + "…"
    sp = f.getlength(" ")
    lines = layout(tx, f, 10 ** 6, 26 * s)
    draw_line(im, d, 132 * s, 84 * s - f.size // 2 - 4 * s, lines[0][0], f, (226, 228, 236), 26 * s, sp)
    out = im.resize((w + 40, h + 40), Image.LANCZOS)
    _bc[k] = out
    return out


def text_shadow(img, xy, txt, f, fill, anchor="mm", blur=10, k=180, off=(0, 4)):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + off[0], xy[1] + off[1]), txt, font=f, fill=(0, 0, 0, k), anchor=anchor)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(img).text(xy, txt, font=f, fill=fill, anchor=anchor)


def hook_text(size, lines, t, accent=(255, 214, 90), y0=250, fsize=76):
    """lines: list of list of (word, accent bool). word-by-word pop in over first 0.9 s"""
    lay = Image.new("RGBA", size, (0, 0, 0, 0))
    f = font(F_XB, fsize)
    idx = 0
    for li, words in enumerate(lines):
        sp = f.getlength(" ")
        total = sum(f.getlength(w) for w, _ in words) + sp * (len(words) - 1)
        x = size[0] / 2 - total / 2
        y = y0 + li * (fsize + 18)
        for w, acc in words:
            ap = min(1.0, max(0.0, (t - idx * 0.11) / 0.22))
            wlen = f.getlength(w)
            if ap > 0:
                sc = 0.7 + 0.3 * (1 - (1 - ap) ** 3) + (0.06 * math.sin(ap * math.pi))
                wl = Image.new("RGBA", (int(wlen + 80), int(fsize * 2.0)), (0, 0, 0, 0))
                ImageDraw.Draw(wl).text((40, fsize), w, font=f, fill=(0, 0, 0, 0), anchor="lm")
                if acc:
                    pad = 12
                    ImageDraw.Draw(wl).rounded_rectangle([40 - pad, fsize - fsize * .62, 40 + wlen + pad, fsize + fsize * .52], 16, fill=accent + (255,))
                    col = (20, 18, 24)
                else:
                    col = (255, 255, 255)
                text_shadow(wl, (40, fsize), w, f, col, anchor="lm", blur=9, k=0 if acc else 200)
                wl = wl.resize((max(2, int(wl.width * sc)), max(2, int(wl.height * sc))), Image.LANCZOS)
                a = wl.getchannel("A").point(lambda v: int(v * ap))
                wl.putalpha(a)
                lay.alpha_composite(wl, (int(x - 40 * sc), int(y - fsize * sc)))
            x += wlen + sp
            idx += 1
    return lay


def lock_screen(size, lock, t):
    """full-frame lock screen insert with stacked notifications."""
    W, H = size
    bg = Image.new("RGBA", size, (14, 16, 30, 255))
    d = ImageDraw.Draw(bg)
    for i in range(H):
        a = i / H
        d.line([0, i, W, i], fill=(int(18 + 30 * a), int(20 + 14 * a), int(40 + 36 * (1 - a)), 255))
    bk = Image.new("RGBA", size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(bk)
    import random
    r = random.Random(11)
    for i in range(24):
        x, y, rr = r.uniform(0, W), r.uniform(0, H), r.uniform(30, 120)
        c = r.choice([(255, 150, 90), (110, 150, 255), (255, 110, 150)])
        bd.ellipse([x - rr, y - rr, x + rr, y + rr], fill=c + (46,))
    bg.alpha_composite(bk.filter(ImageFilter.GaussianBlur(40)))
    d = ImageDraw.Draw(bg)
    d.text((W / 2, 250), lock["date"], font=font(F_SEMI, 40), fill=(255, 255, 255, 220), anchor="mm")
    d.text((W / 2, 400), lock["time"], font=font(F_BOLD, 220), fill=(255, 255, 255), anchor="mm")
    y = 600
    for i, cd_ in enumerate(lock["cards"]):
        tt = t - cd_["t"]
        if tt < 0:
            continue
        ap = min(1, tt / 0.28)
        e = 1 - (1 - ap) ** 3
        ov = 0.06 * math.sin(ap * math.pi)
        h = cd_.get("h", 150)
        card = Image.new("RGBA", (W - 90, h), (0, 0, 0, 0))
        cdx = ImageDraw.Draw(card)
        red = cd_.get("red")
        cdx.rounded_rectangle([0, 0, W - 91, h - 1], 40, fill=(200, 40, 50, 235) if red else (44, 46, 58, 232), outline=(255, 255, 255, 36), width=2)
        cdx.text((36, 40), cd_["title"], font=font(F_BOLD, 38), fill=(255, 255, 255), anchor="lm")
        cdx.text((W - 91 - 34, 40), cd_.get("when", "now"), font=font(F_REG, 28), fill=(210, 212, 222), anchor="rm")
        f = font(F_REG, 34)
        lines = layout(cd_["text"], f, W - 91 - 80, 36)
        sp = f.getlength(" ")
        draw_line(card, cdx, 36, 76, lines[0][0], f, (236, 238, 246), 36, sp)
        sc = (0.84 + 0.16 * e + ov)
        card = card.resize((int(card.width * sc), int(card.height * sc)), Image.LANCZOS)
        a = card.getchannel("A").point(lambda v: int(v * ap))
        card.putalpha(a)
        shake = 0
        if tt < 0.5:
            shake = math.sin(tt * 60) * 9 * (1 - tt / 0.5)
        bg.alpha_composite(card, (int((W - card.width) / 2 + shake), int(y + (h - card.height) / 2 + (1 - e) * 30)))
        y += h + 22
    return bg
