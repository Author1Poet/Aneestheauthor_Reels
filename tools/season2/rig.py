"""Layered puppet rig: every part is authored as SVG (beziers, gradients), rasterised once with rsvg-convert,
then animated by compositing transformed sprites. All sprite coordinates are in a 560x960 character canvas
(head centre = HX,HY) and sprites are stored at 2x resolution."""
import io, math, os, random, subprocess, pickle, hashlib
from PIL import Image, ImageChops, ImageDraw, ImageFilter

S = 2
HX, HY = 280, 488
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spritecache")
os.makedirs(CACHE, exist_ok=True)


def hx(c):
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, v))) for v in c)


def mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def lighten(c, t): return mix(c, (255, 255, 255), t)
def darken(c, t): return mix(c, (0, 0, 0), t)


def rsvg(svg, w, h):
    p = subprocess.run(["rsvg-convert", "-w", str(int(w)), "-h", str(int(h)), "-f", "png"], input=svg.encode(), capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode()[:400])
    return Image.open(io.BytesIO(p.stdout)).convert("RGBA")


def sprite(body, x, y, w, h, defs=""):
    """render svg body in canvas-coordinate box (x,y,w,h) at 2x. returns (img, x, y)"""
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}" width="{w * S}" height="{h * S}"><defs>{defs}</defs>{body}</svg>'
    return rsvg(svg, w * S, h * S), x, y


def hs(body):
    return f'<g transform="translate({HX},{HY})">{body}</g>'


def H(lx, ly):  # head-local -> canvas
    return HX + lx, HY + ly


def lin(id_, stops, x1=0, y1=0, x2=0, y2=1):
    s = "".join(f'<stop offset="{o}" stop-color="{col}" stop-opacity="{a}"/>' for o, col, a in stops)
    return f'<linearGradient id="{id_}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">{s}</linearGradient>'


def rad(id_, stops, cx=.5, cy=.5, r=.5, fx=None, fy=None):
    s = "".join(f'<stop offset="{o}" stop-color="{col}" stop-opacity="{a}"/>' for o, col, a in stops)
    return f'<radialGradient id="{id_}" cx="{cx}" cy="{cy}" r="{r}" fx="{fx if fx is not None else cx}" fy="{fy if fy is not None else cy}">{s}</radialGradient>'


# ------------------------------------------------------------------ cast
CAST = {
    "ammi": dict(name="Ammi", skin=(214, 160, 120), hair=(58, 44, 42), gray=(196, 190, 186), outfit=(120, 38, 58), trim=(222, 178, 80),
                 dup=(238, 228, 208), fw=102, jaw=72, cw=32, chin=150, iris=(70, 44, 28), ew=28, eh=16, lash=0, brow=(70, 56, 52), bt=7.5, arch=4,
                 lip=(176, 86, 84), glasses=("gold", 0), age=1, earring=(230, 190, 90), phone=(232, 224, 214), nose=1.1, tired=0.0,
                 style="ammi", mouth_w=48, sleeve=(120, 38, 58), blink=1.35, fidget=0.5),
    "hamza": dict(name="Hamza", skin=(190, 140, 104), hair=(28, 22, 22), outfit=(62, 76, 72), trim=(40, 48, 46), dup=None,
                  fw=96, jaw=58, cw=20, chin=154, iris=(52, 34, 24), ew=28, eh=15.5, lash=0, brow=(30, 22, 22), bt=9.5, arch=2,
                  lip=(150, 90, 80), glasses=None, stubble=1, circles=1, earring=None, phone=(32, 32, 36), nose=1.0, tired=0.22,
                  style="hamza", mouth_w=46, sleeve=(62, 76, 72), belt=True, blink=1.0, fidget=1.0),
    "sara": dict(name="Sara", skin=(240, 198, 164), hair=(122, 68, 42), outfit=(210, 158, 54), trim=(244, 238, 228), dup=None,
                 fw=95, jaw=58, cw=22, chin=150, iris=(120, 84, 44), ew=29, eh=17.5, lash=1, brow=(98, 56, 36), bt=6, arch=7,
                 lip=(206, 112, 112), glasses=None, freckles=1, earring=(236, 200, 110), phone=(212, 86, 96), nose=0.9, tired=0.05,
                 style="sara", mouth_w=44, sleeve=(210, 158, 54), blink=1.0, fidget=1.3),
    "noor": dict(name="Noor", skin=(232, 184, 146), hair=(40, 28, 24), outfit=(88, 120, 164), trim=(236, 238, 242), dup=None, hijab=(34, 128, 130),
                 fw=104, jaw=74, cw=36, chin=148, iris=(56, 36, 26), ew=29, eh=17, lash=1, brow=(46, 30, 26), bt=9.5, arch=5,
                 lip=(190, 96, 98), glasses=None, stud=1, earring=None, phone=(240, 190, 76), nose=1.0, tired=0.0,
                 style="noor", mouth_w=48, sleeve=(88, 120, 164), belt=True, blink=1.0, fidget=1.1),
}

# ------------------------------------------------------------------ face
def face_d(c, grow=0):
    fw, j, cw, chy = c["fw"] + grow, c["jaw"] + grow, c["cw"], c["chin"] + grow
    return (f"M0,{-160 - grow} C62,{-160 - grow} {fw},-122 {fw},-30 C{fw},30 {j + 28},84 {j},110 C{j - 22},140 {cw},{chy} 0,{chy} "
            f"C-{cw},{chy} -{j - 22},140 -{j},110 C-{j + 28},84 -{fw},30 -{fw},-30 C-{fw},-122 -62,{-160 - grow} 0,{-160 - grow} Z")


