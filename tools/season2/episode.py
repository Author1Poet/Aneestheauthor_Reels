#!/usr/bin/env python3
"""Director + compositor for the split-screen text-story reels.
usage: episode.py info|frame|render|audio <spec.json> ...
"""
import sys, json, math, subprocess, os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFilter, ImageChops

import rig as R
from actor import Actor, sm
from scenes import Scene
import ui
import imgops

W, H, FPS = 1080, 1920, 30
HH = H // 2
TYPE_SPEED = {"ammi": .052, "hamza": .030, "sara": .024, "noor": .029, "abbu": .075, "zoya": .021, "daniyal": .028, "rayyan": .030}
TONES = {"ammi": "marimba", "hamza": "tok", "sara": "chime", "noor": "ping", "abbu": "boom", "zoya": "bell", "daniyal": "pluck", "rayyan": "drop"}


def clamp(x, a, b): return max(a, min(b, x))


class Episode:
    def __init__(self, spec_path):
        self.spec = json.load(open(spec_path))
        sp = self.spec
        self.names = [R.CAST[c]["name"] for c in sp["chars"]]
        self.side = sp["layout"]
        self.lock_dur = sp["lock"]["dur"] if sp.get("lock") else 0.0
        self.build_timeline()
        self.actors = [Actor(sp["chars"][h], self.tracks[h], seed=h + 1 + sp.get("seed", 0)) for h in (0, 1)]
        self.scenes = [Scene(s["kind"], cx=(280 if self.side[h] == "L" else 800), variant=s.get("variant"), seed=h + 3) for h, s in enumerate(sp["scenes"])]
        self.avatars = [self.make_avatar(h) for h in (0, 1)]
        self.vig = {}
        self.rng = np.random.default_rng(5)
        self.grain = [self.rng.normal(0, 2.4, (H // 2, W // 2, 1)).astype(np.float32) for _ in range(6)]

    # ----------------------------------------------------------------------------- avatars
    def make_avatar(self, h):
        a = Actor(self.spec["chars"][h], [dict(t=0, emo="soft", pose="hold", look="cam")], seed=9)
        im = a.render(1.3)
        face = im.crop((280 - 125, 488 - 175, 280 + 125, 488 + 105)).convert("RGBA")
        sq = Image.new("RGBA", (250, 250), (60, 56, 80, 255))
        sq.alpha_composite(face.crop((0, 15, 250, 265)), (0, 0)) if face.height >= 265 else sq.alpha_composite(face, (0, 0))
        return sq

    # ----------------------------------------------------------------------------- timeline
    def build_timeline(self):
        sp = self.spec
        chars = sp["chars"]
        t = self.lock_dur + sp.get("scene_lead", 0.35)
        self.tracks = [[], []]
        cur = [dict(emo=e, pose="hold", look="phone", typing=False) for e in sp.get("start_emo", ["neutral", "neutral"])]
        for h in (0, 1):
            if sp.get("start_look"):
                cur[h]["look"] = sp["start_look"][h]
            self.tracks[h].append(dict(t=0.0, **cur[h]))
        self.msgs, self.focus, self.sfx, self.notes = [], [], [], []
        T0 = t

        def kf(h, tt, blend=None, **kw):
            cur[h].update(kw)
            d = dict(t=round(tt, 3), **cur[h])
            if blend:
                d["blend"] = blend
            self.tracks[h].append(d)

        for b in sp["beats"]:
            if b["k"] == "beat":
                for h in (0, 1):
                    kws = {}
                    if b.get("emo") and b["emo"][h]: kws["emo"] = b["emo"][h]
                    if b.get("pose") and b["pose"][h]: kws["pose"] = b["pose"][h]
                    if b.get("look") and b["look"][h]: kws["look"] = b["look"][h]
                    if kws:
                        kf(h, t, blend=b.get("blend"), **kws)
                if b.get("focus") is not None:
                    self.focus.append((b["focus"], t - 0.25, t + b["dur"] + 0.2))
                for s_ in b.get("sfx", []):
                    self.sfx.append((t + s_[1], s_[0]))
                t += b["dur"]
                continue
            who = b["who"]
            oth = 1 - who
            text = b.get("text", "")
            burst = b.get("burst", False)
            per = TYPE_SPEED[chars[who]]
            ghost = b.get("ghost")
            body = ghost if ghost else text
            typ = b.get("type") or clamp(0.42 + per * len(body), .75, 1.9)
            if burst:
                typ = clamp(typ * .6, .55, 1.6)
            ts = t + b.get("lead", .12 if burst else .22)
            spans = []
            hes = b.get("hes")
            if hes:
                a1 = typ * hes[0]
                spans.append((ts, ts + a1))
                spans.append((ts + a1 + hes[1], ts + a1 + hes[1] + typ * (1 - hes[0]) + .3))
                ta = spans[-1][1] + .05
                kf(who, ts, typing=True, look="phone")
                kf(who, spans[0][1], typing=False, look=hes[2] if len(hes) > 2 else "away")
                kf(who, spans[1][0], typing=True, look="phone")
            else:
                spans.append((ts, ts + typ))
                ta = ts + typ + .05
                kf(who, ts, typing=True, look="phone", **({"emo": b["pre"][0]} if b.get("pre") else {}))
            if ghost:
                # typed, held, deleted — nothing is sent
                dele = 0.9
                spans = [(ts, ts + typ)]
                hold = b.get("ghost_hold", .9)
                m = dict(who=who, text="", ghost=ghost, ts=ts, ta=None, spans=spans, hold_end=ts + typ + hold, del_end=ts + typ + hold + dele)
                self.msgs.append(m)
                kf(who, ts + typ + hold * .4, emo=b["emo"][0] if b.get("emo") else cur[who]["emo"], look="away")
                kf(who, ts + typ + hold + dele, typing=False, look="phone")
                if b.get("emo") and b["emo"][1]:
                    kf(oth, ts + typ + hold + dele, emo=b["emo"][1])
                t = ts + typ + hold + dele + b.get("pause", .6)
                continue
            m = dict(who=who, text=text, ghost=None, ts=ts, ta=ta, spans=spans)
            self.msgs.append(m)
            emo = b.get("emo", [None, None])
            pose = b.get("pose", [None, None])
            kws_s = dict(typing=False, look=b.get("look", [None, None])[0] or "phone")
            if emo[0]: kws_s["emo"] = emo[0]
            if pose[0]: kws_s["pose"] = pose[0]
            kf(who, ta, **kws_s)
            kws_r = dict(look=b.get("look", [None, None])[1] or "phone")
            if emo[1]: kws_r["emo"] = emo[1]
            if pose[1]: kws_r["pose"] = pose[1]
            kf(oth, ta + .02, **kws_r)
            read = clamp(.38 + .011 * len(text), .55, 1.15)
            pause = b.get("pause", .3 if burst else read)
            # revert special poses
            stay = b.get("stay", 1.9)
            for h, pz in ((who, pose[0]), (oth, pose[1])):
                if pz and pz != "hold" and not b.get("keep"):
                    kf(h, ta + stay, pose="hold")
            if b.get("focus") is not None:
                self.focus.append((b["focus"], ta - .5, ta + pause + .9))
            self.sfx.append((ta, "msg"))
            t = ta + pause
        self.end_msgs = t + sp.get("end_pad", .9)
        self.dur = self.end_msgs + sp.get("closer_hold", 4.0)
        for h in (0, 1):
            self.tracks[h].sort(key=lambda k: k["t"])
        # panel intervals
        hold = 2.7
        self.panel = [[], []]
        self.banners = [[], []]
        for h in (0, 1):
            ev = []
            for m in self.msgs:
                if m["who"] == h:
                    ev.append((m["ts"] - .25, (m["ta"] or m["del_end"]) + .1, False))
                elif m["ta"] is not None:
                    ev.append((m["ta"], m["ta"] + .1, True))
            ev.sort()
            ivs = []
            for (a, b_, recv) in ev:
                if ivs and a <= ivs[-1][1] + hold:
                    ivs[-1][1] = max(ivs[-1][1], b_)
                else:
                    ivs.append([a, b_, recv])
            for iv in ivs:
                iv[1] += hold
                if iv[2]:
                    self.banners[h].append(iv[0])
                    iv.append(iv[0] + .38)  # panel opens after banner
                else:
                    iv.append(iv[0])
            self.panel[h] = ivs
        # sfx for typing/keys/banners
        for m in self.msgs:
            for (a, b_) in m["spans"]:
                self.sfx.append((a, ("keys", b_ - a, m["who"])))
        for h in (0, 1):
            for tb in self.banners[h]:
                self.sfx.append((tb, ("banner", h)))

    # ----------------------------------------------------------------------------- state queries
    def nvis(self, t):
        return sum(1 for m in self.msgs if m["ta"] is not None and m["ta"] <= t)

    def sent_msgs(self):
        return [(m["who"], m["text"]) for m in self.msgs if m["ta"] is not None]

    def input_state(self, h, t):
        for m in self.msgs:
            if m["who"] != h:
                continue
            if m["ghost"] is not None:
                if m["ts"] <= t < m["del_end"]:
                    typ_end = m["spans"][0][1]
                    if t < typ_end:
                        p = (t - m["ts"]) / (typ_end - m["ts"])
                        return m["ghost"][:int(len(m["ghost"]) * p)]
                    if t < m["hold_end"]:
                        return m["ghost"]
                    p = (t - m["hold_end"]) / (m["del_end"] - m["hold_end"])
                    return m["ghost"][:int(len(m["ghost"]) * (1 - p))]
                continue
            if m["ts"] <= t < m["ta"]:
                tot = sum(b - a for a, b in m["spans"])
                done = 0
                for a, b in m["spans"]:
                    if t >= b: done += b - a
                    elif t >= a: done += t - a
                p = clamp(done / tot * 1.04, 0, 1)
                return m["text"][:int(len(m["text"]) * p + .5)]
        return ""

    def typing_dots(self, h, t):
        """is the other person typing right now (shown on h's phone)?"""
        for m in self.msgs:
            if m["who"] == h:
                continue
            for (a, b) in m["spans"]:
                if a <= t < b:
                    if m["ghost"] is not None and t > m["spans"][0][1] + .35:
                        continue
                    return (t * 1.6) % 1.0
        return None

    def panel_state(self, h, t):
        """returns (visible, open_progress 0..1, banner_t or None)"""
        for iv in self.panel[h]:
            start, end, recv, open_t = iv
            if start - .02 <= t <= end + .4:
                banner = None
                if recv and start <= t < start + 1.6:
                    banner = t - start
                if t < open_t:
                    return False, 0.0, banner
                op = spring_(t - open_t, .5)
                cl = sm((end + .3 - t) / .3)
                return True, min(op, cl if cl < 1 else 9), banner, cl
        return False, 0.0, None

    def focus_env(self, h, t):
        f = 0.0
        for (hh, a, b) in self.focus:
            if hh == h:
                f = max(f, sm((t - a) / .7) * sm((b - t) / .7))
        return f

    # ----------------------------------------------------------------------------- lighting
    def light(self, h, img, t):
        sc = self.scenes[h]
        mood = sc.mood
        a = np.asarray(img, np.float32)
        rgb = a[..., :3] * np.array(mood["tint"], np.float32)
        alpha = a[..., 3:4] / 255.0
        hh_, ww_ = a.shape[:2]
        xs = np.linspace(0, 1, ww_, dtype=np.float32)[None, :, None]
        side = xs if mood["key_dir"] > 0 else (1 - xs)
        key = np.array(mood["key"], np.float32)
        rgb = rgb + key * mood["key_k"] * (side ** 1.6) * alpha * 255 / 255.0 * 0.9
        # phone glow from below on face/chest
        p = self.actors[h].params(t)
        on = 1.0 if (p["look"] == "phone" or p["typing"]) else .35
        ys = np.linspace(0, 1, hh_, dtype=np.float32)[:, None, None]
        glow = np.exp(-((ys * 960 - 800) ** 2) / (2 * 190 ** 2)) * np.exp(-((xs * 560 - 280) ** 2) / (2 * 240 ** 2))
        rgb = rgb + np.array([100, 150, 255], np.float32) * glow * np.clip((0.86 - ys) * 8, 0, 1) * alpha * 0.20 * on
        # contact darkening toward the bottom
        rgb = rgb * (1 - 0.18 * ys ** 3)
        out = np.concatenate([np.clip(rgb, 0, 255), a[..., 3:4]], axis=2).astype(np.uint8)
        return Image.fromarray(out, "RGBA")

    # ----------------------------------------------------------------------------- compose
    def half_frame(self, h, t):
        sp = self.spec
        sc = self.scenes[h]
        bg = sc.render(t)
        ch = self.lit(h, t)
        layer = Image.new("RGBA", (W, HH), (0, 0, 0, 0))
        x0 = 0 if self.side[h] == "L" else 520
        layer.alpha_composite(ch, (x0, 0))
        prog = t / self.dur
        f = self.focus_env(h, t)
        fx = 280 if self.side[h] == "L" else 800
        z_bg = 1 + .035 * prog + .06 * f
        z_ch = 1 + .05 * prog + .16 * f
        dx = 3 * math.sin(t * .5 + h)
        dy = 2 * math.sin(t * .37 + h * 2)

        def zoom(im, z, px, py):
            return imgops.zoom(im, z, px, py, dx, dy)

        bgz = zoom(bg, z_bg, fx, 500)
        chz = zoom(layer, z_ch, fx, 470)
        # handheld drift on both (tiny)
        out = Image.alpha_composite(bgz, chz)
        # panel + banner
        ps = self.panel_state(h, t)
        if ps[0] or (len(ps) > 2 and ps[2] is not None):
            self.draw_panel(out, h, t, ps)
        arr = np.asarray(out.convert("RGB"), np.float32)
        key = (round(sc.vig, 2))
        if key not in self.vig:
            yy, xx = np.mgrid[0:HH, 0:W]
            r = np.hypot((xx - W / 2) / (W / 2), (yy - HH * .5) / (HH / 2 * 1.05))
            self.vig[key] = (1 - sc.vig * np.clip(r - .35, 0, 1) ** 1.6).astype(np.float32)[..., None]
        ex = getattr(sc, 'expo', 1.0)
        arr = (arr * ex + (ex - 1) * 14) * self.vig[key]
        f_other = self.focus_env(1 - h, t)
        if f_other > 0:
            gray = arr.mean(axis=2, keepdims=True)
            arr = (arr * (1 - .35 * f_other) + gray * .35 * f_other) * (1 - .42 * f_other)
        return arr

    def lit(self, h, t):
        key = (h, round(t * 30))
        im = self.actors[h].render(t)
        return self.light(h, im, t)

    def draw_panel(self, out, h, t, ps):
        sp = self.spec
        side = self.side[h]
        pcx = 800 if side == "L" else 280
        pcy = 478
        vis, op = ps[0], ps[1]
        if vis:
            cl = ps[3] if len(ps) > 3 else 1.0
            nv = self.nvis(t)
            typed = self.input_state(h, t)
            dots = self.typing_dots(h, t)
            last = None
            seen = False
            mine = [m for m in self.msgs if m["ta"] is not None and m["ta"] <= t]
            if mine and mine[-1]["who"] == h and t > mine[-1]["ta"] + 1.0:
                seen = True
            caret = int(t * 2.2) % 2 == 0 and bool(typed)
            newa = 1.0
            if nv:
                last_m = [m for m in self.msgs if m["ta"] is not None][nv - 1]
                newa = sm((t - last_m["ta"]) / .22)
            ph = ui.phone_img((h, sp.get("id", 0)), self.names[1 - h], self.avatars[1 - h], self.sent_msgs(), h, nv, dots, typed, caret, seen, sp.get("time_label", ""), newa)
            # motion
            bump, rot = 0.0, 0.0
            if nv:
                dt = t - last_m["ta"]
                if dt >= 0:
                    if last_m["who"] == h:
                        bump = .025 * math.exp(-dt * 9) * math.sin(dt * 26)
                    else:
                        bump = .035 * math.exp(-dt * 8) * math.sin(dt * 28)
                        rot = 2.6 * math.exp(-dt * 7) * math.sin(dt * 36)
            s = (.55 + .45 * min(op, 1.0) ** 1.0 if op < 1 else 1.0) * (1 + bump)
            s = (0.55 + 0.45 * min(1.0, op)) + (op - 1) * .06 if op > 1 and op < 3 else s
            s = max(.2, min(1.06, s))
            alpha = min(1.0, op * 2.2) * (cl if cl < 1 else 1.0)
            slide = (1 - min(1.0, op)) * (60 if side == "L" else -60) + (1 - (cl if cl < 1 else 1.0)) * (50 if side == "L" else -50)
            if abs(rot) > .05:
                ph = ph.rotate(rot, resample=Image.BICUBIC)
            if abs(s - 1) > .002:
                ph = ph.resize((int(ph.width * s), int(ph.height * s)), Image.BICUBIC)
            if alpha < 1:
                ph = ph.copy()
                ph.putalpha(ph.getchannel("A").point(lambda v: int(v * alpha)))
            out.alpha_composite(ph, (int(pcx + slide - ph.width / 2), int(pcy - ph.height / 2)))
        # banner
        if len(ps) > 2 and ps[2] is not None:
            bt = ps[2]
            m_ = [m for m in self.msgs if m["ta"] is not None and abs(m["ta"] - (t - bt)) < .02]
            if m_:
                bn = ui.banner_img(self.names[1 - h], m_[0]["text"], self.avatars[1 - h])
                y_in = sm(bt / .3)
                y_out = sm((1.55 - bt) / .25)
                yy = -140 + 230 * y_in
                bn = bn.copy()
                bn.putalpha(bn.getchannel("A").point(lambda v: int(v * y_out)))
                out.alpha_composite(bn, (int(W / 2 - bn.width / 2), int(yy - 20 + (1 - y_out) * -40)))

    def hud(self, img, t):
        d = ImageDraw.Draw(img, "RGBA")
        f = ui.font(ui.F_SEMI, 27)
        sp = self.spec
        for h in (0, 1):
            label = f'{self.names[h]}  ·  {sp["places"][h]}'
            tw = f.getlength(label)
            a = int(150 * sm((t - self.lock_dur - .1) / .5))
            y0 = 36 + h * HH
            d.rounded_rectangle([34, y0, 34 + tw + 44, y0 + 52], 26, fill=(0, 0, 0, a))
            if a > 20:
                d.text((56, y0 + 26), label, font=f, fill=(255, 255, 255, min(255, a * 2)), anchor="lm")
        hd = "@aneestheauthor"
        f2 = ui.font(ui.F_SEMI, 25)
        tw = f2.getlength(hd)
        d.rectangle([0, HH - 3, W, HH + 3], fill=(8, 8, 12, 255))
        d.rounded_rectangle([W / 2 - tw / 2 - 26, HH - 23, W / 2 + tw / 2 + 26, HH + 23], 23, fill=(12, 12, 16, 240))
        d.text((W / 2, HH), hd, font=f2, fill=(240, 240, 246), anchor="mm")

    def closer(self, img, t):
        sp = self.spec
        a = sm((t - self.end_msgs) / .7)
        if a <= 0:
            return
        dim = Image.new("RGBA", (W, H), (6, 6, 10, int(205 * a)))
        img.alpha_composite(dim)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fc = ui.font(ui.ITALIC, 78)
        lines = sp["closer"]
        y0 = H / 2 - (len(lines) - 1) * 56 - 90
        for i, ln in enumerate(lines):
            la = sm((t - self.end_msgs - .35 - i * .55) / .6)
            if la <= 0: continue
            tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ui.text_shadow(tmp, (W / 2, y0 + i * 112 + (1 - la) * 22), ln, fc, (255, 236, 205, 255), blur=8, k=200)
            tmp.putalpha(tmp.getchannel("A").point(lambda v, la=la: int(v * la)))
            lay.alpha_composite(tmp)
        ca = sm((t - self.end_msgs - .35 - len(lines) * .55 - .4) / .6)
        if ca > 0:
            tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(tmp)
            cta = sp.get("cta", "Send this to someone")
            f3 = ui.font(ui.F_SEMI, 38)
            tw = f3.getlength(cta)
            yy = H / 2 + 190
            d.rounded_rectangle([W / 2 - tw / 2 - 44, yy - 44, W / 2 + tw / 2 + 44, yy + 44], 44, fill=(255, 214, 90, 255))
            d.text((W / 2, yy), cta, font=f3, fill=(24, 20, 26), anchor="mm")
            d.text((W / 2, yy + 120), "@aneestheauthor", font=ui.font(ui.F_SEMI, 36), fill=(236, 232, 226), anchor="mm")
            d.text((W / 2, yy + 175), sp.get("follow", "New episode every night at 10 PM"), font=ui.font(ui.F_REG, 30), fill=(190, 188, 196), anchor="mm")
            tmp.putalpha(tmp.getchannel("A").point(lambda v: int(v * ca)))
            lay.alpha_composite(tmp)
        img.alpha_composite(lay)

    def split_frame(self, t):
        top = self.half_frame(0, t)
        bot = self.half_frame(1, t)
        full = np.concatenate([top, bot], axis=0)
        return full

    def post(self, arr, t, idx):
        # bloom
        small = cv2.resize(arr, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
        lum = small.mean(axis=2, keepdims=True)
        hi = np.clip(small - 200, 0, None) * (lum > 205)
        bl = cv2.GaussianBlur(hi, (0, 0), 7)
        bl = cv2.resize(bl, (W, H), interpolation=cv2.INTER_LINEAR)
        arr = arr + bl * .55
        g = self.grain[idx % 6]
        g = cv2.resize(g, (W, H), interpolation=cv2.INTER_NEAREST)[..., None]
        arr = arr + g
        return np.clip(arr, 0, 255).astype(np.uint8)

    def frame(self, t, idx=0):
        L = self.lock_dur
        sp = self.spec
        if L and t < L + .35:
            lock = ui.lock_screen((W, H), sp["lock"], t)
            hk = ui.hook_text((W, H), sp["hook"], t, y0=sp.get("hook_y", 1500), fsize=sp.get("hook_size", 78))
            lock.alpha_composite(hk)
            lock_rgb = np.asarray(lock.convert("RGB"), np.float32)
            if t < L - .15:
                return self.post(lock_rgb, t, idx)
            sp_arr = self.split_frame(t)
            sp_im = Image.fromarray(np.clip(sp_arr, 0, 255).astype(np.uint8))
            u = sm((t - (L - .15)) / .5)
            z = 1.10 - .10 * u
            a = 1 / z
            sp_im = sp_im.transform(sp_im.size, Image.AFFINE, (a, 0, W / 2 - a * W / 2, 0, a, H / 2 - a * H / 2), resample=Image.BICUBIC)
            lz = 1 + .12 * u
            la = 1 / lz
            lk = Image.fromarray(lock_rgb.astype(np.uint8)).transform((W, H), Image.AFFINE, (la, 0, W / 2 - la * W / 2, 0, la, H / 2 - la * H / 2), resample=Image.BICUBIC)
            arr = np.asarray(sp_im, np.float32) * u + np.asarray(lk, np.float32) * (1 - u)
            arr = arr * (1 + .35 * math.sin(u * math.pi))
            im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
            self.hud(im, t)
            return self.post(np.asarray(im.convert("RGB"), np.float32), t, idx)
        arr = self.split_frame(t)
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
        self.hud(im, t)
        self.closer(im, t)
        if t > self.dur - .45:
            k = sm((t - (self.dur - .45)) / .45)
            im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * k))))
        return self.post(np.asarray(im.convert("RGB"), np.float32), t, idx)


