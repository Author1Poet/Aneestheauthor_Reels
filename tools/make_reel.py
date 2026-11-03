#!/usr/bin/env python3
"""Render a Dream Note reel (1080x1920, 30fps) with PIL + numpy and pipe it to ffmpeg.
Styles: 'W' = clean off-white card, text block low on the page (like the user's reference screenshot)
        'D' = dark cinematic card with soft rain streaks and bokeh
No watermark, no external assets: everything is drawn and synthesised locally.
Usage: make_reel.py <json spec> <out.mp4>
"""
import json, math, random, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
SERIF = "/usr/share/texmf/fonts/opentype/public/lm/lmroman17-regular.otf"
SERIF_FALLBACK = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
ITALIC = "/usr/share/texmf/fonts/opentype/public/lm/lmroman12-italic.otf"


def font(path, size):
    for p in (path, SERIF_FALLBACK):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    raise SystemExit("no font")


def spaced_width(text, f, sp):
    return sum(f.getlength(c) + sp for c in text) - sp


def text_mask(text, f, sp, pad=8):
    """Return an 'L' mask of letter-spaced text and its size."""
    w = int(spaced_width(text, f, sp)) + pad * 2
    asc, desc = f.getmetrics()
    h = asc + desc + pad * 2
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    x = pad
    for c in text:
        d.text((x, pad), c, font=f, fill=255)
        x += f.getlength(c) + sp
    return np.asarray(im, dtype=np.float32) / 255.0


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def build(spec, out):
    style = spec["style"]
    day = spec["day"]
    lines = spec["lines"]
    small = spec.get("small", [])  # smaller lines (e.g. English meaning) shown after the poem
    size = spec.get("size", 82 if style == "W" else 76)
    sp = 3 if style == "W" else 2
    f_main = font(SERIF, size)
    f_small = font(ITALIC, 44)
    f_tag = font(SERIF, 34)
    max_w = 880 if style == "W" else 920

    def wrap(t):
        out_, cur = [], ""
        for w_ in t.split():
            trial = (cur + " " + w_).strip()
            if cur and spaced_width(trial, f_main, sp) > max_w:
                out_.append(cur)
                cur = w_
            else:
                cur = trial
        out_.append(cur)
        return out_

    sub, grp = [], []
    for gi, t in enumerate(lines):
        for part in wrap(t):
            sub.append(part)
            grp.append(gi)
    lh = int(size * 1.32)
    gapg = 26
    ys, y = [], 0
    for i in range(len(sub)):
        if i and grp[i] != grp[i - 1]:
            y += gapg
        ys.append(y)
        y += lh
    block_h = y
    masks = [text_mask(t, f_main, sp) for t in sub]
    smasks = [text_mask(t, f_small, 1) for t in small]
    total_h = block_h + (len(small) * 70 + 40 if small else 0)

    # timeline (all wrapped parts of one source line fade in together)
    t0, gap, fade = 0.9, spec.get("gap", 2.6), 0.9
    gstarts = [t0 + i * gap for i in range(len(lines))]
    starts = [gstarts[g] for g in grp]
    sstarts = [gstarts[-1] + gap + j * 1.4 for j in range(len(small))]
    last = (sstarts[-1] if small else gstarts[-1]) + fade
    end_card = last + 2.0
    dur = end_card + 3.2
    nframes = int(dur * FPS)

    # layout (top-left of each line's mask)
    pos, spos = [], []
    if style == "W":
        x0 = 130
        y0 = 1540 - total_h
        for i, m in enumerate(masks):
            pos.append((x0 - 8, y0 + ys[i]))
        for j, m in enumerate(smasks):
            spos.append((x0 - 8, y0 + block_h + 40 + j * 70))
    else:
        y0 = 930 - total_h // 2
        for i, m in enumerate(masks):
            pos.append(((W - m.shape[1]) // 2, y0 + ys[i]))
        for j, m in enumerate(smasks):
            spos.append(((W - m.shape[1]) // 2, y0 + block_h + 40 + j * 70))

    # tag + footer masks
    tag = text_mask(f"DREAM NOTE  #{day}", f_tag, 7)
    foot_a = text_mask("Follow for daily Dream Notes", font(ITALIC, 44), 2)
    foot_b = text_mask("@aneestheauthor", f_tag, 6)

    rng = np.random.default_rng(day * 7 + 1)
    # background
    if style == "W":
        bg = np.full((H, W, 3), (251, 250, 247), np.float32)
        ink = np.array((26, 26, 28), np.float32)
        soft = np.array((120, 118, 114), np.float32)
    else:
        yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        base = np.array((11, 12, 17), np.float32) * (1 - yy[..., None] * 0) + 0
        g = np.zeros((H, W, 3), np.float32)
        g[:] = np.array((9, 10, 15), np.float32)
        g += (yy[..., None] * np.array((10, 10, 14), np.float32))
        # vignette
        xs = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
        ys = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
        vig = 1 - 0.45 * np.clip(xs ** 2 * 0.8 + ys ** 2 * 0.6, 0, 1.2)
        bg = g * vig[..., None]
        ink = np.array((238, 234, 226), np.float32)
        soft = np.array((165, 163, 160), np.float32)

    grain = [rng.normal(0, 3.2 if style == "D" else 1.6, (H, W, 1)).astype(np.float32) for _ in range(4)]

    # bokeh sprites (dark style)
    bokeh = []
    if style == "D":
        for _ in range(7):
            r = int(rng.integers(60, 130))
            im = Image.new("L", (r * 4, r * 4), 0)
            ImageDraw.Draw(im).ellipse((r, r, r * 3, r * 3), fill=255)
            im = im.filter(ImageFilter.GaussianBlur(r * 0.55))
            bokeh.append((np.asarray(im, np.float32) / 255.0, rng.uniform(0, W), rng.uniform(300, H - 300),
                          rng.uniform(-6, 6), rng.uniform(-5, 5), rng.uniform(0.06, 0.13),
                          np.array(rng.choice([(255, 214, 150), (190, 200, 255), (255, 235, 210)]), np.float32)))
        streaks = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1100, 1700), rng.integers(70, 190),
                    rng.uniform(0.10, 0.28)) for _ in range(90)]

    def blend(frame, mask, xy, a, color):
        x, y = xy
        h, w = mask.shape
        x1, y1 = max(x, 0), max(y, 0)
        x2, y2 = min(x + w, W), min(y + h, H)
        if x2 <= x1 or y2 <= y1 or a <= 0:
            return
        m = mask[y1 - y:y2 - y, x1 - x:x2 - x][..., None] * a
        reg = frame[y1:y2, x1:x2]
        frame[y1:y2, x1:x2] = reg * (1 - m) + color * m

    # audio first (synth ambient pad, + soft rain for dark style)
    wav = out.replace(".mp4", ".wav")
    fc = ("[0][1][2][3]amix=inputs=4:normalize=0,volume=0.20,tremolo=f=0.18:d=0.5,lowpass=f=1100,"
          f"aecho=0.8:0.6:700:0.35,afade=t=in:d=2.5,afade=t=out:st={dur - 2.5:.2f}:d=2.5[pad]")
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for fr in (110.0, 164.81, 220.0, 277.18):
        cmd += ["-f", "lavfi", "-t", f"{dur:.2f}", "-i", f"sine=frequency={fr}:sample_rate=44100"]
    if style == "D":
        cmd += ["-f", "lavfi", "-t", f"{dur:.2f}", "-i", "anoisesrc=color=pink:amplitude=0.5:sample_rate=44100"]
        fc += (";[4]highpass=f=500,lowpass=f=3500,volume=0.05,afade=t=in:d=2:curve=tri,"
               f"afade=t=out:st={dur - 2:.2f}:d=2[rain];[pad][rain]amix=inputs=2:normalize=0,loudnorm=I=-18:TP=-2:LRA=7[a]")
    else:
        fc += ";[pad]loudnorm=I=-18:TP=-2:LRA=7[a]"
    cmd += ["-filter_complex", fc, "-map", "[a]", "-ac", "2", wav]
    subprocess.run(cmd, check=True)

    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out],
        stdin=subprocess.PIPE)

    for n in range(nframes):
        t = n / FPS
        frame = bg.copy()
        if style == "D":
            for (sp_, bx, by, vx, vy, al, col) in bokeh:
                cx = (bx + vx * t) % W
                cy = (by + vy * t) % H
                pulse = al * (0.8 + 0.2 * math.sin(t * 0.7 + bx))
                blend(frame, sp_, (int(cx - sp_.shape[1] / 2), int(cy - sp_.shape[0] / 2)), pulse, col)
            streak_layer = np.zeros((H, W), np.float32)
            for (sx, sy, v, ln, al) in streaks:
                y = (sy + v * t) % (H + ln) - ln
                x = int(sx + 0.12 * (y))  # slight slant
                if 0 <= x < W - 3:
                    y1, y2 = int(max(y, 0)), int(min(y + ln, H))
                    if y2 > y1:
                        grad = np.linspace(0, al, y2 - y1, dtype=np.float32)
                        streak_layer[y1:y2, x:x + 2] = np.maximum(streak_layer[y1:y2, x:x + 2], grad[:, None])
            frame = frame * (1 - streak_layer[..., None]) + np.array((170, 180, 205), np.float32) * streak_layer[..., None]

        drift = int(-14 * t / dur)  # slow upward drift of the text block
        # tag
        ta = smooth((t - 0.2) / 1.0) * (0.75 if style == "W" else 0.7)
        if style == "W":
            blend(frame, tag, (122, 150), ta, soft)
        else:
            blend(frame, tag, ((W - tag.shape[1]) // 2, 170), ta, soft)
        for i, m in enumerate(masks):
            a = smooth((t - starts[i]) / fade)
            blend(frame, m, (pos[i][0], pos[i][1] + drift), a, ink)
        for j, m in enumerate(smasks):
            a = smooth((t - sstarts[j]) / fade) * 0.85
            blend(frame, m, (spos[j][0], spos[j][1] + drift), a, soft)
        ea = smooth((t - end_card) / 1.0)
        if ea > 0:
            if style == "W":
                blend(frame, foot_a, (122, 1650), ea * 0.9, ink)
                blend(frame, foot_b, (122, 1730), ea * 0.7, soft)
            else:
                blend(frame, foot_a, ((W - foot_a.shape[1]) // 2, 1560), ea * 0.9, ink)
                blend(frame, foot_b, ((W - foot_b.shape[1]) // 2, 1640), ea * 0.7, soft)
        frame = frame + grain[n % 4]
        enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close()
    enc.wait()
    print(f"{out}: {dur:.1f}s, {nframes} frames")


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    build(spec, sys.argv[2])
