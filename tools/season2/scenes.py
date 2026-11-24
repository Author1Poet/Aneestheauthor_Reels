"""Cinematic backgrounds: authored in SVG (gradients, blur), animated with rain, twinkle, flicker, steam, headlight sweeps."""
import math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from rig import rsvg, lin, rad

W, HH = 1080, 960


def svg(body, defs=""):
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {HH}" width="{W}" height="{HH}"><defs>{defs}'
         '<filter id="b4"><feGaussianBlur stdDeviation="4"/></filter><filter id="b8"><feGaussianBlur stdDeviation="8"/></filter>'
         '<filter id="b16"><feGaussianBlur stdDeviation="16"/></filter><filter id="b30"><feGaussianBlur stdDeviation="30"/></filter>'
         '<filter id="b60"><feGaussianBlur stdDeviation="60"/></filter></defs>' + body + '</svg>')
    return rsvg(s, W, HH)


def glowdot(sprite_cache={}):
    if "g" not in sprite_cache:
        n = 64
        y, x = np.mgrid[0:n, 0:n]
        d = np.hypot(x - n / 2 + .5, y - n / 2 + .5) / (n / 2)
        a = np.clip(1 - d, 0, 1) ** 2
        im = np.zeros((n, n, 4), np.uint8)
        im[..., :3] = 255
        im[..., 3] = (a * 255).astype(np.uint8)
        sprite_cache["g"] = Image.fromarray(im)
    return sprite_cache["g"]


def tint(img, col, a):
    r = Image.new("RGBA", img.size, col + (0,))
    r.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    return r