def sprite_face(c):
    sk = c["skin"]
    fw = c["fw"]
    defs = (lin("fb", [(0, hx(lighten(sk, .10)), 1), (.45, hx(sk), 1), (1, hx(darken(sk, .13)), 1)]) +
            lin("side", [(0, hx(darken(sk, .45)), .38), (.22, hx(darken(sk, .45)), 0), (.78, hx(darken(sk, .45)), 0), (1, hx(darken(sk, .45)), .38)], 0, 0, 1, 0) +
            rad("cheek", [(0, "#ff7a7a", .42), (1, "#ff7a7a", 0)]) +
            rad("hl", [(0, "#ffffff", .30), (1, "#ffffff", 0)]) + rad("chs", [(0, "#000000", .16), (1, "#000000", 0)]) +
            lin("hairsh", [(0, hx(darken(c["hair"], .2)), .45), (1, hx(darken(c["hair"], .2)), 0)]) +
            f'<clipPath id="fc"><path d="{face_d(c)}"/></clipPath>')
    b = []
    # ears
    for sg in (-1, 1):
        b.append(f'<ellipse cx="{sg * (fw - 2)}" cy="12" rx="17" ry="27" fill="{hx(darken(sk, .08))}"/>')
        b.append(f'<ellipse cx="{sg * (fw + 1)}" cy="14" rx="7" ry="14" fill="{hx(darken(sk, .25))}" opacity=".45"/>')
    b.append(f'<path d="{face_d(c)}" fill="url(#fb)"/>')
    b.append('<g clip-path="url(#fc)">')
    b.append('<rect x="-130" y="-170" width="260" height="90" fill="url(#hairsh)"/>')
    b.append('<rect x="-130" y="-170" width="260" height="340" fill="url(#side)"/>')
    for sg in (-1, 1):
        b.append(f'<ellipse cx="{sg * 58}" cy="48" rx="34" ry="26" fill="url(#cheek)"/>')
    b.append('<ellipse cx="0" cy="-70" rx="50" ry="40" fill="url(#hl)"/>')
    b.append('<ellipse cx="0" cy="136" rx="70" ry="34" fill="url(#chs)"/>')
    # under eye
    for sg in (-1, 1):
        dark = 0.30 if c.get("circles") else 0.10 + c["tired"] * 0.5
        b.append(f'<ellipse cx="{sg * 44}" cy="20" rx="30" ry="9" fill="{hx(darken(sk, .45))}" opacity="{dark}"/>')
    if c.get("age"):
        for sg in (-1, 1):
            b.append(f'<path d="M{sg * 22},50 C{sg * 34},66 {sg * 38},80 {sg * 34},92" stroke="{hx(darken(sk, .4))}" stroke-width="2.4" fill="none" opacity=".35" stroke-linecap="round"/>')
            b.append(f'<path d="M{sg * 74},-4 l{sg * 12},-5 M{sg * 75},4 l{sg * 13},1 M{sg * 73},12 l{sg * 11},7" stroke="{hx(darken(sk, .4))}" stroke-width="1.8" fill="none" opacity=".30" stroke-linecap="round"/>')
        b.append(f'<path d="M-30,-104 C-10,-110 10,-110 30,-104 M-26,-92 C-8,-97 8,-97 26,-92" stroke="{hx(darken(sk, .4))}" stroke-width="2" fill="none" opacity=".18" stroke-linecap="round"/>')
    if c.get("freckles"):
        rnd = random.Random(5)
        for _ in range(34):
            sg = rnd.choice((-1, 1))
            x, y = sg * rnd.uniform(14, 74), rnd.uniform(24, 56)
            b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rnd.uniform(1.0, 1.9):.1f}" fill="{hx(darken(sk, .45))}" opacity="{rnd.uniform(.25, .5):.2f}"/>')
    if c.get("stubble"):
        rnd = random.Random(9)
        b.append(f'<path d="M-96,10 C-92,70 -60,118 0,146 C60,118 92,70 96,10 C80,60 50,92 0,100 C-50,92 -80,60 -96,10 Z" fill="{hx(c["hair"])}" opacity=".32"/>')
        for _ in range(520):
            x, y = rnd.uniform(-88, 88), rnd.uniform(40, 150)
            d_ = (x / 94) ** 2 + ((y - 40) / 114) ** 2
            if d_ < 1.0 and (y > 74 or abs(x) > 52) and not (abs(x) < 26 and 60 < y < 74):
                b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.1" fill="{hx(c["hair"])}" opacity="{rnd.uniform(.35, .85):.2f}"/>')
    b.append('</g>')
    # nose
    n = c["nose"]
    sh = hx(darken(sk, .38))
    b.append(f'<path d="M{5 * n},8 C{10 * n},26 {13 * n},38 {5 * n},46" stroke="{sh}" stroke-width="3.6" fill="none" opacity=".34" stroke-linecap="round"/>')
    b.append(f'<path d="M{-11 * n},44 C{-6 * n},52 {6 * n},52 {11 * n},44" stroke="{sh}" stroke-width="3.2" fill="none" opacity=".5" stroke-linecap="round"/>')
    b.append(f'<ellipse cx="{-6 * n}" cy="47" rx="3" ry="2.2" fill="{sh}" opacity=".5"/><ellipse cx="{6 * n}" cy="47" rx="3" ry="2.2" fill="{sh}" opacity=".5"/>')
    b.append(f'<ellipse cx="{-1 * n}" cy="38" rx="5" ry="6" fill="#fff" opacity=".22"/>')
    if c.get("stud"):
        b.append(f'<circle cx="{12 * n}" cy="42" r="2.6" fill="#f2c94c"/><circle cx="{11.2 * n}" cy="41.2" r="1" fill="#fff" opacity=".8"/>')
    if c.get("earring"):
        for sg in (-1, 1):
            b.append(f'<circle cx="{sg * (fw + 3)}" cy="44" r="5.5" fill="{hx(c["earring"])}"/><circle cx="{sg * (fw + 2)}" cy="43" r="1.8" fill="#fff" opacity=".7"/>')
    return sprite(hs("".join(b)), HX - 140, HY - 190, 280, 370, defs)


def sprite_neck(c):
    sk = c["skin"]
    defs = lin("n", [(0, hx(darken(sk, .45)), 1), (.35, hx(darken(sk, .22)), 1), (1, hx(darken(sk, .12)), 1)]) + lin("ns", [(0, "#000", .35), (1, "#000", 0)])
    body = (f'<path d="M-40,0 L-40,70 C-40,100 40,100 40,70 L40,0 Z" fill="url(#n)"/>')
    # drawn in canvas coords below head: neck from y=590 to 730
    return sprite(f'<g transform="translate(280,0)"><rect x="-38" y="590" width="76" height="150" rx="30" fill="url(#n)"/>'
                  f'<ellipse cx="0" cy="640" rx="40" ry="22" fill="#000" opacity=".34"/></g>', 200, 560, 160, 200, defs)


# ------------------------------------------------------------------ eyes / brows / mouth
EYE_LEVELS = 9


def eye_geom(c):
    return c["ew"], c["eh"]


