"""Sound design: stereo ambience per location, phone tones per character, haptics, keyboard taps, heartbeat hook,
synth piano + pad score with reverb."""
import math, wave
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 44100
NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def hz(name):
    n = NOTE[name[0]] + (1 if "#" in name else 0) - (1 if "b" in name else 0)
    octv = int(name[-1])
    return 440.0 * 2 ** ((n - 9 + 12 * (octv - 4)) / 12)


def bp(x, lo, hi, order=2):
    sos = butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return sosfilt(sos, x)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, btype="low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, btype="high", fs=SR, output="sos"), x)


class Mix:
    def __init__(self, dur):
        self.n = int(SR * dur) + SR
        self.L = np.zeros(self.n, np.float32)
        self.R = np.zeros(self.n, np.float32)

    def add(self, t, sig, pan=.5, gain=1.0):
        i0 = int(t * SR)
        if i0 >= self.n or i0 < 0:
            return
        i1 = min(self.n, i0 + len(sig))
        s = sig[:i1 - i0].astype(np.float32) * gain
        self.L[i0:i1] += s * (1 - pan) ** .5 * 1.414 * .7071
        self.R[i0:i1] += s * pan ** .5 * 1.414 * .7071


def env_exp(n, tau, attack=.003):
    x = np.arange(n) / SR
    return np.exp(-x / tau) * np.minimum(1, x / attack)


def tone(f, d, amp=1.0, tau=.12, harm=(1,), attack=.003, glide=None):
    n = int(SR * d)
    x = np.arange(n) / SR
    fr = f if glide is None else f + (glide - f) * x / d
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(fr, (n,))) / SR
    s = sum(a * np.sin((i + 1) * ph) for i, a in enumerate(harm))
    return (amp * s * env_exp(n, tau, attack)).astype(np.float32)


def phone_tone(kind):
    if kind == "marimba":   # Ammi: warm two-note marimba
        return _seq([(659.3, 0), (880, .13)], .55, .09, (1, .35, .12))
    if kind == "tok":       # Hamza: low woody tok
        return _seq([(392, 0), (294, .11)], .6, .07, (1, .5, .2))
    if kind == "chime":     # Sara: soft glass chime
        return _seq([(1174.7, 0), (1568, .1), (2093, .2)], .38, .22, (1, .2))
    return _seq([(1318.5, 0), (1760, .09)], .45, .12, (1, .25))  # Noor: crisp ping


def _seq(notes, amp, tau, harm):
    tail = .8
    out = np.zeros(int(SR * (notes[-1][1] + tail)), np.float32)
    for f, o in notes:
        s = tone(f, .7, amp, tau, harm)
        i = int(o * SR)
        out[i:i + len(s)] += s[:len(out) - i]
    return out


def send_whoosh():
    n = int(SR * .16)
    x = np.random.default_rng(1).normal(0, 1, n)
    x = bp(x, 900, 5200)
    e = np.sin(np.linspace(0, np.pi, n)) ** 2
    return (x * e * .12).astype(np.float32)


def haptic(pulses=2):
    out = np.zeros(int(SR * .36), np.float32)
    for k in range(pulses):
        n = int(SR * .06)
        x = np.arange(n) / SR
        s = np.sin(2 * np.pi * 150 * x) * np.exp(-x / .02) * .5
        i = int(k * .12 * SR)
        out[i:i + n] += s
    return out


def key_click(rng, soft=1.0):
    n = int(SR * .02)
    x = rng.normal(0, 1, n)
    x = hp(x, 1800)
    e = np.exp(-np.arange(n) / (SR * .004))
    th = np.sin(2 * np.pi * 180 * np.arange(n) / SR) * np.exp(-np.arange(n) / (SR * .008)) * .25
    return ((x * e * .5 + th) * .25 * soft).astype(np.float32)


def heartbeat():
    n = int(SR * .5)
    out = np.zeros(n, np.float32)
    for off, amp in ((0, 1.0), (.17, .7)):
        m = int(SR * .16)
        x = np.arange(m) / SR
        s = np.sin(2 * np.pi * (58 - 18 * x * 6) * x) * np.exp(-x / .05) * amp
        i = int(off * SR)
        out[i:i + m] += s
    return out * .6


def impact():
    n = int(SR * 1.4)
    x = np.arange(n) / SR
    sub = np.sin(2 * np.pi * (70 - 25 * np.minimum(x, .5) / .5) * x) * np.exp(-x / .35)
    noise = lp(np.random.default_rng(3).normal(0, 1, n), 1800) * np.exp(-x / .12) * .6
    return ((sub * .9 + noise) * .6).astype(np.float32)