class Scene:
    def __init__(self, kind, cx=320, variant=None, seed=1):
        self.kind = kind
        self.cx = cx
        self.rnd = random.Random(seed)
        self.rain = None
        self.twinkles = []
        self.glows = []   # (layer, flicker_amount, speed, phase)
        self.steam = None
        self.sweep = None
        self.motes = [(self.rnd.uniform(0, W), self.rnd.uniform(0, HH), self.rnd.uniform(.3, 1.2), self.rnd.uniform(0, 6.28), self.rnd.uniform(6, 22)) for _ in range(34)]
        getattr(self, "build_" + kind)(variant)
        self.rain_streaks = None
        if self.rain:
            x0, y0, x1, y1, dens = self.rain
            r = self.rnd
            self.rain_streaks = [(r.uniform(x0, x1), r.uniform(0, 1), r.uniform(110, 260), r.uniform(26, 78), r.uniform(.5, 1.0)) for _ in range(int(dens))]
            self.static_drops = [(r.uniform(x0, x1), r.uniform(y0, y1), r.uniform(2, 5)) for _ in range(int(dens * 1.4))]

    # ------------------------------------------------------------ builders
    def build_livingroom(self, v):
        d = (lin("wall", [(0, "#46323c", 1), (1, "#271c27", 1)]) + lin("floor", [(0, "#2e2024", 1), (1, "#1a1216", 1)]) +
             lin("sofa", [(0, "#58664e", 1), (1, "#364232", 1)]) + lin("sofa2", [(0, "#657458", 1), (1, "#3f4c3a", 1)]) +
             lin("curt", [(0, "#7a2a3c", 1), (.5, "#5e1f2f", 1), (1, "#7a2a3c", 1)], 0, 0, 1, 0) +
             lin("win", [(0, "#0d1530", 1), (1, "#243456", 1)]) + rad("shade", [(0, "#ffe6b0", 1), (1, "#f0b060", 1)]) +
             lin("vig", [(0, "#000", .0), (1, "#000", .55)], 0, .5, 0, 1))
        b = ['<rect width="1080" height="960" fill="url(#wall)"/>']
        # wallpaper subtle stripes
        for x in range(0, 1080, 90):
            b.append(f'<rect x="{x}" y="0" width="44" height="960" fill="#fff" opacity=".018"/>')
        # window + city
        b.append('<rect x="696" y="96" width="320" height="470" rx="8" fill="url(#win)"/>')
        rnd = random.Random(3)
        for i in range(34):
            x, y = rnd.uniform(710, 1004), rnd.uniform(330, 560)
            col = rnd.choice(["#ffcf86", "#ffb866", "#9fc6ff", "#ffe9b0"])
            b.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rnd.uniform(3, 8):.0f}" fill="{col}" opacity="{rnd.uniform(.4, .9):.2f}" filter="url(#b4)"/>')
        b.append('<rect x="696" y="96" width="320" height="470" rx="8" fill="none" stroke="#2a1d22" stroke-width="12"/><line x1="856" y1="96" x2="856" y2="566" stroke="#2a1d22" stroke-width="8"/><line x1="696" y1="330" x2="1016" y2="330" stroke="#2a1d22" stroke-width="8"/>')
        for x0, wd in ((636, 86), (990, 96)):
            b.append(f'<rect x="{x0}" y="60" width="{wd}" height="720" fill="url(#curt)"/>')
            for k in range(5):
                b.append(f'<rect x="{x0 + k * wd / 5 + 4}" y="60" width="4" height="720" fill="#000" opacity=".22"/>')
        b.append('<rect x="620" y="52" width="476" height="12" rx="6" fill="#c9a24a"/>')
        # clock
        b.append('<circle cx="430" cy="190" r="70" fill="#e9dcc0" stroke="#7a5a30" stroke-width="10"/>')
        for k in range(12):
            a = k * math.pi / 6
            b.append(f'<line x1="{430 + 56 * math.sin(a):.1f}" y1="{190 - 56 * math.cos(a):.1f}" x2="{430 + 64 * math.sin(a):.1f}" y2="{190 - 64 * math.cos(a):.1f}" stroke="#4a3320" stroke-width="3"/>')
        b.append(f'<line x1="430" y1="190" x2="{430 + 36 * math.sin(math.radians(36)):.1f}" y2="{190 - 36 * math.cos(math.radians(36)):.1f}" stroke="#2a1c10" stroke-width="6" stroke-linecap="round"/>')
        b.append(f'<line x1="430" y1="190" x2="{430 + 54 * math.sin(math.radians(72)):.1f}" y2="{190 - 54 * math.cos(math.radians(72)):.1f}" stroke="#2a1c10" stroke-width="4" stroke-linecap="round"/><circle cx="430" cy="190" r="5" fill="#2a1c10"/>')
        # frames
        for (x, y, w, h) in ((90, 110, 150, 190), (270, 150, 120, 150)):
            b.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#7a5a30"/><rect x="{x + 10}" y="{y + 10}" width="{w - 20}" height="{h - 20}" fill="#cdb48a"/>')
            b.append(f'<circle cx="{x + w * .36}" cy="{y + h * .45}" r="{w * .10}" fill="#6a5238"/><circle cx="{x + w * .64}" cy="{y + h * .45}" r="{w * .10}" fill="#6a5238"/>'
                     f'<path d="M{x + w * .22},{y + h - 14} C{x + w * .24},{y + h * .62} {x + w * .48},{y + h * .6} {x + w * .5},{y + h - 14} Z" fill="#6a5238"/>'
                     f'<path d="M{x + w * .5},{y + h - 14} C{x + w * .52},{y + h * .62} {x + w * .76},{y + h * .6} {x + w * .78},{y + h - 14} Z" fill="#6a5238"/>')
        # floor
        b.append('<rect x="0" y="858" width="1080" height="102" fill="url(#floor)"/>')
        # sofa
        b.append('<rect x="-60" y="500" width="860" height="470" rx="90" fill="url(#sofa)"/>')
        b.append('<rect x="-20" y="540" width="780" height="420" rx="70" fill="url(#sofa2)"/>')
        for x in (40, 160, 280, 400, 520, 640):
            for y in (590, 700, 810):
                b.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#2c3628" opacity=".6"/>')
        b.append('<rect x="640" y="640" width="190" height="330" rx="46" fill="#4b5844"/>')
        # throw blanket
        b.append('<path d="M640,620 C700,600 790,640 800,720 L760,960 L640,960 Z" fill="#e8dcc0"/>')
        for k in range(8):
            b.append(f'<path d="M{650 + k * 18},640 L{640 + k * 15},960" stroke="#b5432f" stroke-width="5" opacity=".7"/>')
        # side table + lamp
        b.append('<rect x="-20" y="650" width="190" height="310" rx="12" fill="#3a2a22"/><rect x="-20" y="640" width="190" height="20" rx="8" fill="#5a4030"/>')
        b.append('<rect x="76" y="470" width="12" height="170" fill="#3a2a22"/><path d="M20,470 L144,470 L116,370 L48,370 Z" fill="url(#shade)"/>')
        # cup
        b.append('<ellipse cx="112" cy="632" rx="42" ry="12" fill="#e8e0d0"/><path d="M70,590 L154,590 L146,632 C130,644 94,644 78,632 Z" fill="#f0e8dc"/><ellipse cx="112" cy="591" rx="42" ry="10" fill="#b0743c"/><path d="M152,600 C176,600 176,628 148,626" stroke="#f0e8dc" stroke-width="7" fill="none"/>')
        body = "".join(b)
        self.static = svg(body, d)
        lamp = svg('<ellipse cx="82" cy="420" rx="330" ry="360" fill="#ffb868" opacity=".55" filter="url(#b60)"/><ellipse cx="82" cy="420" rx="120" ry="140" fill="#ffe0a0" opacity=".7" filter="url(#b30)"/>'
                   '<path d="M20,470 L144,470 L420,960 L-200,960 Z" fill="#ffc47a" opacity=".16" filter="url(#b16)"/>')
        self.glows.append((lamp, .10, 1.7, 0.0))
        win = svg('<ellipse cx="856" cy="330" rx="250" ry="300" fill="#6f8cff" opacity=".18" filter="url(#b60)"/>')
        self.glows.append((win, .05, .4, 2.0))
        self.rain = (700, 100, 1012, 562, 56)
        self.steam = (112, 584)
        self.vig = .55
        self.mood = dict(tint=(1.0, .93, .88), key=(255, 190, 120), key_dir=-1, key_k=.30)

    def build_car(self, v):
        v = v or "pump"
        cx = self.cx
        d = (lin("sky", [(0, "#070a18", 1), (1, "#141a30", 1)]) + lin("seat", [(0, "#2b2830", 1), (1, "#15141a", 1)]) +
             lin("glass", [(0, "#8fb0ff", .10), (1, "#8fb0ff", .02)]) + lin("dash", [(0, "#16161c", 1), (1, "#0a0a0e", 1)]))
        b = ['<rect width="1080" height="960" fill="url(#sky)"/>']
        ext = []
        rnd = random.Random(7)
        if v == "pump":
            # canopy lights, pumps, neon sign
            ext.append('<rect x="120" y="150" width="900" height="26" fill="#eaffee" opacity=".95"/><rect x="120" y="176" width="900" height="70" fill="#bfe8d0" opacity=".16"/>')
            for x in range(170, 1000, 110):
                ext.append(f'<rect x="{x}" y="148" width="64" height="12" fill="#fff"/>')
            ext.append('<rect x="140" y="250" width="860" height="14" fill="#2c3a30" opacity=".8"/>')
            for x, c in ((260, "#e03a3a"), (520, "#e03a3a"), (780, "#e03a3a")):
                ext.append(f'<rect x="{x}" y="320" width="84" height="170" rx="8" fill="{c}" opacity=".85"/><rect x="{x + 10}" y="334" width="64" height="38" fill="#8fffb0" opacity=".9"/>')
            ext.append('<rect x="780" y="70" width="190" height="64" rx="10" fill="#e8243c" opacity=".95"/><rect x="800" y="84" width="150" height="36" rx="6" fill="#ffd6dc" opacity=".85"/>')
            ext.append('<circle cx="170" cy="110" r="22" fill="#3cff8a" opacity=".9"/>')
            ext.append('<rect x="0" y="500" width="1080" height="130" fill="#0c1220"/>')
            for x in range(150, 1000, 120):
                ext.append(f'<rect x="{x}" y="504" width="22" height="120" fill="#cfeedd" opacity=".12" filter="url(#b8)"/>')
            ext.append('<rect x="120" y="150" width="900" height="26" fill="#fff" opacity=".5" filter="url(#b16)"/>')
            self.mood = dict(tint=(.95, 1.0, 1.05), key=(150, 230, 190), key_dir=-1, key_k=.10)
            self.sweep = (130, 60, 1000, 560)
        else:  # street, house with lit window
            ext.append('<ellipse cx="170" cy="150" rx="260" ry="260" fill="#ff9a40" opacity=".42" filter="url(#b60)"/>')
            ext.append('<rect x="162" y="140" width="10" height="470" fill="#06080e"/><path d="M110,140 L224,140 L196,110 L138,110 Z" fill="#06080e"/>')
            ext.append('<ellipse cx="168" cy="144" rx="30" ry="12" fill="#ffd9a0"/>')
            ext.append('<rect x="520" y="200" width="460" height="360" fill="#0b0f1c"/><path d="M500,200 L750,110 L1000,200 Z" fill="#0b0f1c"/>')
            ext.append('<rect x="580" y="250" width="86" height="100" fill="#ffc46a"/><rect x="580" y="250" width="86" height="100" fill="none" stroke="#06080e" stroke-width="6"/><line x1="623" y1="250" x2="623" y2="350" stroke="#06080e" stroke-width="5"/>'
                       '<rect x="800" y="250" width="86" height="100" fill="#1a2234"/><rect x="580" y="430" width="86" height="130" fill="#12182a"/>')
            ext.append('<rect x="560" y="560" width="400" height="12" fill="#1b2236"/>')
            for i in range(8):
                ext.append(f'<line x1="{540 + i * 56}" y1="560" x2="{540 + i * 56}" y2="470" stroke="#12182a" stroke-width="8"/>')
            ext.append('<circle cx="740" cy="456" r="9" fill="#ffd98a" opacity=".9" filter="url(#b4)"/>')
            ext.append('<rect x="0" y="560" width="1080" height="80" fill="#0b0e1a"/><ellipse cx="170" cy="610" rx="220" ry="26" fill="#ff9a40" opacity=".28" filter="url(#b16)"/>')
            for i in range(10):
                x = rnd.uniform(0, 1080)
                ext.append(f'<circle cx="{x:.0f}" cy="{rnd.uniform(60, 120):.0f}" r="{rnd.uniform(5, 14):.0f}" fill="#9fb8ff" opacity=".22" filter="url(#b4)"/>')
            self.mood = dict(tint=(.98, .98, 1.05), key=(255, 160, 80), key_dir=-1, key_k=.14)
            self.sweep = (130, 60, 1000, 560)
        b.append('<g filter="url(#b8)">' + "".join(ext) + '</g>')
        # glass sheen + door/pillar frame
        b.append('<rect x="120" y="50" width="920" height="580" fill="url(#glass)"/>')
        b.append('<path d="M0,0 L1080,0 L1080,60 L120,60 L120,640 L0,700 Z" fill="#0c0c10"/>')
        b.append('<path d="M1040,50 L1080,0 L1080,700 L1040,640 Z" fill="#0c0c10"/>')
        b.append('<path d="M0,690 C300,630 780,620 1080,650 L1080,960 L0,960 Z" fill="url(#dash)"/>')
        # seat headrest behind driver
        b.append(f'<rect x="{cx - 210}" y="640" width="420" height="330" rx="120" fill="#16151b"/><rect x="{cx - 86}" y="360" width="172" height="200" rx="60" fill="#14131a"/>')
        body = "".join(b)
        self.static = svg(body, d)
        # dash glow (cool) + passing light
        glow = svg('<ellipse cx="540" cy="940" rx="520" ry="140" fill="#4b7bff" opacity=".28" filter="url(#b30)"/>')
        self.glows.append((glow, .12, .9, 1.0))
        self.rain = (120, 56, 1040, 630, 120)
        self.vig = .55
        self.expo = 1.28

    def build_bedroom(self, v):
        cx = self.cx
        d = (lin("wall", [(0, "#241a40", 1), (1, "#3b2652", 1)]) + lin("bed", [(0, "#6a3a5a", 1), (1, "#43243d", 1)]) + lin("win", [(0, "#0b1030", 1), (1, "#2a2f66", 1)]) +
             lin("curt", [(0, "#8a4a7a", 1), (.5, "#6a3560", 1), (1, "#8a4a7a", 1)], 0, 0, 1, 0) + lin("blank", [(0, "#d9879a", 1), (1, "#a45672", 1)]) +
             rad("moon", [(0, "#fffbe8", 1), (1, "#e8e0c0", 1)]))
        b = ['<rect width="1080" height="960" fill="url(#wall)"/>']
        for x in range(0, 1080, 110):
            b.append(f'<circle cx="{x + 55}" cy="30" r="1.5" fill="#fff" opacity="0"/>')
        # window
        wx = 720
        b.append(f'<rect x="{wx}" y="120" width="290" height="430" rx="10" fill="url(#win)"/>')
        b.append(f'<circle cx="{wx + 200}" cy="210" r="34" fill="url(#moon)"/><circle cx="{wx + 214}" cy="200" r="30" fill="#2a2f66" opacity=".55"/>')
        rnd = random.Random(4)
        for i in range(40):
            b.append(f'<circle cx="{rnd.uniform(wx + 10, wx + 280):.0f}" cy="{rnd.uniform(130, 330):.0f}" r="{rnd.uniform(1, 2.4):.1f}" fill="#fff" opacity="{rnd.uniform(.3, .9):.2f}"/>')
        for i in range(16):
            x = wx + 10 + i * 17
            h = rnd.uniform(40, 140)
            b.append(f'<rect x="{x}" y="{550 - h}" width="15" height="{h}" fill="#0a0d24"/>')
            for k in range(int(h // 24)):
                if rnd.random() < .4:
                    b.append(f'<rect x="{x + 3}" y="{550 - h + k * 24 + 6}" width="8" height="8" fill="#ffd68a" opacity=".8"/>')
        b.append(f'<rect x="{wx}" y="120" width="290" height="430" rx="10" fill="none" stroke="#d8c8e0" stroke-width="12"/><line x1="{wx + 145}" y1="120" x2="{wx + 145}" y2="550" stroke="#d8c8e0" stroke-width="8"/>')
        for x0, wd in ((wx - 66, 80), (wx + 270, 80)):
            b.append(f'<rect x="{x0}" y="90" width="{wd}" height="720" fill="url(#curt)"/>')
        # polaroids with string
        b.append('<path d="M60,120 C200,170 330,170 450,120" stroke="#d8c8e0" stroke-width="2" fill="none" opacity=".7"/>')
        for i, (x, y, rot, col) in enumerate(((100, 140, -6, "#e8b0a0"), (200, 158, 4, "#a0b8e8"), (300, 160, -3, "#e8d8a0"), (390, 142, 6, "#b8e0b0"))):
            b.append(f'<g transform="translate({x},{y}) rotate({rot})"><rect x="0" y="0" width="64" height="78" fill="#f4eee6"/><rect x="6" y="6" width="52" height="52" fill="{col}"/><circle cx="26" cy="28" r="9" fill="#fff" opacity=".35"/></g>')
        # bed: back wall headboard
        b.append('<rect x="-30" y="520" width="1140" height="450" rx="60" fill="#3a2248"/>')
        b.append('<rect x="-30" y="470" width="620" height="120" rx="50" fill="#4b2c5e"/>')
        # blanket & pillows
        b.append('<path d="M-30,760 C200,700 500,720 700,770 L700,960 L-30,960 Z" fill="url(#blank)"/>')
        for k in range(6):
            b.append(f'<path d="M{-10 + k * 120},760 C{40 + k * 120},820 {20 + k * 120},900 {60 + k * 120},960" stroke="#fff" stroke-width="3" opacity=".08" fill="none"/>')
        b.append(f'<rect x="{cx + 120}" y="640" width="190" height="140" rx="44" fill="#f2e6ee"/><rect x="{cx + 120}" y="640" width="190" height="140" rx="44" fill="#000" opacity=".06"/>')
        # plushie bunny
        b.append(f'<g transform="translate({cx - 270},780)"><ellipse cx="0" cy="40" rx="48" ry="52" fill="#f3e9ee"/><circle cx="0" cy="-20" r="36" fill="#f3e9ee"/><ellipse cx="-16" cy="-70" rx="11" ry="34" fill="#f3e9ee"/><ellipse cx="16" cy="-70" rx="11" ry="34" fill="#f3e9ee"/><ellipse cx="-16" cy="-68" rx="5" ry="22" fill="#e8b4c4"/><ellipse cx="16" cy="-68" rx="5" ry="22" fill="#e8b4c4"/><circle cx="-12" cy="-22" r="3.4" fill="#2a1a24"/><circle cx="12" cy="-22" r="3.4" fill="#2a1a24"/></g>')
        # bedside table + lamp + tissues (right)
        b.append('<rect x="930" y="640" width="190" height="330" rx="14" fill="#2a1c34"/><rect x="920" y="630" width="210" height="18" rx="8" fill="#4a3258"/>')
        b.append('<rect x="1000" y="520" width="10" height="112" fill="#d8c8e0"/><path d="M950,520 L1062,520 L1040,440 L972,440 Z" fill="#ffe2b4"/>')
        b.append('<rect x="942" y="590" width="74" height="42" rx="6" fill="#e8f0ff"/><path d="M962,590 C962,566 978,560 984,552 C990,566 1000,572 996,590 Z" fill="#fff"/>')
        body = "".join(b)
        self.static = svg(body, d)
        lamp = svg('<ellipse cx="1006" cy="470" rx="320" ry="340" fill="#ffb878" opacity=".45" filter="url(#b60)"/><ellipse cx="1006" cy="480" rx="90" ry="100" fill="#ffe4b0" opacity=".6" filter="url(#b30)"/>')
        self.glows.append((lamp, .10, 1.3, 0.5))
        moon = svg(f'<ellipse cx="{wx + 160}" cy="360" rx="260" ry="300" fill="#8aa0ff" opacity=".16" filter="url(#b60)"/>')
        self.glows.append((moon, .04, .3, 1.0))
        # fairy lights
        pts = []
        for i in range(16):
            x = i * 72 - 10
            y = 38 + 30 * math.sin(i * 0.9) + 10
            pts.append((x, y))
        path = "M" + " L".join(f"{x:.0f},{y:.0f}" for x, y in pts)
        wire = svg(f'<path d="{path}" stroke="#16101e" stroke-width="3" fill="none"/>')
        self.static.alpha_composite(wire)
        for (x, y) in pts:
            self.twinkles.append((x, y + 12, self.rnd.uniform(14, 22), (255, 214, 150), self.rnd.uniform(0, 6.28), self.rnd.uniform(.8, 1.8)))
        self.rain = (wx + 4, 126, wx + 286, 546, 40)
        self.vig = .6
        self.mood = dict(tint=(.94, .9, 1.0), key=(255, 190, 130), key_dir=1, key_k=.26)


    def build_kitchen(self, v):
        v = v or "dawn"
        d = (lin("wall", [(0, "#d9cdb0", 1), (1, "#b8a888", 1)]) + lin("sky", [(0, "#0a1030", 1), (.6, "#1a2450", 1), (1, "#33407a", 1)] if v == "night" else [(0, "#2a3a66", 1), (.6, "#d98a5a", 1), (1, "#ffcf8a", 1)]) +
             lin("cab", [(0, "#6a4a36", 1), (1, "#4a3022", 1)]) + lin("cnt", [(0, "#8a7a6a", 1), (1, "#5c5046", 1)]) + lin("fr", [(0, "#e8e4de", 1), (1, "#bdb8b0", 1)]))
        b = ['<rect width="1080" height="960" fill="url(#wall)"/>']
        for y in range(0, 640, 70):
            for x in range(-40 if (y // 70) % 2 else 0, 1080, 80):
                b.append(f'<rect x="{x}" y="{y}" width="76" height="66" rx="4" fill="#fff" opacity=".10"/>')
        wx = 70
        b.append(f'<rect x="{wx}" y="100" width="300" height="360" rx="8" fill="url(#sky)"/>')
        b.append(f'<circle cx="{wx + 210}" cy="420" r="60" fill="#fff2c0" opacity=".9" filter="url(#b16)"/>')
        for i in range(10):
            xx = wx + 8 + i * 30
            hh = random.Random(i).uniform(50, 130)
            b.append(f'<rect x="{xx}" y="{460 - hh}" width="26" height="{hh}" fill="#1a2240" opacity=".85"/>')
        b.append(f'<rect x="{wx}" y="100" width="300" height="360" rx="8" fill="none" stroke="#f0ece4" stroke-width="14"/><line x1="{wx + 150}" y1="100" x2="{wx + 150}" y2="460" stroke="#f0ece4" stroke-width="9"/><line x1="{wx}" y1="280" x2="{wx + 300}" y2="280" stroke="#f0ece4" stroke-width="9"/>')
        # shelf with jars
        b.append('<rect x="440" y="170" width="300" height="14" rx="5" fill="#6a4a36"/>')
        for i, col in enumerate(("#c9712f", "#8a5a30", "#c2a14a", "#7a8a4a", "#a8432c")):
            b.append(f'<rect x="{456 + i * 56}" y="{110}" width="44" height="60" rx="8" fill="{col}"/><rect x="{462 + i * 56}" y="{98}" width="32" height="14" rx="4" fill="#3a2a22"/>')
        # hanging utensils
        b.append('<rect x="780" y="120" width="230" height="8" rx="4" fill="#5a4636"/>')
        for i, x in enumerate((800, 850, 905, 960)):
            b.append(f'<line x1="{x}" y1="128" x2="{x}" y2="{200 + i % 2 * 20}" stroke="#aaa" stroke-width="5"/><ellipse cx="{x}" cy="{232 + i % 2 * 20}" rx="{22 - i * 2}" ry="{30 + i * 2}" fill="#b8bcc4"/>')
        # calendar
        b.append('<rect x="780" y="300" width="130" height="170" fill="#f4eee0"/><rect x="780" y="300" width="130" height="34" fill="#b5432f"/>' + "".join(f'<rect x="{792 + (k % 5) * 22}" y="{346 + (k // 5) * 24}" width="14" height="14" fill="#8a8070" opacity=".5"/>' for k in range(20)))
        # counter, cabinets, stove
        b.append('<rect x="0" y="640" width="1080" height="320" fill="url(#cab)"/><rect x="0" y="624" width="1080" height="26" fill="url(#cnt)"/>')
        for x in range(0, 1080, 216):
            b.append(f'<rect x="{x + 14}" y="670" width="188" height="270" rx="8" fill="#000" opacity=".14"/><circle cx="{x + 180}" cy="700" r="7" fill="#d8c7a0"/>')
        px = 810
        b.append(f'<rect x="{px - 110}" y="596" width="220" height="30" rx="6" fill="#222"/><ellipse cx="{px}" cy="590" rx="92" ry="14" fill="#8a8e98"/><path d="M{px - 92},590 L{px - 80},520 C{px - 40},508 {px + 40},508 {px + 80},520 L{px + 92},590 Z" fill="#a8acb8"/><ellipse cx="{px}" cy="520" rx="80" ry="12" fill="#b8793c"/><path d="M{px + 92},560 C{px + 150},550 {px + 150},590 {px + 94},584" stroke="#2a2a30" stroke-width="12" fill="none"/>')
        b.append(f'<path d="M{px - 50},560 C{px - 30},610 {px + 30},610 {px + 50},560" fill="#ff8a3c" opacity=".0"/>')
        self.static = svg("".join(b), d)
        win = svg(f'<ellipse cx="{wx + 160}" cy="420" rx="320" ry="260" fill="{"#7a8cff" if v == "night" else "#ffb878"}" opacity="{.16 if v == "night" else .42}" filter="url(#b60)"/>')
        self.glows.append((win, .06, .25, 0.7))
        lamp = svg('<ellipse cx="540" cy="80" rx="520" ry="230" fill="#ffd9a0" opacity=".38" filter="url(#b60)"/>')
        self.glows.append((lamp, .08, 1.4, 0.2))
        self.steam = (px, 505)
        self.vig = .5
        self.mood = dict(tint=(1.0, .95, .88), key=(255, 200, 140), key_dir=-1, key_k=.28)

    def build_desk(self, v):
        v = v or "hostel"
        cx = self.cx
        d = (lin("wall", [(0, "#1b2236", 1), (1, "#2a2a42", 1)]) + lin("win", [(0, "#080c22", 1), (1, "#2a2f5e", 1)]) + lin("desk", [(0, "#6a4a36", 1), (1, "#3e2a20", 1)]))
        b = ['<rect width="1080" height="960" fill="url(#wall)"/>']
        wx = 90 if cx > 500 else 700
        b.append(f'<rect x="{wx}" y="110" width="290" height="400" rx="8" fill="url(#win)"/>')
        rnd = random.Random(11)
        for i in range(15):
            xx = wx + 8 + i * 18
            hh = rnd.uniform(40, 160)
            b.append(f'<rect x="{xx}" y="{510 - hh}" width="16" height="{hh}" fill="#0a0d22"/>')
            for k in range(int(hh // 22)):
                if rnd.random() < .45:
                    b.append(f'<rect x="{xx + 3}" y="{510 - hh + k * 22 + 6}" width="8" height="8" fill="#ffd68a" opacity=".8"/>')
        for i in range(30):
            b.append(f'<circle cx="{rnd.uniform(wx + 10, wx + 280):.0f}" cy="{rnd.uniform(120, 300):.0f}" r="{rnd.uniform(1, 2.2):.1f}" fill="#fff" opacity="{rnd.uniform(.3, .8):.2f}"/>')
        b.append(f'<rect x="{wx}" y="110" width="290" height="400" rx="8" fill="none" stroke="#cfcfe0" stroke-width="12"/><line x1="{wx + 145}" y1="110" x2="{wx + 145}" y2="510" stroke="#cfcfe0" stroke-width="8"/>')
        # shelf with books
        sx = 700 if cx > 500 else 90
        b.append(f'<rect x="{sx}" y="300" width="300" height="12" rx="4" fill="#5a4030"/>')
        xx = sx + 10
        while xx < sx + 280:
            w_, h_ = rnd.randint(18, 32), rnd.randint(60, 100)
            b.append(f'<rect x="{xx}" y="{300 - h_}" width="{w_}" height="{h_}" fill="{rnd.choice(["#b04a4a", "#4a6ab0", "#c9a24a", "#4a9a78", "#8a5ab0"])}"/>')
            xx += w_ + 3
        b.append(f'<rect x="{sx}" y="150" width="300" height="12" rx="4" fill="#5a4030"/>')
        for i in range(4):
            b.append(f'<circle cx="{sx + 40 + i * 70}" cy="130" r="18" fill="{["#c9a24a", "#7a8a9a", "#a86a4a", "#6a9a8a"][i]}"/>')
        # desk
        b.append('<rect x="0" y="720" width="1080" height="240" fill="url(#desk)"/><rect x="0" y="706" width="1080" height="20" rx="6" fill="#7a5a44"/>')
        # laptop (back faces viewer) and lamp
        lx = cx - 180 if cx < 500 else cx - 120
        b.append(f'<rect x="{cx - 210}" y="650" width="150" height="70" rx="6" fill="#c4c8d0"/><path d="M{cx - 210},650 L{cx - 60},650 L{cx - 60},720 L{cx - 210},720 Z" fill="#9aa0aa" opacity=".4"/>')
        b.append(f'<circle cx="{cx - 135}" cy="686" r="9" fill="#e8ecf4" opacity=".7"/>')
        lampx = cx + 230 if cx < 500 else cx - 330
        b.append(f'<rect x="{lampx}" y="580" width="10" height="130" fill="#222"/><path d="M{lampx - 50},590 L{lampx + 60},590 L{lampx + 40},540 L{lampx - 30},540 Z" fill="#f4d890"/>')
        b.append(f'<rect x="{cx + 110}" y="670" width="60" height="50" rx="8" fill="#e8e0d0"/><ellipse cx="{cx + 140}" cy="670" rx="30" ry="9" fill="#a8743c"/>')
        if v == "packing":
            b.append(f'<rect x="{sx - 30}" y="740" width="360" height="190" rx="18" fill="#3a4a6a"/><rect x="{sx - 10}" y="760" width="320" height="150" rx="12" fill="#e6dccb"/>')
            for k, col in enumerate(("#b04a4a", "#4a6ab0", "#c9a24a", "#e8e0d0")):
                b.append(f'<rect x="{sx + 20 + k * 66}" y="{770 + k % 2 * 14}" width="58" height="{110 - k % 2 * 14}" rx="8" fill="{col}" opacity=".9"/>')
            b.append(f'<rect x="{sx - 40}" y="690" width="100" height="70" fill="#a8844a"/><rect x="{sx - 40}" y="720" width="100" height="10" fill="#c8a468"/>')
        self.static = svg("".join(b), d)
        lm = svg(f'<ellipse cx="{lampx + 5}" cy="560" rx="300" ry="280" fill="#ffc47a" opacity=".5" filter="url(#b60)"/><ellipse cx="{lampx + 5}" cy="560" rx="90" ry="90" fill="#ffe4b0" opacity=".6" filter="url(#b30)"/>')
        self.glows.append((lm, .06, 1.1, .3))
        lap = svg(f'<ellipse cx="{cx - 135}" cy="700" rx="220" ry="150" fill="#7ab0ff" opacity=".22" filter="url(#b30)"/>')
        self.glows.append((lap, .12, 1.6, 1.0))
        self.rain = (wx + 4, 116, wx + 286, 506, 30)
        self.vig = .6
        self.mood = dict(tint=(.94, .94, 1.04), key=(255, 190, 130), key_dir=1 if cx < 500 else -1, key_k=.22)

    def build_cafe(self, v):
        v = v or "closing"
        d = (lin("wall", [(0, "#5a3028", 1), (1, "#32201e", 1)]) + lin("win", [(0, "#0c1230", 1), (1, "#2a2a52", 1)]) + lin("cnt", [(0, "#7a5a44", 1), (1, "#3e2c22", 1)]))
        b = ['<rect width="1080" height="960" fill="url(#wall)"/>']
        for x in range(0, 1080, 120):
            b.append(f'<rect x="{x}" y="0" width="60" height="640" fill="#000" opacity=".10"/>')
        b.append('<rect x="690" y="130" width="320" height="420" rx="140" fill="url(#win)"/>')
        rnd = random.Random(13)
        for i in range(22):
            x, y, r = rnd.uniform(710, 990), rnd.uniform(300, 520), rnd.uniform(6, 16)
            b.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="{rnd.choice(["#ff6a5a", "#ffc46a", "#9fc6ff", "#9affc0"])}" opacity="{rnd.uniform(.3, .7):.2f}" filter="url(#b8)"/>')
        b.append('<rect x="690" y="130" width="320" height="420" rx="140" fill="none" stroke="#a4784a" stroke-width="14"/>')
        # shelf cups
        b.append('<rect x="60" y="250" width="440" height="14" rx="5" fill="#8a6244"/><rect x="60" y="400" width="440" height="14" rx="5" fill="#8a6244"/>')
        for i in range(9):
            col = ["#e8dccb", "#d8a46a", "#9ab8a8", "#c8786a"][i % 4]
            b.append(f'<path d="M{82 + i * 46},{250} l4,-34 h28 l4,34 Z" fill="{col}"/>')
            b.append(f'<path d="M{82 + i * 46},{400} l4,-34 h28 l4,34 Z" fill="{["#c8786a", "#e8dccb", "#9ab8a8", "#d8a46a"][i % 4]}"/>')
        # chalkboard
        b.append('<rect x="120" y="90" width="300" height="120" rx="8" fill="#26302c" stroke="#8a6244" stroke-width="8"/>' +
                 "".join(f'<line x1="146" y1="{120 + k * 24}" x2="{300 + (k % 2) * 60}" y2="{120 + k * 24}" stroke="#e8e8e0" stroke-width="3" opacity=".55"/>' for k in range(3)))
        # pendant lamps
        for x, ln in ((600, 150), (330, 70), (520, 330)):
            b.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{ln}" stroke="#1a1210" stroke-width="3"/><path d="M{x - 40},{ln + 46} L{x + 40},{ln + 46} L{x + 18},{ln} L{x - 18},{ln} Z" fill="#2a1c18"/><ellipse cx="{x}" cy="{ln + 48}" rx="20" ry="8" fill="#ffe4a8"/>')
        # counter w/ espresso machine
        b.append('<rect x="0" y="640" width="1080" height="320" fill="url(#cnt)"/><rect x="0" y="626" width="1080" height="24" fill="#a07a58"/>')
        b.append('<rect x="760" y="530" width="230" height="96" rx="10" fill="#b8bcc4"/><rect x="780" y="500" width="190" height="40" rx="8" fill="#8a8e98"/><rect x="830" y="590" width="20" height="36" fill="#222"/><circle cx="930" cy="565" r="16" fill="#e8d28a"/>')
        # stacked chairs
        for i in range(3):
            b.append(f'<g transform="translate({600 + i * 6},{600 - i * 10})" opacity=".0"></g>')
        F = self.cx > 500
        inner = "".join(b)
        txt = '<text x="%d" y="330" font-family="Inter" font-size="46" font-weight="700" fill="#ff7a6a" text-anchor="middle" opacity=".85" >CLOSED</text>' % (230 if F else 850)
        if F:
            inner = '<g transform="translate(1080,0) scale(-1,1)">' + inner + '</g>'
        self.static = svg(inner + txt, d)
        for x, ln in ((600, 150), (330, 70), (520, 330)):
            xx = 1080 - x if F else x
            g = svg(f'<ellipse cx="{xx}" cy="{ln + 90}" rx="230" ry="190" fill="#ffc47a" opacity=".42" filter="url(#b60)"/>')
            self.glows.append((g, .05, 1.0 + x / 900, x / 100))
        self.rain = (80, 140, 380, 540, 50) if F else (700, 140, 1000, 540, 50)
        self.steam = (220, 498) if F else (860, 498)
        self.vig = .55
        self.mood = dict(tint=(1.0, .92, .86), key=(255, 190, 120), key_dir=-1, key_k=.28)

    # ------------------------------------------------------------ frame
    def render(self, t):
        im = self.static.copy()
        # animated glows
        for (layer, amt, spd, ph) in self.glows:
            f = 1 - amt + amt * (0.5 + 0.5 * math.sin(t * spd * 6 + ph) * math.sin(t * spd * 2.3 + ph * 1.7))
            a = layer.getchannel("A").point(lambda v, f=f: int(v * f))
            l2 = layer.copy()
            l2.putalpha(a)
            im.alpha_composite(l2)
        # fairy light twinkle
        if self.twinkles:
            gd = glowdot()
            for (x, y, r, col, ph, spd) in self.twinkles:
                a = 0.55 + 0.45 * math.sin(t * spd * 2.2 + ph)
                sp = tint(gd.resize((int(r * 2), int(r * 2))), col, a)
                im.alpha_composite(sp, (int(x - r), int(y - r)))
        # headlight sweep behind glass
        if self.sweep and self.kind == "car":
            x0, y0, x1, y1 = self.sweep
            ph = (t % 11.0) / 11.0
            if ph < .45:
                u = ph / .45
                xc = x0 - 200 + u * (x1 - x0 + 400)
                lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
                d = ImageDraw.Draw(lay)
                d.ellipse([xc - 150, y0 + 200, xc + 150, y1 - 30], fill=(255, 245, 220, int(70 * math.sin(u * math.pi))))
                lay = lay.filter(ImageFilter.GaussianBlur(40))
                im.alpha_composite(lay)
        # rain on glass
        if self.rain_streaks:
            x0, y0, x1, y1, _ = self.rain
            lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(lay)
            for (x, ph, spd, ln, op) in self.rain_streaks:
                y = y0 + ((ph * (y1 - y0) + t * spd) % (y1 - y0 + ln)) - ln
                ya, yb = max(y, y0), min(y + ln, y1)
                if yb > ya:
                    d.line([x + (y - y0) * .02, ya, x + (yb - y0) * .02 - 1.2, yb], fill=(215, 230, 255, int(70 * op)), width=2)
            for (x, y, r) in self.static_drops:
                d.ellipse([x - r, y - r, x + r, y + r + 2], fill=(230, 240, 255, 38), outline=(255, 255, 255, 80))
            im.alpha_composite(lay)
        # steam
        if self.steam:
            sx, sy = self.steam
            lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(lay)
            for i in range(7):
                u = ((t * .28 + i / 7) % 1.0)
                x = sx + math.sin(u * 6 + i) * (10 + 16 * u) + (i - 3) * 5
                y = sy - u * 130
                r = 7 + u * 20
                a = int(70 * math.sin(u * math.pi))
                d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 245, 230, a))
            im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(7)))
        # dust motes
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for (x, y, sp, ph, am) in self.motes:
            xx = x + math.sin(t * .4 + ph) * am
            yy = (y - t * sp * 6) % HH
            a = int(90 * (0.5 + .5 * math.sin(t * .9 + ph)))
            d.ellipse([xx - 1.6, yy - 1.6, xx + 1.6, yy + 1.6], fill=(255, 240, 210, a))
        im.alpha_composite(lay)
        return im