def sprite_sclera(c):
    ew, eh = eye_geom(c)
    defs = lin("sc", [(0, "#f6f3f0", 1), (1, "#d9d3cf", 1)]) + lin("sh", [(0, "#000", .30), (.5, "#000", 0)]) + f'<clipPath id="scp"><path d="M{-ew},0 C{-ew * .55},{-eh * 1.28} {ew * .55},{-eh * 1.28} {ew},0 C{ew * .55},{eh * 1.15} {-ew * .55},{eh * 1.15} {-ew},0 Z"/></clipPath>'
    body = (f'<path d="M{-ew},0 C{-ew * .55},{-eh * 1.28} {ew * .55},{-eh * 1.28} {ew},0 C{ew * .55},{eh * 1.15} {-ew * .55},{eh * 1.15} {-ew},0 Z" fill="url(#sc)"/>'
            f'<g clip-path="url(#scp)"><rect x="{-ew}" y="{-eh * 2}" width="{2 * ew}" height="{eh * 2.4}" fill="url(#sh)"/></g>')
    img, x, y = sprite(body, -40, -30, 80, 60, defs)
    return img, -40, -30


def sprite_iris(c):
    ir = c["eh"] * 0.88
    col = c["iris"]
    defs = rad("ir", [(0, hx(lighten(col, .32)), 1), (.62, hx(col), 1), (1, hx(darken(col, .45)), 1)])
    body = (f'<circle r="{ir}" fill="url(#ir)"/><circle r="{ir}" fill="none" stroke="{hx(darken(col, .6))}" stroke-width="1.6" opacity=".7"/>'
            f'<circle r="{ir * .46}" fill="#0c0808"/><circle cx="{-ir * .34}" cy="{-ir * .38}" r="{ir * .30}" fill="#fff" opacity=".95"/>'
            f'<circle cx="{ir * .34}" cy="{ir * .38}" r="{ir * .13}" fill="#fff" opacity=".75"/>')
    return sprite(body, -20, -20, 40, 40, defs)


def sprite_lid(c, o):
    """upper lid overlay for openness o (1 open .. 0 closed)"""
    ew, eh = eye_geom(c)
    sk = c["skin"]
    o_eff = o * (1 - c["tired"] * 0.55)
    edge_open, edge_closed = -eh * 1.56, eh * 0.55
    edge = edge_closed + (edge_open - edge_closed) * o_eff
    top = edge - eh * 2.2
    defs = (lin("ld", [(0, hx(sk), 0), (.38, hx(sk), 1), (1, hx(darken(sk, .03)), 1)]) +
            lin("lmk", [(0, "#000", 0), (.55, "#fff", 1), (1, "#fff", 1)]) +
            rad("lmr", [(0, "#fff", 1), (.62, "#fff", 1), (1, "#000", 1)]) +
            f'<mask id="lm" maskUnits="userSpaceOnUse" x="-50" y="-40" width="100" height="80"><rect x="{-ew - 12}" y="{top - 6}" width="{2 * ew + 24}" height="{abs(top) + 22}" fill="url(#lmr)"/></mask>')
    ex = ew + 7
    lid = f'M{-ex},0 C{-ew * .55},{edge} {ew * .55},{edge} {ex},0 L{ex},{top} L{-ex},{top} Z'
    lash_w = 4.6 if c["lash"] else 3.4
    lc = hx(darken(c["hair"], .2)) if not c["lash"] else "#1c1212"
    line = f'M{-ew},0 C{-ew * .55},{edge * 0.76} {ew * .55},{edge * 0.76} {ew},0'
    b = [f'<g mask="url(#lm)"><path d="{lid}" fill="url(#ld)"/></g>',
         f'<path d="{line}" fill="none" stroke="{lc}" stroke-width="{lash_w}" stroke-linecap="round"/>']
    if c["lash"]:
        b.append(f'<path d="M{ew - 2},{-0.2} C{ew + 4},{-3} {ew + 8},{-6} {ew + 10},{-9}" stroke="{lc}" stroke-width="3.2" fill="none" stroke-linecap="round"/>')
    if o_eff > 0.45:
        cy = edge * 0.76 - eh * 0.95
        b.append(f'<path d="M{-ew * .85},{-1} C{-ew * .5},{cy} {ew * .5},{cy} {ew * .85},{-1}" fill="none" stroke="{hx(darken(sk, .42))}" stroke-width="2" opacity=".5"/>')
    # lower lash line
    b.append(f'<path d="M{-ew * .9},{1.5} C{-ew * .5},{eh * 1.05} {ew * .5},{eh * 1.05} {ew * .9},{1.5}" fill="none" stroke="{hx(darken(sk, .4))}" stroke-width="1.6" opacity=".45"/>')
    return sprite("".join(b), -40, -34, 80, 60, defs)


def sprite_brow(c):
    bw, t, ar = 30, c["bt"], c["arch"]
    col = hx(c["brow"])
    defs = lin("bg", [(0, col, .95), (.7, col, 1), (1, col, .55)], 0, 0, 1, 0)
    body = (f'<path d="M{-bw},{3 + ar * .2} C{-bw * .4},{-ar * 2.1 - 3} {bw * .3},{-ar * 2.1 - 2} {bw},{4 + ar * .4}" stroke="url(#bg)" stroke-width="{t}" fill="none" stroke-linecap="round"/>'
            f'<path d="M{-bw + 3},{3 + ar * .2} C{-bw * .4},{-ar * 2.1 - 3} {bw * .3},{-ar * 2.1 - 2} {bw},{4 + ar * .4}" stroke="{col}" stroke-width="{t * .45}" fill="none" stroke-linecap="round" opacity=".7" transform="translate(0,2)"/>')
    return sprite(body, -44, -34, 88, 56, defs)