def spring_(x, dur):
    if x <= 0: return 0.0
    u = min(1.0, x / dur)
    if u >= 1: return 3.0 if x > dur + 5 else 1.0 + 0.0
    return 1 - math.exp(-6 * u) * math.cos(9 * u) if True else u


def main():
    cmd = sys.argv[1]
    ep = Episode(sys.argv[2])
    if cmd == "info":
        print(round(ep.dur, 2), "s", int(ep.dur * FPS), "frames")
        for m in ep.msgs:
            print(round(m["ts"], 2), None if m["ta"] is None else round(m["ta"], 2), m["who"], m["text"] or ("<ghost> " + m["ghost"]))
        print("panel", ep.panel)
    elif cmd == "frame":
        t = float(sys.argv[4])
        Image.fromarray(ep.frame(t, int(t * 30))).save(sys.argv[3])
    elif cmd == "render":
        out, n0, n1 = sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
        tmp = out.replace(".mp4", ".tmp.mp4")
        p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                              "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
        for n in range(n0, n1):
            p.stdin.write(ep.frame(n / FPS, n).tobytes())
        p.stdin.close()
        if p.wait() == 0:
            os.rename(tmp, out)
    elif cmd == "audio":
        import audio
        audio.make(ep, sys.argv[3])


if __name__ == "__main__":
    main()
