#!/usr/bin/env python3
"""Mountain poem reel (1080x1920, 30 fps, ~21.5 s), drawn entirely with numpy + PIL (no stock footage, no watermark).
Sky warms from dusk to sunrise, five parallax ridges drift, mist moves, and sunflowers grow in the stony valley on the last line.
Usage:
  make_mountain.py render <spec.json> <out_chunk.mp4> <start_frame> <end_frame>
  make_mountain.py audio  <spec.json> <out.wav>
  make_mountain.py cover  <spec.json> <out.png> <seconds>
spec: {"lines": [...], "times": [...], "gold_last": true, "handle": "@aneestheauthor", "follow": "Follow for more poetry"}
"""
import json, math, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
DUR = 21.5
NF = int(DUR * FPS)
ITALIC = "/usr/share/texmf/fonts/opentype/public/lm/lmroman12-italic.otf"
SERIF = "/usr/share/texmf/fonts/opentype/public/lm/lmroman17-regular.otf"
T_FLOWERS = 9.8


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.2, 2.2
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


# ---------------------------------------------------------------- static scene data
xs = np.arange(W, dtype=np.float32)
rows = np.arange(H, dtype=np.float32)[:, None]
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
GLOW = np.exp(-(((xx - 540) ** 2) / (2 * 430 ** 2) + ((yy - 1130) ** 2) / (2 * 380 ** 2))).astype(np.float32)
del yy, xx

SCROLL = 560
LAYERS = [  # base y, amplitude, roughness, haze, colour, drift px/s, valley-wall rise
    (1190, 330, 1.5, 0.80, (66, 78, 122), 3.0, 0),
    (1290, 310, 1.9, 0.58, (50, 56, 92), 6.0, 40),
    (1410, 280, 2.3, 0.38, (34, 38, 68), 10.0, 110),
    (1520, 230, 2.8, 0.18, (22, 24, 46), 16.0, 210),
    (1665, 130, 3.4, 0.05, (13, 13, 24), 24.0, 280),
]


def ridge(seed, base, amp, rough):
    r = np.random.default_rng(seed)
    n = W + SCROLL
    x = np.arange(n) / n
    y = np.zeros(n)
    a = 1.0
    f = 1.0
    for _ in range(5):
        y += a * (1 - np.abs(np.sin(2 * np.pi * (f * x * rough + r.random())))) ** 1.3
        f *= 2.1
        a *= 0.42
    y = (y - y.min()) / (y.max() - y.min())
    return (base - amp * y).astype(np.float32)


RIDGES = [ridge(11 + i, L[0], L[1], L[2]) for i, L in enumerate(LAYERS)]

_r = np.random.default_rng(3)
STARS = [(int(_r.integers(8, W - 8)), int(_r.integers(260, 760)), float(_r.uniform(0.35, 1.0)), float(_r.uniform(0, 6.28)))
         for _ in range(90)]

# stones (static foreground)
_stone = Image.new("RGBA", (W, H), (0, 0, 0, 0))
_sd = ImageDraw.Draw(_stone)
_r = np.random.default_rng(5)
for _ in range(70):
    cy = float(_r.uniform(1620, 1900))
    size = 26 + (cy - 1620) / 280 * 90 * float(_r.uniform(0.55, 1.1))
    cx = float(_r.uniform(-30, W + 30))
    n = int(_r.integers(6, 9))
    ang = np.sort(_r.uniform(0, 2 * np.pi, n))
    pts = [(cx + math.cos(a) * size * float(_r.uniform(0.7, 1.1)), cy + math.sin(a) * size * 0.55 * float(_r.uniform(0.7, 1.1)))
           for a in ang]
    g = int(_r.integers(30, 62))
    _sd.polygon(pts, fill=(g, g - 2, g + 6, 255))
    top = [(px, py - 3) for px, py in pts if py < cy]
    if len(top) >= 2:
        _sd.line(top, fill=(g + 34, g + 30, g + 40, 255), width=3)
STONE_RGB = np.asarray(_stone, dtype=np.float32)[1560:, :, :3]
STONE_A = np.asarray(_stone, dtype=np.float32)[1560:, :, 3:4] / 255.0

_r = np.random.default_rng(9)
POLLEN = [(float(_r.uniform(0, W)), float(_r.uniform(900, 1900)), float(_r.uniform(14, 34)), float(_r.uniform(0, 6.28)),
           float(_r.uniform(1.5, 4.0))) for _ in range(70)]