def sprite_mouth(c, kind):
    w = c["mouth_w"]
    lip = c["lip"]
    ld = hx(darken(lip, .22))
    lc = hx(lip)
    line = hx(darken(lip, .5))
    defs = lin("lp", [(0, hx(lighten(lip, .14)), 1), (1, hx(darken(lip, .06)), 1)])
    b = []
    up = lambda dy=0: f'M{-w * .5},{dy} C{-w * .28},{dy - 9} {-w * .08},{dy - 8} 0,{dy - 4.5} C{w * .08},{dy - 8} {w * .28},{dy - 9} {w * .5},{dy}'
    if kind == "neutral":
        b.append(f'<path d="M{-w * .46},1 C{-w * .2},{17} {w * .2},{17} {w * .46},1 C{w * .2},5 {-w * .2},5 {-w * .46},1 Z" fill="url(#lp)"/>')
        b.append(f'<path d="{up(1)} C{w * .2},4.5 {-w * .2},4.5 {-w * .5},1 Z" fill="{ld}"/>')
        b.append(f'<path d="M{-w * .5},1 C{-w * .2},4.2 {w * .2},4.2 {w * .5},1" stroke="{line}" stroke-width="2.2" fill="none" stroke-linecap="round"/>')
    elif kind == "soft":
        b.append(f'<path d="M{-w * .46},-2 C{-w * .2},16 {w * .2},16 {w * .46},-2 C{w * .2},5 {-w * .2},5 {-w * .46},-2 Z" fill="url(#lp)"/>')
        b.append(f'<path d="M{-w * .5},-3 C{-w * .3},-12 {-w * .08},-9 0,-6 C{w * .08},-9 {w * .3},-12 {w * .5},-3 C{w * .2},5 {-w * .2},5 {-w * .5},-3 Z" fill="{ld}"/>')
        b.append(f'<path d="M{-w * .52},-4 C{-w * .22},6.5 {w * .22},6.5 {w * .52},-4" stroke="{line}" stroke-width="2.2" fill="none" stroke-linecap="round"/>')
    elif kind == "smile":
        b.append(f'<path d="M{-w * .56},-6 C{-w * .3},22 {w * .3},22 {w * .56},-6 C{w * .3},2 {-w * .3},2 {-w * .56},-6 Z" fill="#5c222c"/>')
        b.append(f'<path d="M{-w * .5},-4.5 C{-w * .26},3 {w * .26},3 {w * .5},-4.5 C{w * .26},0.5 {-w * .26},0.5 {-w * .5},-4.5 Z" fill="#fbf7f2"/>')
        b.append(f'<path d="M{-w * .3},9 C{-w * .1},15 {w * .1},15 {w * .3},9 C{w * .1},5 {-w * .1},5 {-w * .3},9 Z" fill="#c4565f" opacity=".9"/>')
        b.append(f'<path d="M{-w * .6},-8 C{-w * .3},4.5 {w * .3},4.5 {w * .6},-8" stroke="{ld}" stroke-width="3" fill="none" stroke-linecap="round"/>')
        b.append(f'<path d="M{-w * .58},-6 C{-w * .3},24 {w * .3},24 {w * .58},-6" stroke="{lc}" stroke-width="3.4" fill="none" stroke-linecap="round" opacity=".9"/>')
    elif kind == "frown":
        b.append(f'<path d="M{-w * .44},9 C{-w * .2},-3 {w * .2},-3 {w * .44},9 C{w * .2},14 {-w * .2},14 {-w * .44},9 Z" fill="url(#lp)"/>')
        b.append(f'<path d="M{-w * .46},8 C{-w * .22},-6 {w * .22},-6 {w * .46},8" stroke="{line}" stroke-width="2.4" fill="none" stroke-linecap="round"/>')
        b.append(f'<ellipse cx="0" cy="16" rx="{w * .18}" ry="3" fill="#000" opacity=".12"/>')
    elif kind == "wobble":
        b.append(f'<path d="M{-w * .42},10 C{-w * .22},-4 {-w * .1},0 0,3 C{w * .1},0 {w * .22},-4 {w * .42},10 C{w * .2},16 {-w * .2},16 {-w * .42},10 Z" fill="url(#lp)"/>')
        b.append(f'<path d="M{-w * .44},9 C{-w * .22},-5 {-w * .1},-1 0,2 C{w * .1},-1 {w * .22},-5 {w * .44},9" stroke="{line}" stroke-width="2.4" fill="none" stroke-linecap="round"/>')
        b.append(f'<ellipse cx="0" cy="19" rx="{w * .22}" ry="4" fill="#000" opacity=".14"/>')
    elif kind == "o":
        b.append(f'<ellipse cx="0" cy="6" rx="{w * .20}" ry="12" fill="{ld}"/><ellipse cx="0" cy="7" rx="{w * .13}" ry="8" fill="#4a1a22"/>')
    elif kind == "open":
        b.append(f'<path d="M{-w * .42},1 C{-w * .2},-6 {w * .2},-6 {w * .42},1 C{w * .22},13 {-w * .22},13 {-w * .42},1 Z" fill="#521c26"/>')
        b.append(f'<path d="M{-w * .36},0 C{-w * .15},-4 {w * .15},-4 {w * .36},0 C{w * .15},2 {-w * .15},2 {-w * .36},0 Z" fill="#fbf7f2"/>')
        b.append(f'<path d="M{-w * .44},0 C{-w * .2},-8 {w * .2},-8 {w * .44},0" stroke="{ld}" stroke-width="3" fill="none"/>')
    elif kind == "bite":
        b.append(f'<path d="M{-w * .46},1 C{-w * .2},17 {w * .2},17 {w * .46},1 C{w * .2},5 {-w * .2},5 {-w * .46},1 Z" fill="url(#lp)"/>')
        b.append(f'<path d="M{-w * .24},4 L{w * .24},4 L{w * .2},12 C{w * .1},13 {-w * .1},13 {-w * .2},12 Z" fill="#fbf7f2"/>')
        b.append(f'<path d="M{-w * .5},1 C{-w * .2},-6 {w * .2},-6 {w * .5},1 C{w * .2},4 {-w * .2},4 {-w * .5},1 Z" fill="{ld}"/>')
    elif kind == "smirk":
        b.append(f'<path d="M{-w * .44},3 C{-w * .2},12 {w * .2},10 {w * .5},-6 C{w * .25},4 {-w * .2},6 {-w * .44},3 Z" fill="url(#lp)"/>')
        b.append(f'<path d="M{-w * .46},4 C{-w * .2},9 {w * .2},7 {w * .52},-7" stroke="{line}" stroke-width="2.4" fill="none" stroke-linecap="round"/>')
    return sprite("".join(b), -50, -28, 100, 56, defs)


MOUTHS = ["neutral", "soft", "smile", "frown", "wobble", "o", "open", "bite", "smirk"]


# ------------------------------------------------------------------ hair
def strands(rnd, n, region, col, op=.22, w=1.8):
    """region = fn(i)->(path d)"""
    out = []
    for i in range(n):
        out.append(f'<path d="{region(i, rnd)}" stroke="{hx(col)}" stroke-width="{w}" fill="none" opacity="{op}" stroke-linecap="round"/>')
    return "".join(out)