def riser(d):
    n = int(SR * d)
    x = np.random.default_rng(2).normal(0, 1, n)
    out = np.zeros(n)
    for k in range(6):
        a, b = k * n // 6, (k + 1) * n // 6
        out[a:b] = bp(x[a:b], 300 + k * 700, 900 + k * 1400)
    e = np.linspace(0, 1, n) ** 2.2
    return (out * e * .16).astype(np.float32)


def rain_bed(dur, level, bright, seed):
    n = int(SR * dur)
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, n)
    y = bp(x, 500 + 800 * bright, 5000 + 3000 * bright)
    mod = 0.75 + 0.25 * lp(rng.normal(0, 1, n), 1.5, 1)
    mod /= np.abs(mod).max() + 1e-6
    return (y * (0.55 + 0.45 * mod) * level).astype(np.float32)


def tick(rng):
    n = int(SR * .03)
    x = bp(rng.normal(0, 1, n), 1500, 4500)
    return (x * np.exp(-np.arange(n) / (SR * .006)) * .22).astype(np.float32)


def swish(d, rng):
    n = int(SR * d)
    x = bp(rng.normal(0, 1, n), 300, 2400)
    e = np.exp(-((np.arange(n) - n / 2) ** 2) / (2 * (n / 5) ** 2))
    return (x * e * .35).astype(np.float32)


def piano_note(f, d, vel=.6):
    n = int(SR * d)
    x = np.arange(n) / SR
    s = np.zeros(n)
    amps = [1.0, .55, .32, .18, .10, .06]
    for i, a in enumerate(amps, 1):
        dec = 1.8 / (1 + .7 * (i - 1))
        s += a * np.sin(2 * np.pi * f * i * (1 + 0.0004 * i * i) * x + .3 * i) * np.exp(-x / dec)
    s += .5 * np.sin(2 * np.pi * f * .5 * x) * np.exp(-x / .4) * .15
    hammer = lp(np.random.default_rng(int(f)).normal(0, 1, n), 2200) * np.exp(-x / .012) * .25
    s = (s + hammer) * np.minimum(1, x / .004)
    return (s * vel * .22).astype(np.float32)


def pad_chord(freqs, d):
    n = int(SR * d)
    x = np.arange(n) / SR
    s = np.zeros(n)
    for f in freqs:
        for det in (-.002, 0, .002):
            s += np.sin(2 * np.pi * f * (1 + det) * x) + .3 * np.sin(2 * np.pi * 2 * f * (1 + det) * x)
    s = lp(s, 1600)
    e = np.minimum(1, x / 1.2) * np.minimum(1, (d - x) / 1.4)
    return (s * e * .05 / len(freqs)).astype(np.float32)


PROG = [("A2", ["A3", "C4", "E4"]), ("F2", ["F3", "A3", "C4"]), ("C3", ["G3", "C4", "E4"]), ("G2", ["G3", "B3", "D4"])]
ARP = [0, 1, 2, 1, 2, 1, 2, 1]


def score(dur, intensity, dips, bpm=66):
    beat = 60 / bpm
    bar = 4 * beat
    m = Mix(dur)
    nb = int(dur / bar) + 2
    rng = np.random.default_rng(8)
    for b in range(nb):
        root, ch = PROG[b % 4]
        t0 = b * bar
        it = intensity(t0)
        if it <= .02:
            continue
        m.add(t0, piano_note(hz(root), 3.4, .55 * it), .5)
        for k in range(8):
            tt = t0 + k * beat / 2
            if any(a <= tt <= bb for a, bb in dips):
                continue
            f = hz(ch[ARP[k] % 3]) * (2 if k % 4 == 3 and it > .6 else 1)
            m.add(tt + rng.uniform(0, .012), piano_note(f, 1.8, (.35 + .35 * it) * (1.0 if k % 2 == 0 else .75)), .46 + .08 * (k % 3) / 2)
        if it > .55:
            m.add(t0, pad_chord([hz(c) for c in ch], bar + 1.0), .5, it)
    return m


def reverb(sig, wet=.28, seconds=2.4):
    n = int(SR * seconds)
    rng = np.random.default_rng(4)
    ir = rng.normal(0, 1, n) * np.exp(-np.arange(n) / (SR * seconds / 4.5))
    ir = lp(ir, 5200)
    ir /= np.abs(ir).sum() * .05
    return sig * (1 - wet) + fftconvolve(sig, ir)[:len(sig)] * wet


