#!/usr/bin/env python3
"""Cover images for the Seen Just Now series (1080x1920 PNG).
Everything important sits inside the centre 1080x1440 (3:4) so the profile grid crop keeps it.
Usage: make_covers.py <out_dir>"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_series as ms
from PIL import Image, ImageDraw, ImageFont
import numpy as np

W, H = 1080, 1920
BG = (20, 20, 22)
SERIF_IT = "/usr/share/texmf/fonts/opentype/public/lm/lmroman12-italic.otf"
SERIF = "/usr/share/texmf/fonts/opentype/public/lm/lmroman17-regular.otf"

EPS = [
 (1, "Zoya & Ayaan", "what's your most toxic trait?"),
 (2, "Zoya & Ayaan", "I didn't sleep last night."),
 (3, "Zoya & Ayaan", "you up?"),
 (4, "Mehak & Hamza", "Did you eat?"),
 (5, "Mehak & Hamza", "I called you twice."),
 (6, "Mehak & Hamza", "I'm outside your door."),
 (7, "Sara & Rayyan", "Hey. I know I shouldn't text."),
 (8, "Sara & Rayyan", "I'm not asking to come back."),
 (9, "Sara & Rayyan", "You said it was the first honest thing in a year."),
 (10, "Sara & Rayyan", "I'm not asking you to forgive me tonight."),
 (11, "Zoya & Ayaan", "I'm at the cafe. Where are you?"),
 (12, "Zoya & Ayaan", "Your sister asked who I am."),
 (13, "Mehak & Hamza", "Did you read the letter?"),
 (14, "Mehak & Hamza", "Dinner tomorrow? I'll cook."),
 (15, "Noor & Daniyal", "My mother gave me your number. I'm sorry in advance."),
 (16, "Noor & Daniyal", "I read the poem you sent."),
]

def spaced(d, xy, text, font, fill, sp, center=False):
    w = sum(font.getlength(c) + sp for c in text) - sp
    x, y = xy
    if center: x = (W - w) / 2
    for c in text:
        d.text((x, y), c, font=font, fill=fill)
        x += font.getlength(c) + sp
    return w

def gradient_pill(w, h):
    ss = 2
    grad = Image.new("RGB", (w * ss, h * ss))
    gd = ImageDraw.Draw(grad)
    for y in range(h * ss):
        k = y / max(h * ss - 1, 1)
        gd.line([(0, y), (w * ss, y)], fill=(int(104 - 36 * k), int(78 + 52 * k), int(236 + 4 * k)))
    mask = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), h * ss // 2, fill=255)
    out = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out.resize((w, h), Image.LANCZOS)

def make(ep, couple, hook, out):
    # soft vertical vignette background
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :, None]
    base = np.array(BG, np.float32) + 8 * (1 - np.abs(yy - 0.5) * 2) - 6 * xx ** 2
    im = Image.fromarray(np.clip(np.broadcast_to(base, (H, W, 3)), 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(im)

    f_title = ms.F("SemiBold", 44)
    spaced(d, (0, 330), "SEEN JUST NOW", f_title, (240, 240, 244), 9, center=True)

    # episode pill
    f_ep = ms.F("SemiBold", 52)
    txt = "EPISODE %d" % ep
    tw = sum(f_ep.getlength(c) + 6 for c in txt) - 6
    pw, ph = int(tw + 110), 112
    im.alpha_composite(gradient_pill(pw, ph), ((W - pw) // 2, 430))
    spaced(d, (0, 430 + 22), txt, f_ep, (255, 255, 255), 6, center=True)

    # hook bubble (received) + typing reply (sent, violet)
    ms.MAXTXT = 700
    big = ms.F("Regular", 70)
    b = ms.bubble_image(hook, False, big)
    bx, by = 90, 700
    im.alpha_composite(b, (bx, by))
    # reply typing bubble on the right
    tw2, th2 = 230, 120
    typ = gradient_pill(tw2, th2)
    ty = by + b.height + 40
    im.alpha_composite(typ, (W - 90 - tw2, ty))
    d = ImageDraw.Draw(im)
    for j in range(3):
        cx = W - 90 - tw2 + 70 + j * 45
        d.ellipse((cx - 11, ty + th2 // 2 - 11, cx + 11, ty + th2 // 2 + 11), fill=(255, 255, 255))

    # couple name
    f_c = ImageFont.truetype(SERIF_IT, 96)
    cw = f_c.getlength(couple)
    d.text(((W - cw) / 2, 1230), couple, font=f_c, fill=(236, 232, 224))
    f_s = ms.F("Regular", 32)
    spaced(d, (0, 1385), "NEW EPISODE EVERY NIGHT  ·  8 PM", f_s, (130, 130, 138), 5, center=True)
    f_h = ms.F("Regular", 30)
    hw = f_h.getlength("@aneestheauthor")
    d.text(((W - hw) / 2, 1500), "@aneestheauthor", font=f_h, fill=(110, 110, 116))
    im.convert("RGB").save(out)

if __name__ == "__main__":
    od = sys.argv[1]
    os.makedirs(od, exist_ok=True)
    for ep, c, h in EPS:
        make(ep, c, h, os.path.join(od, "Cover_Ep%d.png" % ep))
    print("done")