def sprite_hair(c):
    """returns (back, front) as lists of sprites, each sprite (img,x,y)"""
    st = c["style"]
    hc = c["hair"]
    hl = lighten(hc, .28)
    hd = darken(hc, .3)
    rnd = random.Random(hash(st) % 1000)
    gradH = lin("hg", [(0, hx(hl), 1), (.5, hx(hc), 1), (1, hx(hd), 1)])
    back, front = None, None
    if st == "hamza":
        defs = gradH
        bk = f'<path d="M-106,-14 C-116,-120 -70,-188 0,-190 C70,-188 116,-120 106,-14 L90,10 L-90,10 Z" fill="url(#hg)"/>'
        back = sprite(hs(bk), HX - 140, HY - 210, 280, 250, defs)
        top = ("M-104,-30 C-118,-132 -66,-196 6,-198 C74,-196 118,-130 104,-30 C102,-52 98,-66 94,-76 "
               "L88,-100 L76,-82 L64,-112 L52,-88 L40,-120 L26,-92 L12,-124 L-2,-94 L-18,-118 L-30,-88 L-46,-110 L-58,-82 L-76,-98 L-86,-70 L-96,-76 C-100,-62 -102,-46 -104,-30 Z")
        s = [f'<path d="{top}" fill="url(#hg)"/>']
        for i in range(26):
            x0 = rnd.uniform(-90, 90)
            s.append(f'<path d="M{x0:.0f},{rnd.uniform(-84, -100):.0f} C{x0 + rnd.uniform(-10, 10):.0f},{-140} {x0 + rnd.uniform(-20, 30):.0f},{-170} {x0 + rnd.uniform(-10, 40):.0f},{rnd.uniform(-190, -176):.0f}" stroke="{hx(hl)}" stroke-width="2" fill="none" opacity=".30"/>')
        s.append(f'<path d="M-102,-34 L-99,6 L-94,-6 L-92,-40 Z" fill="{hx(hd)}"/><path d="M102,-34 L99,6 L94,-6 L92,-40 Z" fill="{hx(hd)}"/>')
        front = sprite(hs("".join(s)), HX - 140, HY - 210, 280, 250, defs)
    elif st == "ammi":
        defs = gradH
        bk = f'<path d="M-108,-10 C-118,-120 -70,-188 0,-190 C70,-188 118,-120 108,-10 L96,30 L-96,30 Z" fill="url(#hg)"/>'
        back = sprite(hs(bk), HX - 140, HY - 210, 280, 270, defs)
        top = ("M-104,-28 C-118,-132 -68,-190 0,-192 C68,-190 118,-132 104,-28 C100,-76 66,-114 0,-118 C-66,-114 -100,-76 -104,-28 Z")
        s = [f'<path d="{top}" fill="url(#hg)"/>']
        for sg in (-1, 1):
            for i in range(9):
                x0 = sg * rnd.uniform(6, 60)
                s.append(f'<path d="M{x0 * 0.5:.0f},{-118 - 2 * i} C{x0 * 0.9:.0f},{-130} {x0 * 1.4:.0f},{-110} {x0 * 1.6 + sg * 20:.0f},{-70 + rnd.uniform(-8, 8):.0f}" stroke="{hx(hl)}" stroke-width="1.6" fill="none" opacity=".28"/>')
            for i in range(7):  # grey streaks near temples
                a = rnd.uniform(0, 1)
                s.append(f'<path d="M{sg * (20 + 14 * i):.0f},{-116 - 3 * i} C{sg * (44 + 12 * i):.0f},{-120} {sg * (80 + 4 * i):.0f},{-96} {sg * (98):.0f},{-46 + 5 * i}" stroke="{hx(c["gray"])}" stroke-width="2.4" fill="none" opacity="{0.55 if i % 2 == 0 else .3}" stroke-linecap="round"/>')
        s.append(f'<path d="M0,-118 L0,-190" stroke="{hx(darken(c["skin"], .35))}" stroke-width="2.6" opacity=".6"/>')
        front = sprite(hs("".join(s)), HX - 140, HY - 210, 280, 250, defs)
    elif st == "sara":
        defs = gradH + lin("hg2", [(0, hx(lighten(hc, .1)), 1), (1, hx(darken(hc, .22)), 1)])
        w = ("M-112,-70 C-150,-10 -140,60 -158,120 C-176,180 -150,236 -170,300 L170,300 C150,236 176,180 158,120 C140,60 150,-10 112,-70 Z")
        bk = f'<path d="{w}" fill="url(#hg2)"/>'
        for i in range(14):
            xo = rnd.uniform(-140, 140)
            bk += f'<path d="M{xo * .7:.0f},-40 C{xo:.0f},60 {xo * 1.1:.0f},140 {xo * 1.05:.0f},290" stroke="{hx(hl)}" stroke-width="2.4" fill="none" opacity=".16"/>'
        back = sprite(hs(bk), HX - 190, HY - 240, 380, 560, defs)
        s = []
        # top mass + clip bump
        s.append(f'<path d="M-104,-34 C-118,-136 -64,-196 4,-198 C70,-196 118,-130 104,-34 C100,-84 62,-122 -4,-124 C-62,-122 -98,-84 -104,-34 Z" fill="url(#hg)"/>')
        # face framing locks (wavy)
        L = ("M-20,-166 C-84,-150 -118,-96 -112,-30 C-108,30 -134,70 -122,130 C-118,160 -134,186 -126,214 L-100,214 C-92,170 -98,128 -92,76 C-86,20 -78,-30 -62,-72 C-50,-100 -34,-126 -10,-136 Z")
        s.append(f'<path d="{L}" fill="url(#hg)"/>')
        s.append(f'<path d="{L}" fill="url(#hg)" transform="scale(-1,1)"/>')
        for sg in (-1, 1):
            for i in range(7):
                s.append(f'<path d="M{sg * (30 + i * 9)},{-150 + i * 3} C{sg * (92 + i * 4)},{-120} {sg * (96 + i * 3)},{-20} {sg * (104 - i * 2)},{70 + i * 16}" stroke="{hx(hl)}" stroke-width="2" fill="none" opacity=".26"/>')
        # claw clip
        s.append('<g transform="translate(26,-174) rotate(-16)"><rect x="-34" y="-12" width="68" height="26" rx="10" fill="#8a4a22"/>'
                 '<rect x="-34" y="-12" width="68" height="26" rx="10" fill="none" stroke="#c98a4a" stroke-width="2"/>'
                 + "".join(f'<ellipse cx="{x}" cy="{y}" rx="4" ry="3" fill="#3a1a0c" opacity=".8"/>' for x, y in ((-18, -2), (-4, 5), (12, -3), (24, 4)))
                 + "".join(f'<rect x="{-30 + i * 10}" y="12" width="6" height="12" rx="3" fill="#7a3e1c"/>' for i in range(7)) + '</g>')
        front = sprite(hs("".join(s)), HX - 190, HY - 240, 380, 560, defs)
    elif st == "noor":
        hj = c["hijab"]
        hjl, hjd = lighten(hj, .22), darken(hj, .30)
        defs = (lin("hj", [(0, hx(hjl), 1), (.5, hx(hj), 1), (1, hx(hjd), 1)]) +
                lin("hj2", [(0, hx(hj), 1), (1, hx(darken(hj, .45)), 1)]))
        bk = ("M-134,-20 C-140,-136 -74,-198 0,-200 C74,-198 140,-136 134,-20 C138,70 126,150 118,230 L-118,230 C-126,150 -138,70 -134,-20 Z")
        back = sprite(hs(f'<path d="{bk}" fill="url(#hj2)"/>'), HX - 190, HY - 240, 380, 520, defs)
        outer = ("M-136,-20 C-142,-138 -76,-200 0,-202 C76,-200 142,-138 136,-20 C138,56 130,120 128,170 C132,226 146,270 164,306 C90,332 -90,332 -164,306 C-146,270 -132,226 -128,170 C-130,120 -138,56 -136,-20 Z")
        inner = ("M0,-136 C54,-136 88,-104 92,-40 C96,30 82,98 54,128 C36,148 16,156 0,156 C-16,156 -36,148 -54,128 C-82,98 -96,30 -92,-40 C-88,-104 -54,-136 0,-136 Z")
        s = [f'<path d="{outer} {inner}" fill="url(#hj)" fill-rule="evenodd"/>']
        # inner shadow rim around face opening
        s.append(f'<path d="{inner}" fill="none" stroke="{hx(darken(hj, .55))}" stroke-width="7" opacity=".38"/>')
        # fabric folds
        for sg in (-1, 1):
            for i, (x1, y1, x2, y2) in enumerate(((112, -90, 126, 10), (104, -50, 118, 90), (110, 150, 132, 300), (96, 160, 100, 320), (80, 180, 70, 330))):
                s.append(f'<path d="M{sg * x1},{y1} C{sg * (x1 + 6)},{(y1 + y2) // 2} {sg * (x2 - 4)},{(y1 + y2) // 2 + 20} {sg * x2},{y2}" stroke="{hx(hjd)}" stroke-width="{3 - i * .3:.1f}" fill="none" opacity=".34"/>')
                s.append(f'<path d="M{sg * (x1 - 8)},{y1 + 4} C{sg * (x1 - 2)},{(y1 + y2) // 2} {sg * (x2 - 12)},{(y1 + y2) // 2 + 20} {sg * (x2 - 8)},{y2}" stroke="{hx(hjl)}" stroke-width="2.4" fill="none" opacity=".30"/>')
        # chin wrap + pin
        s.append(f'<path d="M-98,100 C-70,170 70,170 98,100 C80,200 -80,200 -98,100 Z" fill="{hx(darken(hj, .12))}" opacity=".9"/>')
        s.append(f'<path d="M-92,120 C-40,172 40,172 92,120" stroke="{hx(hjd)}" stroke-width="3" fill="none" opacity=".4"/>')
        s.append('<circle cx="70" cy="176" r="7" fill="#d9a441"/><circle cx="68" cy="174" r="2.4" fill="#fff" opacity=".8"/>')
        front = sprite(hs("".join(s)), HX - 190, HY - 240, 380, 600, defs)
    return back, front