def make(ep, path):
    sp = ep.spec
    dur = ep.dur + .4
    m = Mix(dur)
    rng = np.random.default_rng(11)
    L = ep.lock_dur
    kinds = [s["kind"] for s in sp["scenes"]]
    # --- ambience (top = left-ish, bottom = right-ish)
    for h, kd in enumerate(kinds):
        pan = .30 if h == 0 else .70
        n = int(SR * dur)
        if kd == "livingroom":
            m.add(0, rain_bed(dur, .035, .0, 21), pan, 1)
            room = lp(rng.normal(0, 1, n), 220, 1) * .05
            m.add(0, room.astype(np.float32), pan, 1)
            for i in range(int(dur)):
                m.add(i + .0, tick(rng), pan, 1.0 if i % 2 == 0 else .75)
        elif kd == "car":
            m.add(0, rain_bed(dur, .11, 1.0, 22 + h), pan, 1)
            hum = lp(rng.normal(0, 1, n), 120, 2) * .09
            m.add(0, hum.astype(np.float32), pan, 1)
            k = 0
            while 2.5 + k * 11 < dur:
                m.add(2.5 + k * 11 - 1.2, swish(2.4, rng), pan, 1)
                k += 1
        else:
            m.add(0, rain_bed(dur, .04, .2, 25), pan, 1)
            m.add(0, (lp(rng.normal(0, 1, n), 300, 1) * .04).astype(np.float32), pan, 1)
    # --- hook: heartbeat + phone buzzes + riser + impact
    if L:
        t = 0.0
        while t < L - .3:
            m.add(t, heartbeat(), .5, .9)
            t += .82
        for c in sp["lock"]["cards"]:
            m.add(c["t"], haptic(2), .5, 1.3)
            m.add(c["t"], _seq([(988, 0), (1319, .1)], .22, .1, (1, .2)), .5, 1.0)
        m.add(max(0, L - 1.4), riser(1.25), .5, 1)
        m.add(L - .15, impact(), .5, 1.0)
    # --- per-event sfx
    chars = sp["chars"]
    from episode import TONES, TYPE_SPEED
    for mm in ep.msgs:
        who = mm["who"]
        pan_s = .30 if who == 0 else .70
        for (a, b) in mm["spans"]:
            t = a
            per = TYPE_SPEED[chars[who]]
            slow = per > .04
            while t < b:
                m.add(t, key_click(rng, 1.0 if not slow else .8), pan_s, 1)
                t += rng.uniform(.25, .42) if slow else rng.uniform(.07, .14)
        if mm["ta"] is None:
            # backspace burst
            t = mm["hold_end"]
            while t < mm["del_end"]:
                m.add(t, key_click(rng, .9), pan_s, 1)
                t += .045
            continue
        ta = mm["ta"]
        m.add(ta, send_whoosh(), pan_s, 1.0)
        rp = .70 if who == 0 else .30
        m.add(ta + .05, phone_tone(TONES[chars[1 - who]]), rp, 1.0)
        m.add(ta + .05, haptic(2), rp, .7)
    for (t, kind) in ep.sfx:
        if isinstance(kind, tuple) and kind[0] == "banner":
            m.add(t, _seq([(784, 0)], .2, .08, (1, .3)), .5, 1)
    # --- score
    cry_times = [mm["ta"] for mm in ep.msgs if mm["ta"] is not None]
    ghost = [(mm["ts"] - .2, mm["del_end"] + .4) for mm in ep.msgs if mm["ta"] is None]
    end = ep.end_msgs

    def intensity(t):
        if t < L - .3:
            return 0.0
        x = (t - L) / max(1.0, end - L)
        base = .32 + .5 * x
        if t >= end - .5:
            base = 1.0
        return min(1.0, base)

    sc = score(dur, intensity, ghost)
    sc.L = reverb(sc.L, .34)
    sc.R = reverb(sc.R, .34)
    # sidechain-ish duck under message tones
    duck = np.ones(m.n, np.float32)
    for mm in ep.msgs:
        if mm["ta"] is not None:
            i0, i1 = int(mm["ta"] * SR), int((mm["ta"] + .5) * SR)
            duck[i0:i1] *= .62
    gain = .55
    m.L += sc.L[:m.n] * gain * duck
    m.R += sc.R[:m.n] * gain * duck
    out = np.stack([m.L[:int(SR * dur)], m.R[:int(SR * dur)]], axis=1)
    out = np.tanh(out * 1.4) / 1.4
    fade = np.minimum(1, np.arange(len(out)) / (SR * .3))[:, None] * np.minimum(1, (len(out) - np.arange(len(out))) / (SR * .6))[:, None]
    out = out * fade
    out = out / (np.abs(out).max() + 1e-6) * .9
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