# sunflowers: x, base y, full stem height, head radius, start delay
SUNFLOWERS = [(95, 1880, 300, 44, 0.00), (960, 1870, 310, 46, 0.10), (225, 1895, 390, 56, 0.35), (835, 1895, 370, 54, 0.45),
              (360, 1865, 470, 64, 0.15), (690, 1880, 450, 62, 0.25), (525, 1905, 570, 76, 0.55)]


def gradient_stop(k):
    top = np.array((14, 18, 42), np.float32) * (1 - k) + np.array((46, 54, 108), np.float32) * k
    mid = np.array((60, 50, 96), np.float32) * (1 - k) + np.array((206, 124, 122), np.float32) * k
    hor = np.array((172, 108, 126), np.float32) * (1 - k) + np.array((255, 198, 122), np.float32) * k
    return top, mid, hor


# ---------------------------------------------------------------- text
def spaced_mask(text, font, sp):
    w = int(sum(font.getlength(c) + sp for c in text) - sp) + 40
    asc, desc = font.getmetrics()
    h = asc + desc + 40
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    x = 20
    for c in text:
        d.text((x, 20), c, font=font, fill=255)
        x += font.getlength(c) + sp
    return im


def to_float(im):
    return np.asarray(im, dtype=np.float32) / 255.0