def sprite_glasses(c):
    if not c.get("glasses"):
        return None
    col = "#c6a45a" if c["glasses"][0] == "gold" else "#2a2a30"
    r = 36
    b = []
    for sg in (-1, 1):
        b.append(f'<rect x="{sg * 46 - r}" y="{-6 - 28}" width="{2 * r}" height="56" rx="20" fill="#bfe0ff" opacity=".10"/>')
        b.append(f'<rect x="{sg * 46 - r}" y="{-6 - 28}" width="{2 * r}" height="56" rx="20" fill="none" stroke="{col}" stroke-width="3"/>')
    b.append(f'<path d="M-12,-14 C-4,-20 4,-20 12,-14" fill="none" stroke="{col}" stroke-width="3"/>')
    b.append(f'<path d="M-82,-8 L-104,-4 M82,-8 L104,-4" stroke="{col}" stroke-width="3"/>')
    return sprite(hs("".join(b)), HX - 130, HY - 60, 260, 110)


# ------------------------------------------------------------------ torso + poses
def sprite_torso(c):
    o, tr = c["outfit"], c["trim"]
    od, ol = darken(o, .22), lighten(o, .18)
    defs = lin("tg", [(0, hx(ol), 1), (.6, hx(o), 1), (1, hx(od), 1)]) + lin("sh", [(0, "#000", .30), (1, "#000", 0)], 0, 0, 0, 1)
    sh = ("M56,960 C54,840 74,752 190,714 C230,700 256,696 280,696 C304,696 330,700 370,714 C486,752 506,840 504,960 Z")
    b = [f'<path d="{sh}" fill="url(#tg)"/>']
    st = c["style"]
    sk = c["skin"]
    if st == "ammi":
        # kameez neckline with embroidery, dupatta draped
        b.append(f'<path d="M232,700 C250,740 310,740 328,700 L336,704 C314,770 246,770 224,704 Z" fill="{hx(darken(sk, .1))}"/>')
        b.append(f'<path d="M222,702 C242,774 318,774 338,702" stroke="{hx(c["trim"])}" stroke-width="7" fill="none"/>')
        for i in range(9):
            t = i / 8
            x = 232 + t * 96
            y = 722 + 46 * math.sin(t * math.pi) * .95
            b.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3.4" fill="{hx(lighten(c["trim"], .3))}"/>')
        dup = c["dup"]
        b.append(f'<path d="M92,860 C96,780 150,730 236,708 C214,780 176,860 170,960 L96,960 Z" fill="{hx(dup)}"/>')
        b.append(f'<path d="M468,860 C464,780 410,730 324,708 C346,780 384,860 390,960 L464,960 Z" fill="{hx(darken(dup, .05))}"/>')
        for sg, x0 in ((-1, 150), (1, 410)):
            b.append(f'<path d="M{280 + sg * 128},730 C{280 + sg * 96},800 {280 + sg * 112},880 {280 + sg * 108},960" stroke="{hx(c["trim"])}" stroke-width="5" fill="none" opacity=".8"/>')
            b.append(f'<path d="M{280 + sg * 150},750 C{280 + sg * 120},820 {280 + sg * 140},900 {280 + sg * 134},960" stroke="{hx(darken(dup, .22))}" stroke-width="3" fill="none" opacity=".5"/>')
    elif st == "hamza":
        # hoodie: collar ring + drawstrings + hood behind
        b.append(f'<path d="M214,702 C240,742 320,742 346,702 C336,736 316,752 280,754 C244,752 224,736 214,702 Z" fill="{hx(darken(o, .35))}"/>')
        b.append(f'<path d="M222,706 C246,752 314,752 338,706" stroke="{hx(ol)}" stroke-width="5" fill="none" opacity=".6"/>')
        for sg in (-1, 1):
            b.append(f'<path d="M{280 + sg * 22},742 C{280 + sg * 26},790 {280 + sg * 20},830 {280 + sg * 24},866" stroke="#d8d4cc" stroke-width="4" fill="none" stroke-linecap="round"/>')
            b.append(f'<circle cx="{280 + sg * 24}" cy="868" r="4.4" fill="#d8d4cc"/>')
        for i in range(6):
            b.append(f'<path d="M{110 + i * 70},{790 + (i % 2) * 30} C{130 + i * 68},{860} {120 + i * 70},{900} {134 + i * 68},960" stroke="{hx(od)}" stroke-width="3" fill="none" opacity=".25"/>')
    elif st == "sara":
        # chunky cardigan: tee collar + knit lines + buttons
        b.append(f'<path d="M226,702 C250,752 310,752 334,702 L350,712 C326,800 234,800 210,712 Z" fill="{hx(tr)}"/>')
        b.append(f'<path d="M232,706 C254,750 306,750 328,706" stroke="{hx(darken(tr, .15))}" stroke-width="5" fill="none"/>')
        b.append(f'<path d="M208,710 C236,850 246,900 250,960 L310,960 C314,900 324,850 352,710 L340,706 C316,800 244,800 220,706 Z" fill="{hx(darken(o, .1))}"/>')
        for i in range(6):
            b.append(f'<path d="M{70 + i * 80},700 L{40 + i * 80},960" stroke="{hx(od)}" stroke-width="2.4" opacity=".28"/>')
        for y in (800, 862, 924):
            b.append(f'<circle cx="280" cy="{y}" r="9" fill="#7a4a24"/><circle cx="278" cy="{y - 2}" r="3" fill="#c89a62"/>')
        b.append(f'<path d="M280,760 L280,960" stroke="{hx(od)}" stroke-width="3" opacity=".6"/>')
    elif st == "noor":
        # denim jacket over white tee, hijab drape handled by hair front
        b.append(f'<path d="M222,708 C246,744 314,744 338,708 L346,720 C320,780 240,780 214,720 Z" fill="{hx(tr)}"/>')
        b.append(f'<path d="M212,706 L196,812 L252,960 L280,960 L280,740 Z" fill="{hx(ol)}" opacity=".5"/>')
        b.append(f'<path d="M348,706 L364,812 L308,960 L280,960 L280,740 Z" fill="{hx(od)}" opacity=".35"/>')
        for sx in (-1, 1):
            b.append(f'<path d="M{280 + sx * 46},752 L{280 + sx * 18},960" stroke="#e8c870" stroke-width="3" opacity=".7" stroke-dasharray="6 6"/>')
        b.append(f'<path d="M280,742 L280,960" stroke="{hx(od)}" stroke-width="4" opacity=".6"/>')
        for y in (790, 850, 910):
            b.append(f'<circle cx="280" cy="{y}" r="7" fill="#c9a24a"/><circle cx="278" cy="{y - 2}" r="2.4" fill="#fff" opacity=".7"/>')
    # seatbelt
    if c.get("belt"):
        b.append('<path d="M392,700 L330,960 L378,960 L440,716 Z" fill="#1c1c22"/><path d="M398,704 L346,960" stroke="#2c2c34" stroke-width="3"/>')
        b.append('<rect x="352" y="868" width="34" height="46" rx="7" fill="#9a9aa2" transform="rotate(-14 369 891)"/>')
    # collar bone shadow under neck
    b.append(f'<ellipse cx="280" cy="712" rx="70" ry="16" fill="#000" opacity=".18"/>')
    b.append(f'<rect x="0" y="940" width="560" height="20" fill="url(#sh)" opacity="0"/>')
    return sprite("".join(b), 0, 680, 560, 280, defs)


