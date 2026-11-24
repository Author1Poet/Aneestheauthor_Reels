"""Animates a rig: expressions, blinking, saccades, breathing, head motion, pose changes."""
import math, random
from PIL import Image, ImageChops
import rig as R
import imgops
from rig import S, HX, HY

EMOS = {  # raise, tilt, lid, mouth, flush, tear, asym, headdrop, headtilt
    "neutral": dict(raise_=0, tilt=0, lid=.86, mouth="neutral", flush=0, tear=0, asym=0, drop=0, htilt=0),
    "soft": dict(raise_=2, tilt=4, lid=.80, mouth="soft", flush=0, tear=0, asym=0, drop=0, htilt=1.5),
    "worry": dict(raise_=9, tilt=11, lid=1.0, mouth="neutral", flush=0, tear=0, asym=2, drop=0, htilt=-1.5),
    "sad": dict(raise_=3, tilt=13, lid=.64, mouth="frown", flush=.25, tear=0, asym=0, drop=8, htilt=-2.5),
    "cry": dict(raise_=3, tilt=15, lid=.52, mouth="wobble", flush=1, tear=1, asym=1, drop=12, htilt=-3),
    "shock": dict(raise_=15, tilt=0, lid=1.0, mouth="o", flush=0, tear=0, asym=0, drop=-4, htilt=0),
    "smile": dict(raise_=2, tilt=0, lid=.72, mouth="smile", flush=.1, tear=0, asym=0, drop=0, htilt=2),
    "smirk": dict(raise_=5, tilt=-2, lid=.78, mouth="smirk", flush=0, tear=0, asym=5, drop=0, htilt=2.5),
    "tired": dict(raise_=-1, tilt=2, lid=.50, mouth="neutral", flush=0, tear=0, asym=0, drop=6, htilt=-1),
    "nervous": dict(raise_=7, tilt=8, lid=.95, mouth="bite", flush=0, tear=0, asym=3, drop=0, htilt=-1),
    "hurt": dict(raise_=5, tilt=10, lid=.72, mouth="neutral", flush=.15, tear=0, asym=0, drop=6, htilt=-2),
    "relief": dict(raise_=4, tilt=7, lid=.64, mouth="soft", flush=.45, tear=1, asym=0, drop=4, htilt=2),
    "annoyed": dict(raise_=-3, tilt=-7, lid=.66, mouth="neutral", flush=0, tear=0, asym=0, drop=0, htilt=0),
    "laugh": dict(raise_=4, tilt=0, lid=.58, mouth="smile", flush=.2, tear=0, asym=0, drop=0, htilt=3),
}
NUM = ["raise_", "tilt", "lid", "flush", "asym", "drop", "htilt"]


def lerp(a, b, t): return a + (b - a) * t
def sm(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def place(dst, spr, ax, ay, ox, oy, flip=False, rot=0.0, alpha=1.0, scale=None):
    img, x, y = spr
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        x = -(x + img.width / S)  # mirror about anchor
    if rot:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
        # rotate about sprite centre: adjust offset so centre stays
        cx, cy = x + (img.width / S) / 2, y + (img.height / S) / 2
        # approximate: recompute from original centre
        x = (spr[1] + (spr[0].width / S) / 2) - (img.width / S) / 2 * (-1 if False else 1) * 0 - (img.width / S) / 2 + 0
        y = (spr[2] + (spr[0].height / S) / 2) - (img.height / S) / 2
        if flip:
            x = -((spr[1] + (spr[0].width / S) / 2)) - (img.width / S) / 2
    if alpha < 1:
        a = img.getchannel("A").point(lambda v: int(v * alpha))
        img = img.copy()
        img.putalpha(a)
    dst.alpha_composite(img, (int(round((ax + x - ox) * S)), int(round((ay + y - oy) * S)))) if _inside(dst, img, ax + x - ox, ay + y - oy) else _paste_clip(dst, img, ax + x - ox, ay + y - oy)


def _inside(dst, img, px, py):
    x, y = int(round(px * S)), int(round(py * S))
    return x >= 0 and y >= 0 and x + img.width <= dst.width and y + img.height <= dst.height


def _paste_clip(dst, img, px, py):
    x, y = int(round(px * S)), int(round(py * S))
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dst.width, x + img.width), min(dst.height, y + img.height)
    if x1 <= x0 or y1 <= y0:
        return
    crop = img.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    dst.alpha_composite(crop, (x0, y0))


