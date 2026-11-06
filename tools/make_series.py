#!/usr/bin/env python3
"""Render an original dark-grey Instagram-style DM chat reel (1080x1920, 30fps).
Messages pop in, the other person's typing dots show before each reply, the view scrolls
as the chat grows, a slow camera push-in runs throughout, and a closing line fades in
over the dimmed chat. Pop sounds are synthesised. No logos, no watermark.
Usage: make_dm.py <spec.json> <out.mp4>
"""
import json, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
INTER = "/usr/share/fonts/opentype/inter/Inter-{}.otf"
SERIF = "/usr/share/texmf/fonts/opentype/public/lm/lmroman17-regular.otf"
ITAL = "/usr/share/texmf/fonts/opentype/public/lm/lmroman12-italic.otf"
BG = (20, 20, 22)
RECV = (44, 44, 48)
GREY = (150, 150, 156)

VIEW_TOP, VIEW_BOTTOM = 330, 1520
SIDE = 52
MAXTXT = 650
PADX, PADY = 38, 28


def F(weight, size):
    return ImageFont.truetype(INTER.format(weight), size)


def ease_out_back(p):
    c1, c3 = 1.4, 2.4
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def wrap(text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if cur and font.getlength(t) > maxw:
            lines.append(cur)
            cur = w
        else:
            cur = t
    lines.append(cur)
    return lines


def bubble_image(text, sent, font):
    lines = wrap(text, font, MAXTXT)
    lh = int(font.size * 1.32)
    tw = max(int(font.getlength(l)) for l in lines)
    bw, bh = tw + PADX * 2, lh * len(lines) + PADY * 2 - 6
    ss = 2  # supersample for smooth corners
    im = Image.new("RGBA", (bw * ss, bh * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = min(bh * ss // 2, 46 * ss)
    if sent:
        # soft violet-to-blue gradient like the dark-mode sent bubble
        grad = Image.new("RGB", (bw * ss, bh * ss))
        gd = ImageDraw.Draw(grad)
        for y in range(bh * ss):
            k = y / max(bh * ss - 1, 1)
            gd.line([(0, y), (bw * ss, y)], fill=(int(104 - 36 * k), int(78 + 52 * k), int(236 + 4 * k)))
        mask = Image.new("L", (bw * ss, bh * ss), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw * ss - 1, bh * ss - 1), r, fill=255)
        im.paste(grad, (0, 0), mask)
    else:
        d.rounded_rectangle((0, 0, bw * ss - 1, bh * ss - 1), r, fill=RECV + (255,))
    im = im.resize((bw, bh), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    y = PADY - 6
    for l in lines:
        d.text((PADX, y), l, font=font, fill=(255, 255, 255, 255))
        y += lh
    return im


def build(spec, out):
    msgs = spec["msgs"]
    name = spec.get("name", "Zoya")
    stamp = spec.get("stamp", "11:48 PM")
    closer = spec["closer"]
    f_msg = F("Regular", 50)
    f_small = F("Regular", 26)
    f_name = F("SemiBold", 44)
    f_mid = F("Regular", 30)
    f_input = F("Regular", 34)

    # ---- timeline
    COVER_HOLD, COVER_FADE = 0.9, 0.35
    cover_path = spec.get('cover')
    cover_im = None
    if cover_path:
        for cand in (cover_path, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', cover_path)):
            if os.path.exists(cand):
                cover_im = Image.open(cand).convert('RGB').resize((W, H))
                break
        if cover_im is None:
            raise SystemExit('cover not found: %s' % cover_path)
    cov_off = COVER_HOLD if cover_im is not None else 0.0
    t = 1.0 + cov_off
    ev = []  # dict(kind, sent, img, t_typing, t_show)
    for i, (who, text) in enumerate(msgs):
        sent = who == "S"
        img = bubble_image(text, sent, f_msg)
        read = max(1.5, 0.052 * len(text) + 0.7)
        if not sent:
            ev.append(dict(sent=False, img=img, typing=t, show=t + 0.95, text=text))
            t = t + 0.95 + read
        else:
            ev.append(dict(sent=True, img=img, typing=None, show=t, text=text))
            t = t + read * 0.9
    prev_show = cov_off
    for e in ev:
        if e['sent']:
            dt = min(1.0, max(0.45, 0.032 * len(e['text'])))
            e['ttype'] = max(e['show'] - dt, prev_show + 0.25)
            e['tdur'] = max(e['show'] - e['ttype'], 0.2)
        prev_show = e['show']
    t_close = t + 0.5
    dur = t_close + 4.4
    nframes = int(dur * FPS)

    # ---- layout in content space (y from 0), consecutive spacing
    ys, y = [], 40
    tl_y = 0
    prev = None
    for e in ev:
        h = e["img"].height
        y += 0 if prev is None else (10 if prev == e["sent"] else 26)
        e["y"], e["h"] = y, h
        y += h
        prev = e["sent"]
    seen_y = y + 12
    content_bottom = seen_y + 40

    def x_of(e, scale=1.0):
        w = e["img"].width
        return (W - SIDE - w) if e["sent"] else SIDE

    # scroll offset animates when something new occupies space (typing counts)
    def scroll_target(tt):
        bottom = 0
        for e in ev:
            appear = e["typing"] if e["typing"] is not None else e["show"]
            if tt >= appear:
                bottom = max(bottom, e["y"] + e["h"])
        if tt >= ev[-1]["show"] + 0.9:
            bottom += 52  # room for the "Seen" label
        return max(0, bottom - (VIEW_BOTTOM - VIEW_TOP - 40))

    # precompute a smooth scroll curve by sampling targets
    targets = np.array([scroll_target(n / FPS) for n in range(nframes)], np.float64)
    scroll = np.zeros(nframes)
    cur = 0.0
    for n in range(nframes):
        cur += (targets[n] - cur) * 0.16  # critically damped feel
        scroll[n] = cur

    # ---- static layers
    base = Image.new("RGB", (W, H), BG)
    top = Image.new("RGBA", (W, VIEW_TOP + 60), BG + (255,))
    td = ImageDraw.Draw(top)
    # fade the lower 60px of the header overlay
    for k in range(60):
        td.line([(0, VIEW_TOP + k), (W, VIEW_TOP + k)], fill=BG + (int(255 * (1 - k / 60)),))
    # back chevron
    td.line([(70, 176), (50, 200), (70, 224)], fill=(235, 235, 235, 255), width=5, joint="curve")
    # avatar
    av = Image.new("RGBA", (112 * 3, 112 * 3), (0, 0, 0, 0))
    ad = ImageDraw.Draw(av)
    ad.ellipse((0, 0, 335, 335), fill=(70, 70, 76, 255))
    ad.ellipse((118, 70, 218, 170), fill=(150, 150, 156, 255))
    ad.ellipse((62, 190, 274, 400), fill=(150, 150, 156, 255))
    mask = Image.new("L", av.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 335, 335), fill=255)
    av.putalpha(mask)
    av = av.resize((112, 112), Image.LANCZOS)
    top.paste(av, (112, 144), av)
    td.text((248, 150), name, font=f_name, fill=(245, 245, 245, 255))
    td.text((248, 202), "Active now", font=f_small, fill=GREY + (255,))
    # series badge: title left, episode right, couple under the title
    f_badge = F("SemiBold", 27)
    bx = SIDE
    for ch in "SEEN JUST NOW":
        td.text((bx, 62), ch, font=f_badge, fill=(235, 235, 238, 255))
        bx += f_badge.getlength(ch) + 5
    ep_txt = "EP. %s" % spec["ep"]
    ew = sum(f_badge.getlength(ch) + 5 for ch in ep_txt) - 5
    ex = W - SIDE - ew - 36
    td.rounded_rectangle((ex - 20, 52, W - SIDE, 100), 24, fill=(104, 78, 236, 255))
    for ch in ep_txt:
        td.text((ex, 62), ch, font=f_badge, fill=(255, 255, 255, 255))
        ex += f_badge.getlength(ch) + 5
    td.text((SIDE, 100), spec["couple"], font=f_small, fill=(130, 130, 136, 255))
    bot = Image.new("RGBA", (W, H - VIEW_BOTTOM), BG + (255,))
    bd = ImageDraw.Draw(bot)
    for k in range(60):
        bd.line([(0, -60 + k + 60), (W, -60 + k + 60)], fill=BG + (255,))
    bd.rounded_rectangle((SIDE, 130, W - SIDE, 240), 55, outline=(70, 70, 76, 255), width=3, fill=(30, 30, 33, 255))
    bd.ellipse((SIDE + 20, 150, SIDE + 90, 220), fill=(60, 60, 66, 255))
    hh = "@aneestheauthor"
    bd.text(((W - f_small.getlength(hh)) / 2, 300), hh, font=f_small, fill=(110, 110, 116, 255))
    # fade strip above the input bar
    fade = Image.new("RGBA", (W, 70), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fade)
    for k in range(70):
        fd.line([(0, k), (W, k)], fill=BG + (int(255 * k / 70),))

    stamp_w = f_small.getlength(stamp)

    def draw_typing(frame, ty, tt):
        d = ImageDraw.Draw(frame)
        x0 = SIDE
        d.rounded_rectangle((x0, ty, x0 + 170, ty + 88), 44, fill=RECV)
        for j in range(3):
            ph = tt * 7.0 - j * 0.9
            a = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(ph))
            r = 9 + 3 * (0.5 + 0.5 * math.sin(ph))
            cx, cy = x0 + 45 + j * 40, ty + 44 - 5 * math.sin(ph)
            c = int(110 + 120 * a)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(c, c, c))

    # ---- audio: soft pops
    sr = 44100
    audio = np.zeros(int(dur * sr) + sr, np.float32)

    def pop(at, f0, amp):
        n = int(0.14 * sr)
        tt_ = np.arange(n) / sr
        env = np.exp(-tt_ * 38) * (1 - np.exp(-tt_ * 900))
        s = (np.sin(2 * np.pi * f0 * tt_) + 0.35 * np.sin(2 * np.pi * f0 * 2.01 * tt_)) * env * amp
        i0 = int(at * sr)
        audio[i0:i0 + n] += s.astype(np.float32)

    for e in ev:
        pop(e["show"], 520 if e["sent"] else 780, 0.30)
    # soft swell as the closing line arrives
    n = int(2.2 * sr)
    tt_ = np.arange(n) / sr
    swell = (np.sin(2 * np.pi * 220 * tt_) + 0.6 * np.sin(2 * np.pi * 330 * tt_)) * np.sin(np.pi * tt_ / 2.2) ** 2 * 0.07
    i0 = int(t_close * sr)
    audio[i0:i0 + n] += swell.astype(np.float32)
    wav = out.replace(".mp4", ".wav")
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes((np.clip(audio[:int(dur * sr)], -1, 1) * 32767).astype(np.int16).tobytes())

    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out],
        stdin=subprocess.PIPE)

    # closing card text (serif, matches the Dream Note look)
    f_close = ImageFont.truetype(SERIF, 66)
    f_follow = ImageFont.truetype(ITAL, 46)
    c_lines = wrap(closer, f_close, 840)
    def sp_width(s, f, sp):
        return sum(f.getlength(ch) + sp for ch in s) - sp

    for n in range(nframes):
        tt = n / FPS
        frame = base.copy().convert("RGBA")
        off = scroll[n]
        # timestamp
        ts_a = smooth((tt - 0.3) / 0.6)
        if ts_a > 0:
            ty = VIEW_TOP + 10 - off
            ImageDraw.Draw(frame).text(((W - stamp_w) / 2, ty), stamp, font=f_small, fill=(120, 120, 126, int(255 * ts_a)))
        for e in ev:
            if e["typing"] is not None and e["typing"] <= tt < e["show"]:
                draw_typing(frame, VIEW_TOP + e["y"] - off + (e["h"] - 88) / 2, tt)
            if tt >= e["show"]:
                age = tt - e["show"]
                p = ease_out_back(min(age / 0.30, 1.0))
                sc = 0.86 + 0.14 * p
                a = min(age / 0.16, 1.0)
                im = e["img"]
                w2, h2 = max(1, int(im.width * sc)), max(1, int(im.height * sc))
                im2 = im.resize((w2, h2), Image.BILINEAR) if sc != 1 else im
                if a < 1:
                    al = im2.getchannel("A").point(lambda v: int(v * a))
                    im2 = im2.copy(); im2.putalpha(al)
                x = x_of(e)
                if e["sent"]:
                    x = x + (im.width - w2)
                yy = VIEW_TOP + e["y"] - off + (im.height - h2) + (1 - p) * 26
                frame.alpha_composite(im2, (int(x), int(yy))) if (0 <= int(x) < W and -400 < yy < H) else None
        # seen label
        sa = smooth((tt - (ev[-1]["show"] + 0.9)) / 0.5)
        if sa > 0:
            lab = "Seen just now"
            lw = f_small.getlength(lab)
            ImageDraw.Draw(frame).text((W - SIDE - lw, VIEW_TOP + seen_y - off - 20), lab, font=f_small, fill=GREY + (int(255 * sa),))
        frame.alpha_composite(top, (0, 0))
        frame.alpha_composite(fade, (0, VIEW_BOTTOM - 70))
        frame.alpha_composite(bot, (0, VIEW_BOTTOM))
        # input bar: placeholder, or the next sent message being typed
        typed = None
        for e in ev:
            if e['sent'] and e['ttype'] <= tt < e['show']:
                k = int(len(e['text']) * min((tt - e['ttype']) / e['tdur'] * 1.15, 1.0))
                typed = e['text'][:max(k, 1)]
        idraw = ImageDraw.Draw(frame)
        iy = VIEW_BOTTOM + 160
        if typed is None:
            idraw.text((SIDE + 118, iy), "Message...", font=f_mid, fill=(120, 120, 126, 255))
        else:
            shown = typed
            if f_input.getlength(shown) > 700:
                while f_input.getlength('\u2026' + shown) > 700:
                    shown = shown[1:]
                shown = '\u2026' + shown
            idraw.text((SIDE + 118, iy - 3), shown, font=f_input, fill=(240, 240, 244, 255))
            if int(tt * 3.5) % 2 == 0:
                cx = SIDE + 118 + f_input.getlength(shown) + 4
                idraw.rectangle((cx, iy - 2, cx + 3, iy + 36), fill=(200, 200, 206, 255))
            sx, sy = W - SIDE - 62, VIEW_BOTTOM + 185
            idraw.ellipse((sx - 36, sy - 36, sx + 36, sy + 36), fill=(104, 78, 236, 255))
            idraw.line([(sx, sy + 14), (sx, sy - 14)], fill=(255, 255, 255, 255), width=5)
            idraw.line([(sx - 12, sy - 3), (sx, sy - 15), (sx + 12, sy - 3)], fill=(255, 255, 255, 255), width=5, joint='curve')
        rgb = frame.convert("RGB")
        # slow camera push-in
        z = 1.0 + 0.055 * (tt / dur)
        if z > 1.0005:
            zw, zh = int(W * z), int(H * z)
            rgb = rgb.resize((zw, zh), Image.BILINEAR).crop(((zw - W) // 2, (zh - H) // 2, (zw - W) // 2 + W, (zh - H) // 2 + H))
        # closing card
        ca = smooth((tt - t_close) / 0.9)
        if ca > 0:
            arr = np.asarray(rgb, np.float32) * (1 - 0.95 * ca)
            rgb = Image.fromarray(arr.astype(np.uint8))
            d = ImageDraw.Draw(rgb)
            lh = 88
            total = lh * len(c_lines)
            y0 = 880 - total // 2
            for k, line in enumerate(c_lines):
                la = smooth((tt - t_close - 0.35 - 0.0 * k) / 0.9)
                lw = sp_width(line, f_close, 2)
                x = (W - lw) / 2
                col = int(240 * la)
                for ch in line:
                    d.text((x, y0 + k * lh), ch, font=f_close, fill=(col, col, int(col * 0.97)))
                    x += f_close.getlength(ch) + 2
            fa = smooth((tt - t_close - 1.6) / 0.8)
            if fa > 0:
                txt = spec.get("follow", "Follow for the next episode")
                fw = f_follow.getlength(txt)
                c = int(200 * fa)
                d.text(((W - fw) / 2, y0 + total + 90), txt, font=f_follow, fill=(c, c, c))
                h_ = "@aneestheauthor"
                hw2 = f_small.getlength(h_)
                c2 = int(130 * fa)
                d.text(((W - hw2) / 2, y0 + total + 160), h_, font=f_small, fill=(c2, c2, c2))
        if cover_im is not None and tt < cov_off + COVER_FADE:
            ca2 = 1.0 if tt < cov_off else 1.0 - (tt - cov_off) / COVER_FADE
            rgb = Image.blend(rgb, cover_im, ca2)
        enc.stdin.write(rgb.tobytes())
    enc.stdin.close()
    enc.wait()
    print(f"{out}: {dur:.1f}s, {nframes} frames")


if __name__ == "__main__":
    build(json.load(open(sys.argv[1])), sys.argv[2])