def hand_svg(c, x, y, rot=0, sc=1.0, mirror=1):
    sk = c["skin"]
    sd = hx(darken(sk, .18))
    sl = hx(lighten(sk, .08))
    s = (f'<g transform="translate({x},{y}) rotate({rot}) scale({sc * mirror},{sc})">'
         f'<ellipse cx="0" cy="6" rx="31" ry="30" fill="{hx(sk)}"/>'
         f'<ellipse cx="-8" cy="-4" rx="18" ry="14" fill="{sl}" opacity=".45"/>')
    for i in range(4):
        fx = -22 + i * 14.5
        s += (f'<rect x="{fx - 6.5}" y="-40" width="13" height="40" rx="6.5" fill="{hx(sk)}"/>'
              f'<rect x="{fx - 6.5}" y="-40" width="13" height="40" rx="6.5" fill="none" stroke="{sd}" stroke-width="1.2" opacity=".55"/>'
              f'<ellipse cx="{fx}" cy="-34" rx="4" ry="3" fill="#fff" opacity=".18"/>')
    s += f'<path d="M-32,6 C-44,-4 -48,-22 -38,-30" stroke="{hx(sk)}" stroke-width="15" fill="none" stroke-linecap="round"/></g>'
    return s


def phone_back(c, x, y, rot=0, w=126, h=218):
    p = c["phone"]
    return (f'<g transform="translate({x},{y}) rotate({rot})">'
            f'<rect x="{-w / 2 + 4}" y="{-h / 2 + 8}" width="{w}" height="{h}" rx="22" fill="#000" opacity=".28"/>'
            f'<rect x="{-w / 2}" y="{-h / 2}" width="{w}" height="{h}" rx="22" fill="{hx(p)}"/>'
            f'<rect x="{-w / 2}" y="{-h / 2}" width="{w}" height="{h}" rx="22" fill="none" stroke="{hx(darken(p, .3))}" stroke-width="3"/>'
            f'<rect x="{-w / 2 + 12}" y="{-h / 2 + 12}" width="46" height="46" rx="14" fill="{hx(darken(p, .45))}"/>'
            f'<circle cx="{-w / 2 + 28}" cy="{-h / 2 + 28}" r="9" fill="#14141a"/><circle cx="{-w / 2 + 28}" cy="{-h / 2 + 28}" r="4" fill="#4a5a78"/>'
            f'<circle cx="{-w / 2 + 46}" cy="{-h / 2 + 46}" r="5" fill="#14141a"/></g>')