def build_text(spec):
    size, sp = 68, 2
    f = ImageFont.truetype(ITALIC, size)
    max_w = 960
    lines = spec["lines"]
    times = spec["times"]
    subs = []
    for gi, t in enumerate(lines):
        cur = ""
        for w_ in t.split():
            trial = (cur + " " + w_).strip()
            if cur and sum(f.getlength(c) + sp for c in trial) > max_w:
                subs.append((gi, cur)); cur = w_
            else:
                cur = trial
        subs.append((gi, cur))
    lh = int(size * 1.34)
    y = 420
    items = []
    for i, (gi, s) in enumerate(subs):
        if i and subs[i - 1][0] != gi:
            y += 30
        im = spaced_mask(s, f, sp)
        m = to_float(im)
        shadow = to_float(im.filter(ImageFilter.GaussianBlur(16)))
        x = (W - im.width) // 2
        gold = spec.get("gold_last", True) and gi == len(lines) - 1
        items.append(dict(m=m, sh=shadow, xy=(x, y - 20), t=times[gi], gold=gold))
        y += lh
    handle = ImageFont.truetype(SERIF, 34)
    hm = spaced_mask(spec.get("handle", "@aneestheauthor"), handle, 6)
    fm = spaced_mask(spec.get("follow", "Follow for more poetry"), ImageFont.truetype(ITALIC, 46), 2)
    return items, (to_float(hm), to_float(hm.filter(ImageFilter.GaussianBlur(10))), ((W - hm.width) // 2, 285)), \
        (to_float(fm), to_float(fm.filter(ImageFilter.GaussianBlur(12))), ((W - fm.width) // 2, 262))


def blend_mask(frame, m, sh, xy, a, col, shadow_k=0.9):
    if a <= 0:
        return
    x, y = xy
    h, w = m.shape
    x1, y1 = max(x, 0), max(y, 0)
    x2, y2 = min(x + w, W), min(y + h, H)
    if x2 <= x1 or y2 <= y1:
        return
    mm = m[y1 - y:y2 - y, x1 - x:x2 - x][..., None]
    ss = sh[y1 - y:y2 - y, x1 - x:x2 - x][..., None]
    reg = frame[y1:y2, x1:x2]
    reg *= (1 - shadow_k * ss * a)
    frame[y1:y2, x1:x2] = reg * (1 - mm * a) + col * mm * a


# ---------------------------------------------------------------- sunflowers (supersampled)
def draw_flowers(t):
    if t < T_FLOWERS:
        return None
    ss = 2
    y0 = 1100
    img = Image.new("RGBA", (W * ss, (H - y0) * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def P(x, y):
        return (x * ss, (y - y0) * ss)

    for (x, by, hgt, rad, delay) in sorted(SUNFLOWERS, key=lambda s: s[2]):
        g = ease_back((t - T_FLOWERS - delay) / 2.0)
        if g <= 0.001:
            continue
        gh = min(g, 1.05)
        sway = math.sin(t * 1.1 + x * 0.01) * 9 * gh
        top_x, top_y = x + sway, by - hgt * gh
        # stem (curved)
        pts = []
        for i in range(21):
            u = i / 20
            pts.append(P(x + sway * u * u, by - (by - top_y) * u))
        d.line(pts, fill=(44, 92, 40, 255), width=int(9 * ss))
        # leaves
        for lf, side in ((0.42, -1), (0.62, 1)):
            lx, ly = x + sway * lf * lf, by - (by - top_y) * lf
            d.polygon([P(lx, ly), P(lx + side * rad * 1.1 * gh, ly - rad * 0.75 * gh), P(lx + side * rad * 1.6 * gh, ly - rad * 0.2 * gh),
                       P(lx + side * rad * 0.7 * gh, ly + rad * 0.12 * gh)], fill=(52, 112, 44, 255))
        # head
        R = rad * gh
        if R > 3:
            spin = t * 0.08 + x
            for layer, (cnt, col, ln) in enumerate(((18, (236, 160, 24), 1.85), (18, (255, 205, 48), 1.7))):
                for k_ in range(cnt):
                    a = spin + (k_ + 0.5 * layer) / cnt * 2 * math.pi
                    dx, dy = math.cos(a), math.sin(a)
                    px, py = -dy, dx
                    base = 0.75 * R
                    tip = ln * R
                    w_ = 0.27 * R
                    d.polygon([P(top_x + dx * base + px * w_, top_y + dy * base + py * w_), P(top_x + dx * tip, top_y + dy * tip),
                               P(top_x + dx * base - px * w_, top_y + dy * base - py * w_)], fill=col + (255,))
            d.ellipse([P(top_x - 0.82 * R, top_y - 0.82 * R), P(top_x + 0.82 * R, top_y + 0.82 * R)], fill=(66, 38, 16, 255))
            d.ellipse([P(top_x - 0.56 * R, top_y - 0.56 * R), P(top_x + 0.56 * R, top_y + 0.56 * R)], fill=(104, 62, 24, 255))
            d.ellipse([P(top_x - 0.22 * R, top_y - 0.22 * R), P(top_x + 0.12 * R, top_y + 0.12 * R)], fill=(150, 98, 40, 255))
    img = img.resize((W, H - y0), Image.LANCZOS)
    arr = np.asarray(img, dtype=np.float32)
    return y0, arr[..., :3], arr[..., 3:4] / 255.0


# ---------------------------------------------------------------- frame
def render_frame(n, text):
    items, handle, follow = text
    t = n / FPS
    k = smooth((t - 7.5) / 9.0)
    top, mid, hor = gradient_stop(k)
    ypos = np.array([0, 0.50, 0.60, 1.0]) * H
    col_y = np.stack([np.interp(np.arange(H), ypos, [top[c], mid[c], hor[c], hor[c]]) for c in range(3)], axis=1).astype(np.float32)
    frame = np.empty((H, W, 3), np.float32)
    frame[:] = col_y[:, None, :]
    frame += GLOW[..., None] * np.array((255, 175, 92), np.float32) * (0.10 + 0.55 * k)

    for (sx, sy, b, ph) in STARS:
        v = (1 - k) * b * (0.65 + 0.35 * math.sin(t * 1.4 + ph)) * 235
        if v > 4:
            frame[sy:sy + 2, sx:sx + 2] = np.maximum(frame[sy:sy + 2, sx:sx + 2], v)

    hc = hor  # haze colour follows the horizon
    for i, (base, amp, rough, haze, colr, drift, wall) in enumerate(LAYERS):
        off = int(drift * t)
        yt = RIDGES[i][off:off + W] - wall * ((xs - 540) / 540) ** 2
        mask = rows >= yt[None, :]
        shade = 1 - 0.38 * np.clip((rows - yt[None, :]) / 650, 0, 1)
        col = np.array(colr, np.float32) * (1 - haze) + hc * haze
        layer = col[None, None, :] * shade[..., None]
        rim = ((rows >= yt[None, :]) & (rows < yt[None, :] + 5))[..., None]
        layer = layer + rim * (hc * 0.28 * (0.2 + k))
        if i <= 2:  # snow caps on the higher peaks
            thr = base - amp * 0.42
            s = np.clip((thr - yt) / 90, 0, 1)[None, :]
            sn = s * np.clip(1 - (rows - yt[None, :]) / (28 + 120 * s), 0, 1) * mask * (1 - 0.55 * haze)
            snow = (np.array((226, 228, 242), np.float32) * (0.62 + 0.38 * k)) * 0.8 + hc * 0.2
            layer = layer * (1 - sn[..., None]) + snow * sn[..., None]
        frame = np.where(mask[..., None], layer, frame)
        if i in (1, 3):  # mist bands in front of this ridge
            cy, sg, ph = (1210, 85, 0.0) if i == 1 else (1400, 110, 1.7)
            vg = np.exp(-((rows[:, 0] - cy) ** 2) / (2 * sg ** 2))[:, None]
            xn = 0.5 + 0.5 * np.sin(2 * np.pi * (xs / W * 1.2 + t * 0.018) + ph)
            a = (0.30 * vg * xn[None, :])[..., None]
            mc = hc * 0.85 + np.array((60, 60, 70), np.float32) * 0.15
            frame = frame * (1 - a) + mc * a

    # stones, warmed by the sunrise
    sl = frame[1560:]
    stone = STONE_RGB + np.array((70, 38, 6), np.float32) * k * (STONE_RGB / 80.0)
    frame[1560:] = sl * (1 - STONE_A) + stone * STONE_A

    # sunflowers
    fl = draw_flowers(t)
    if fl is not None:
        y0, rgb, al = fl
        frame[y0:] = frame[y0:] * (1 - al) + rgb * al

    # pollen
    if k > 0.05:
        pil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pil)
        for (px, py, vy, ph, r) in POLLEN:
            y = (py - vy * t) % (H + 100) - 50
            x = (px + 24 * math.sin(t * 0.7 + ph)) % W
            al_ = int(220 * k * (0.5 + 0.5 * math.sin(t * 2 + ph)))
            pd.ellipse((x - r, y - r, x + r, y + r), fill=(255, 224, 150, al_))
        pil = pil.filter(ImageFilter.GaussianBlur(1.2))
        pa = np.asarray(pil, dtype=np.float32)
        frame = frame * (1 - pa[..., 3:4] / 255.0) + pa[..., :3] * (pa[..., 3:4] / 255.0)

    # soft scrim behind the text block so it stays readable at sunrise
    scr = np.exp(-((rows[:, 0] - 700) ** 2) / (2 * 260 ** 2))[:, None, None]
    frame *= 1 - (0.18 + 0.30 * k) * scr
    # text
    for it in items:
        a = 1.0 if it["t"] <= 0 else smooth((t - it["t"]) / 0.9)
        col = np.array((255, 214, 140) if it["gold"] else (246, 241, 233), np.float32)
        blend_mask(frame, it["m"], it["sh"], it["xy"], a, col)
    blend_mask(frame, handle[0], handle[1], handle[2], 0.55 * smooth((t - 0.4) / 1.0) * (1 - smooth((t - 15.4) / 0.6)), np.array((236, 232, 224), np.float32))
    blend_mask(frame, follow[0], follow[1], follow[2], 0.95 * smooth((t - 16.0) / 1.0), np.array((255, 236, 200), np.float32))

    # fade in from black at the very start is avoided on purpose (frame 0 is the cover); fade out at the end
    if t > DUR - 1.0:
        frame *= 1 - 0.85 * smooth((t - (DUR - 1.0)) / 1.0)
    grain = np.random.default_rng(n).normal(0, 2.2, (H, W, 1)).astype(np.float32)
    return np.clip(frame + grain, 0, 255).astype(np.uint8)


def main():
    mode = sys.argv[1]
    spec = json.load(open(sys.argv[2]))
    if mode == "audio":
        out = sys.argv[3]
        cmd = ["ffmpeg", "-v", "error", "-y"]
        for fr in (110.0, 164.81, 220.0, 277.18):
            cmd += ["-f", "lavfi", "-t", f"{DUR:.2f}", "-i", f"sine=frequency={fr}:sample_rate=44100"]
        cmd += ["-f", "lavfi", "-t", f"{DUR:.2f}", "-i", "anoisesrc=color=pink:amplitude=0.5:sample_rate=44100"]
        fc = ("[0][1][2][3]amix=inputs=4:normalize=0,volume=0.22,tremolo=f=0.15:d=0.5,lowpass=f=1000,aecho=0.8:0.6:700:0.35,"
              f"afade=t=in:d=2.5,afade=t=out:st={DUR - 3:.2f}:d=3[pad];"
              "[4]highpass=f=180,lowpass=f=1700,tremolo=f=0.11:d=0.6,volume=0.08,"
              f"afade=t=in:d=3,afade=t=out:st={DUR - 3:.2f}:d=3[wind];"
              "[pad][wind]amix=inputs=2:normalize=0,loudnorm=I=-18:TP=-2:LRA=7[a]")
        cmd += ["-filter_complex", fc, "-map", "[a]", "-ac", "2", out]
        subprocess.run(cmd, check=True)
        return
    text = build_text(spec)
    if mode == "cover":
        Image.fromarray(render_frame(int(float(sys.argv[4]) * FPS), text)).save(sys.argv[3])
        return
    out, s, e = sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", out],
                           stdin=subprocess.PIPE)
    for n in range(s, min(e, NF)):
        enc.stdin.write(render_frame(n, text).tobytes())
    enc.stdin.close()
    enc.wait()


if __name__ == "__main__":
    main()