class Actor:
    def __init__(self, name, track, seed=1):
        self.name = name
        self.rig = R.build_rig(name)
        self.c = R.CAST[name]
        self.track = sorted(track, key=lambda k: k["t"])  # keys: t, emo, pose, look, speed, typing(bool span handled by director)
        self.rnd = random.Random(seed * 77 + 5)
        self.seed = seed
        # blink schedule
        self.blinks = []
        t = 0.9 + self.rnd.random() * 1.2
        for _ in range(60):
            dbl = self.rnd.random() < 0.18
            self.blinks.append((t, dbl))
            t += (2.3 + self.rnd.random() * 2.6) * self.c.get("blink", 1.0)
        # saccade schedule (gaze jitter)
        self.sacc = []
        t = 0.3
        for _ in range(120):
            self.sacc.append((t, self.rnd.uniform(-1, 1), self.rnd.uniform(-1, 1)))
            t += self.rnd.uniform(.6, 2.2)

    # --------------- state evaluation
    def keyframe_at(self, t):
        cur = self.track[0]
        prev = self.track[0]
        for k in self.track:
            if k["t"] <= t:
                prev, cur = cur, k
            else:
                break
        if cur is self.track[0]:
            prev = cur
        return prev, cur

    def params(self, t):
        prev, cur = self.keyframe_at(t)
        e0, e1 = EMOS[prev["emo"]], EMOS[cur["emo"]]
        k = sm((t - cur["t"]) / cur.get("blend", 0.28)) if cur is not prev else 1.0
        p = {n: lerp(e0[n], e1[n], k) for n in NUM}
        p["tear"] = e1["tear"] if k > .4 else e0["tear"]
        p["mouth"] = e1["mouth"]
        p["mouth_prev"] = e0["mouth"]
        p["mouth_k"] = k
        p["pose"] = cur.get("pose", "hold")
        p["pose_prev"] = prev.get("pose", "hold") if cur is not prev else p["pose"]
        p["pose_k"] = sm((t - cur["t"]) / 0.30) if cur is not prev else 1.0
        p["look"] = cur.get("look", "phone")
        p["look_since"] = cur["t"]
        p["typing"] = cur.get("typing", False)
        p["since"] = t - cur["t"]
        return p

    def gaze(self, t, p):
        look = p["look"]
        base = {"phone": (0, 6.5), "cam": (0, 0), "away": (7, -2), "up": (1, -6), "down": (0, 9), "left": (-8, 1), "right": (8, 1), "far": (3, 3)}[look]
        gx, gy = base
        # saccades
        s = [x for x in self.sacc if x[0] <= t][-1:]
        if s:
            gx += s[0][1] * (1.6 if look != "phone" else 1.0)
            gy += s[0][2] * (1.2 if look != "phone" else .6)
        if p["typing"]:
            gx += 2.2 * math.sin(t * 9.0)   # reading what is typed
        return gx, gy

    def blink_amt(self, t):
        for (bt, dbl) in self.blinks:
            if bt - 0.02 <= t <= bt + 0.22 + (0.26 if dbl else 0):
                u = t - bt
                if u < 0.10: return max(0, u / 0.10)
                if u < 0.22: return max(0, 1 - (u - 0.10) / 0.12)
                if dbl and 0.26 <= u < 0.48:
                    v = u - 0.26
                    return math.sin(min(1, v / 0.22) * math.pi)
        return 0.0

    # --------------- render
    def render(self, t, light=None):
        r = self.rig
        c = self.c
        p = self.params(t)
        gx, gy = self.gaze(t, p)
        bl = self.blink_amt(t)
        since = p["since"]
        # --- motion
        breath = math.sin(t * 1.55 + self.seed) * 3.0
        sway = math.sin(t * .63 + self.seed * 2) * 1.2 + math.sin(t * 1.1) * .5
        nod = 0.0
        if p["typing"]:
            nod = 3.5 + math.sin(t * 5.3) * 1.2
        elif p["look"] == "phone":
            nod = 2.5
        react = 0.0
        if 0 <= since < .5:
            react = math.sin(min(1, since / .5) * math.pi) * (5 if p["look"] == "phone" else 3)
        drop = p["drop"] + nod + react
        tilt = p["htilt"] + sway + (-math.sin(min(1, since / .7) * math.pi) * 1.5 if 0 <= since < .7 else 0)
        # --- canvas (full char)
        canvas = Image.new("RGBA", (560 * S, 960 * S), (0, 0, 0, 0))
        bob = breath * .6
        # head canvas
        hox, hoy, hw, hh = HX - 200, HY - 250, 400, 640  # head canvas origin / size (canvas coords)
        pivot = ((HX - hox) * S, (690 - hoy) * S)
        # back hair
        if r["hair_back"]:
            hb = Image.new("RGBA", (hw * S, hh * S), (0, 0, 0, 0))
            R_ = r["hair_back"]
            place(hb, R_, 0, 0, hox, hoy)
            hb = imgops.rot(hb, tilt * .2 + math.sin(t * .9 + 1) * .7, ((HX - hox) * S, (HY - 150 - hoy) * S))
            hb = imgops.rot(hb, tilt, pivot)
            canvas.alpha_composite(hb, (hox * S, int((hoy + drop * .6 + bob * .4) * S)))
        # neck + torso
        place(canvas, r["neck"], 0, 0 + drop * .3, 0, 0)
        torso = r["torso"]
        place(canvas, (torso[0], torso[1], torso[2] + bob * .8), 0, 0, 0, 0)
        # pose (under head)
        pose_over = p["pose"] in ("mouth", "face") or p["pose_prev"] in ("mouth", "face")
        under = []
        for nm, a in ((p["pose_prev"], 1 - p["pose_k"]), (p["pose"], p["pose_k"])):
            if p["pose_k"] >= 1 and nm != p["pose"]:
                continue
            if a <= 0.01:
                continue
            under.append((nm, a))
        jitter = 0.0
        if p["typing"]:
            jitter = 2.6 * abs(math.sin(t * 11.0 + math.sin(t * 3.0) * 2))
        lap = 0
        if p["look"] in ("away", "up") and p["pose"] == "hold":
            lap = 36
        for nm, a in under:
            if nm in ("mouth", "face"):
                continue
            real = "hold" if nm == "lap" else nm
            sp = r["poses"][real]
            dy = 74 if nm == "lap" else (lap if nm == "hold" else 0)
            place(canvas, (sp[0], sp[1], sp[2] + bob + jitter + dy), 0, 0, 0, 0, alpha=a)
        # --- head
        head = Image.new("RGBA", (hw * S, hh * S), (0, 0, 0, 0))
        place(head, r["face"], HX, HY, hox, hoy) if False else place(head, r["face"], 0, 0, hox, hoy)
        # flush
        if p["flush"] > .02:
            place(head, r["flush"], 0, 0, hox, hoy, alpha=min(1, p["flush"]))
        ew, eh = c["ew"], c["eh"]
        ex = 46 if c["fw"] < 100 else 48
        ey = HY - 6
        lvl_f = max(0.0, min(1.0, p["lid"] * (1 - bl * .98)))
        lvl = int(round(lvl_f * (R.EYE_LEVELS - 1)))
        sc, ir, lid = r["sclera"], r["iris"], r["lids"][lvl]
        for sg in (-1, 1):
            eye = Image.new("RGBA", (80 * S, 60 * S), (0, 0, 0, 0))
            eye.alpha_composite(sc[0], ((sc[1] + 40) * S, (sc[2] + 30) * S))
            ig = Image.new("RGBA", eye.size, (0, 0, 0, 0))
            gxx = gx * (1 if sg == 1 else 1)
            ig.alpha_composite(ir[0], (int((ir[1] + 40 + gxx) * S), int((ir[2] + 30 + gy * .7) * S)))
            mask = eye.getchannel("A")
            ig.putalpha(ImageChops.multiply(ig.getchannel("A"), mask))
            eye.alpha_composite(ig)
            eye.alpha_composite(lid[0], ((lid[1] + 40) * S, (lid[2] + 30) * S))
            if sg == -1:
                eye = eye.transpose(Image.FLIP_LEFT_RIGHT)
            head.alpha_composite(eye, (int((HX + sg * ex - 40 - hox) * S), int((ey - 30 - hoy) * S)))
        # tears
        if p["tear"]:
            for sg, ph in ((-1, 0.0), (1, 0.45)):
                u = ((t * .9 + ph) % 1.0)
                tx, ty = HX + sg * (ex + 8) - hox, ey + 16 + u * 62 - hoy
                place(head, r["tear"], 0, 0, 0, 0) if False else None
                tr = r["tear"]
                a = math.sin(min(1, u) * math.pi) ** .6
                im = tr[0].copy()
                im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
                head.alpha_composite(im, (int((tx + tr[1]) * S), int((ty + tr[2]) * S)))
        # brows
        bsp = r["brow"]
        by = HY - 52 - p["raise_"] + (-1 if c["tired"] else 0)
        for sg in (-1, 1):
            ang = p["tilt"] + (p["asym"] if sg == 1 else -p["asym"] * .0)
            im = bsp[0]
            if sg == -1:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
                a_pil = ang
            else:
                a_pil = -ang
            im = im.rotate(a_pil, resample=Image.BICUBIC)
            extra = -(p["asym"] if sg == 1 else 0) * .5
            head.alpha_composite(im, (int((HX + sg * (ex + 2) + bsp[1] - hox) * S), int((by + extra + bsp[2] - hoy) * S)))
        # mouth (cross-fade)
        my = HY + 86 + p["drop"] * 0
        ms = r["mouths"]
        mk = p["mouth_k"]
        shake = 0.0
        if p["mouth"] == "wobble":
            shake = math.sin(t * 22) * 1.2
        for nm, a in ((p["mouth_prev"], 1 - mk), (p["mouth"], mk)):
            if a <= .01 or (mk >= 1 and nm != p["mouth"]):
                continue
            m = ms[nm]
            im = m[0]
            if a < 1:
                im = im.copy()
                im.putalpha(im.getchannel("A").point(lambda v, a=a: int(v * a)))
            head.alpha_composite(im, (int((HX + m[1] - hox) * S), int((my + shake + m[2] - hoy) * S)))
        # glasses
        if r["glasses"]:
            g = r["glasses"]
            gl = g[0]
            head.alpha_composite(gl, (int((g[1] - hox) * S), int((g[2] - hoy) * S)))
            if p["look"] == "phone" or p["typing"]:  # screen glow in lenses
                lens = Image.new("RGBA", gl.size, (190, 220, 255, 0))
                a = gl.getchannel("A")
                head.alpha_composite(Image.merge("RGBA", (*lens.split()[:3], a.point(lambda v: int(v * .0)))), (int((g[1] - hox) * S), int((g[2] - hoy) * S)))
        # front hair / hijab
        if r["hair_front"]:
            place(head, r["hair_front"], 0, 0, hox, hoy)
        # head transform
        head = imgops.rot(head, tilt, pivot)
        canvas.alpha_composite(head, (hox * S, int((hoy + drop + bob * .5) * S)))
        # raised-hand poses above head
        for nm, a in ((p["pose_prev"], 1 - p["pose_k"]), (p["pose"], p["pose_k"])):
            if nm in ("mouth", "face") and a > .01 and not (p["pose_k"] >= 1 and nm != p["pose"]):
                sp = r["poses"][nm]
                dy = 0 if nm == p["pose"] else 0
                place(canvas, (sp[0], sp[1], sp[2] + bob), 0, 0, 0, 0, alpha=a)
        out = canvas.resize((560, 960), Image.LANCZOS)
        return out


if __name__ == "__main__":
    import sys
    sheet = Image.new("RGB", (560 * 4, 960 * 2), (70, 60, 80))
    names = ["ammi", "hamza", "sara", "noor"]
    sets = [("neutral", "hold", 3.0), ("cry", "face", 6.0)]
    for r_, (emo, pose, t) in enumerate(sets):
        for i, n in enumerate(names):
            a = Actor(n, [dict(t=0, emo=emo, pose=pose, look="phone")], seed=i + 1)
            im = a.render(t)
            sheet.paste(im, (i * 560, r_ * 960), im)
    sheet.resize((1680, 1440)).save("rigtest.png")