def sleeve(c, pts, width, cuff=True):
    sl = c["sleeve"]
    sk = c["skin"]
    d = "M" + " L".join(f"{x},{y}" for x, y in pts) if len(pts) == 2 else f"M{pts[0][0]},{pts[0][1]} C{pts[1][0]},{pts[1][1]} {pts[2][0]},{pts[2][1]} {pts[3][0]},{pts[3][1]}"
    b = f'<path d="{d}" stroke="{hx(darken(sl, .18))}" stroke-width="{width + 6}" fill="none" stroke-linecap="round"/>'
    b += f'<path d="{d}" stroke="{hx(sl)}" stroke-width="{width}" fill="none" stroke-linecap="round"/>'
    b += f'<path d="{d}" stroke="{hx(lighten(sl, .2))}" stroke-width="{width * .28}" fill="none" stroke-linecap="round" opacity=".16" transform="translate(-6,-4)"/>'
    return b


def sprite_pose(c, pose):
    """arms + hands + phone, canvas coords. returns sprite (img,x,y); 'over' poses are drawn above the head"""
    b = []
    sl = c["sleeve"]
    cuffc = hx(lighten(sl, .1))
    if pose in ("hold", "lap"):
        b.append(sleeve(c, [(120, 800), (130, 880), (170, 920), (222, 900)], 66))
        b.append(sleeve(c, [(440, 800), (430, 880), (390, 920), (338, 900)], 66))
        b.append(phone_back(c, 280, 846, 0))
        b.append(hand_svg(c, 232, 905, 78, .86, 1))
        b.append(hand_svg(c, 328, 905, -78, .86, -1))
    elif pose == "chest":
        b.append(sleeve(c, [(440, 800), (452, 880), (420, 930), (384, 912)], 66))
        b.append(phone_back(c, 372, 884, -12, 112, 196))
        b.append(hand_svg(c, 338, 928, -70, .80, -1))
        b.append(sleeve(c, [(116, 790), (132, 950)], 66))
        b.append(sleeve(c, [(132, 950), (236, 806)], 60))
        b.append(hand_svg(c, 250, 794, 62, .84, 1))
    elif pose == "mouth":
        b.append(sleeve(c, [(440, 800), (452, 880), (420, 930), (384, 912)], 66))
        b.append(phone_back(c, 372, 884, -12, 112, 196))
        b.append(hand_svg(c, 338, 928, -70, .80, -1))
        b.append(sleeve(c, [(116, 790), (128, 950)], 66))
        b.append(sleeve(c, [(128, 950), (240, 614)], 58))
        b.append(hand_svg(c, 256, 584, 20, .86, 1))
    elif pose == "face":
        b.append(sleeve(c, [(440, 800), (452, 880), (420, 930), (384, 912)], 66))
        b.append(phone_back(c, 372, 884, -12, 112, 196))
        b.append(hand_svg(c, 338, 928, -70, .80, -1))
        b.append(sleeve(c, [(116, 790), (124, 950)], 66))
        b.append(sleeve(c, [(124, 950), (226, 562)], 58))
        b.append(hand_svg(c, 238, 520, 12, .80, 1))
    return sprite("".join(b), 0, 440, 560, 520)


def sprite_flush(c):
    """red-eyed, pink-nosed 'crying' overlay in head-local coords"""
    defs = rad("fl", [(0, "#ff5a6a", .55), (1, "#ff5a6a", 0)])
    b = f'<ellipse cx="0" cy="44" rx="26" ry="22" fill="url(#fl)"/>'
    for sg in (-1, 1):
        b += f'<ellipse cx="{sg * 46}" cy="2" rx="34" ry="18" fill="url(#fl)" opacity=".7"/>'
        b += f'<ellipse cx="{sg * 58}" cy="46" rx="30" ry="22" fill="url(#fl)" opacity=".5"/>'
    return sprite(hs(b), HX - 100, HY - 50, 200, 150, defs)


def sprite_tear(c):
    defs = lin("tr", [(0, "#cfe8ff", .0), (.2, "#cfe8ff", .9), (1, "#9ac8ff", .95)])
    return sprite('<path d="M0,-12 C6,0 8,6 0,12 C-8,6 -6,0 0,-12 Z" fill="url(#tr)"/><circle cx="-1.6" cy="3" r="1.8" fill="#fff" opacity=".9"/>', -12, -16, 24, 32, defs)


# ------------------------------------------------------------------ build / cache
def build_rig(name):
    path = os.path.join(CACHE, name + ".pkl")
    c = CAST[name]
    key = hashlib.md5((open(__file__).read() + name).encode()).hexdigest()
    if os.path.exists(path):
        try:
            d = pickle.load(open(path, "rb"))
            if d["key"] == key:
                return d
        except Exception:
            pass
    rig = dict(key=key, c=c)
    rig["face"] = sprite_face(c)
    rig["neck"] = sprite_neck(c)
    rig["torso"] = sprite_torso(c)
    rig["sclera"] = sprite_sclera(c)
    rig["iris"] = sprite_iris(c)
    rig["lids"] = [sprite_lid(c, k / (EYE_LEVELS - 1)) for k in range(EYE_LEVELS)]
    rig["brow"] = sprite_brow(c)
    rig["mouths"] = {m: sprite_mouth(c, m) for m in MOUTHS}
    rig["hair_back"], rig["hair_front"] = sprite_hair(c)
    rig["glasses"] = sprite_glasses(c)
    rig["poses"] = {p: sprite_pose(c, p) for p in ("hold", "chest", "mouth", "face")}
    rig["flush"] = sprite_flush(c)
    rig["tear"] = sprite_tear(c)
    pickle.dump(rig, open(path, "wb"))
    return rig


if __name__ == "__main__":
    import sys
    for n in (sys.argv[1:] or CAST):
        build_rig(n)
        print("built", n)
