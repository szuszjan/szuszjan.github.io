"""NEON HYDRA - demo parts. Each part: start(ctx) once, then draw(ctx, t, beat) every frame.

t    = song rows since the part started (1 row = 1/16 bar, ~120 ms)
beat = dict(kick=0..1, snare=0..1)  (1 right on the hit, decays to 0)
"""

import math
import random
from array import array

try:
    from . import fx
except ImportError:
    from apps.NeonHydra import fx

_W = const(240)
_H = const(135)

# C64-like 16 color palette (RGB)
C64 = (
    (0, 0, 0), (255, 255, 255), (136, 0, 0), (170, 255, 238),
    (204, 68, 204), (0, 204, 85), (0, 0, 170), (238, 238, 119),
    (221, 136, 85), (102, 68, 0), (255, 119, 119), (51, 51, 51),
    (119, 119, 119), (170, 255, 102), (0, 136, 255), (187, 187, 187),
)


def scale(rgb, k):
    return (min(255, int(rgb[0] * k)), min(255, int(rgb[1] * k)), min(255, int(rgb[2] * k)))


# ---------------------------------------------------------------- shared helpers
class Stars:
    """3-layer horizontal parallax starfield."""

    def __init__(self, ctx, n=54, ymin=0, ymax=_H):
        rnd = random.random
        self.ctx = ctx
        self.x = [rnd() * _W for _ in range(n)]
        self.y = [int(ymin + rnd() * (ymax - ymin)) for _ in range(n)]
        self.layer = [i % 3 for i in range(n)]
        self.cols = [ctx.c(scale((255, 255, 255), k)) for k in (0.35, 0.65, 1.0)]
        self.last = None

    def draw(self, t, speed=1.0):
        dt = 0 if self.last is None else (t - self.last)
        self.last = t
        if dt < 0 or dt > 8:
            dt = 0
        px = self.ctx.fb.pixel
        xs, ys, ls, cols = self.x, self.y, self.layer, self.cols
        for i in range(len(xs)):
            lay = ls[i]
            x = xs[i] - dt * speed * (1.5 + lay * 2.5)
            if x < 0:
                x += _W
            xs[i] = x
            px(int(x), ys[i], cols[lay])
            if lay == 2:
                px(int(x) + 1, ys[i], cols[1])


def copper_grad(ctx, rgb, n=15):
    """Raster bar gradient (dark-bright-dark), returns list of fb colors."""
    out = []
    for i in range(n):
        k = 1 - abs(i - (n - 1) / 2) / ((n - 1) / 2)
        out.append(ctx.c(scale(rgb, 0.15 + 0.95 * k)))
    return out


class Copper:
    """Moving raster bars into a row-color array."""

    def __init__(self, ctx, colors, bg=(0, 0, 0)):
        self.ctx = ctx
        self.grads = [copper_grad(ctx, C64[c] if isinstance(c, int) else c) for c in colors]
        self.bg = ctx.c(bg)
        self.rowc = array("H", [self.bg] * _H)

    def build(self, t, center=67, amp=50, spread=0.6, speed=0.12, flash=0.0, count=None):
        rowc = self.rowc
        bg = self.bg
        for y in range(_H):
            rowc[y] = bg
        grads = self.grads if count is None else self.grads[:count]
        sin = math.sin
        for i, g in enumerate(grads):
            yc = int(center + amp * sin(t * speed + i * spread)) - len(g) // 2
            for j, col in enumerate(g):
                y = yc + j
                if 0 <= y < _H:
                    rowc[y] = col
        if flash > 0.05:
            w = self.ctx.c(scale((255, 255, 255), flash * 0.5))
            for y in range(0, _H, 2):
                if rowc[y] == bg:
                    rowc[y] = w
        return rowc


def text_center(ctx, s, y, rgb, font=None, shadow=True):
    D = ctx.D
    w = D.get_total_width(s, font)
    x = (_W - w) // 2
    if shadow:
        D.text(s, x + 1, y + 1, ctx.rgb565((0, 0, 0)), font)
    D.text(s, x, y, ctx.rgb565(rgb), font)


class BigText:
    """Text rendered with fx.big_text (16x32 font, optional 2x scale)."""

    def __init__(self, ctx, text, grad):
        self.text = text
        self.cols = bytearray(len(text) * 64)  # 32-bit column masks
        self.ncols = fx.build_cols(ctx.BIG.FONT, text.encode(), self.cols)
        self.ctab = array("H", ctx.sin16)
        for i in range(64):
            self.ctab.append(grad[i])
        self.prm = array("i", [0] * 12)
        self.prm[0] = self.ncols
        self.prm[11] = _H

    def width(self, sh):
        return self.ncols << sh

    def draw(self, ctx, x, y, amp=0, phase=0, xs=2, sh=1, ys=2, goff=0, shadow=0, y0=0, y1=_H):
        q = self.prm
        q[1] = -x
        q[2] = y
        q[3] = amp
        q[4] = phase
        q[5] = xs
        q[6] = sh
        q[7] = ys
        q[8] = goff
        q[9] = shadow
        q[10] = y0
        q[11] = y1
        fx.big_text(ctx.fb, self.cols, q, self.ctab)


def gradient64(ctx, stops):
    """64-entry looping gradient through RGB stops."""
    out = []
    n = len(stops)
    for i in range(64):
        f = i * n / 64
        a = stops[int(f) % n]
        b = stops[(int(f) + 1) % n]
        k = f - int(f)
        out.append(ctx.c((int(a[0] + (b[0] - a[0]) * k), int(a[1] + (b[1] - a[1]) * k),
                          int(a[2] + (b[2] - a[2]) * k))))
    return out


def flash_screen(ctx, amount, rgb=(255, 255, 255)):
    """Blend the whole frame toward a color (amount 0..1)."""
    k = int(amount * 32)
    if k <= 0:
        return
    q = ctx.blend_prm
    q[0] = min(32, k)
    q[1] = rgb[0] >> 3
    q[2] = rgb[1] >> 2
    q[3] = rgb[2] >> 3
    q[4] = 1 if ctx.swap else 0
    fx.blend(ctx.fb, q)


# ---------------------------------------------------------------- parts
class Intro:
    """Raster bars appear, NEON HYDRA logo drops in."""

    def start(self, ctx):
        self.copper = Copper(ctx, (6, 14, 3, 1, 3, 14, 6, 4, 10, 7))
        neon = gradient64(ctx, ((255, 60, 200), (255, 255, 255), (60, 220, 255), (40, 40, 255)))
        self.l1 = BigText(ctx, "NEON", neon)
        self.l2 = BigText(ctx, "HYDRA", neon)

    def draw(self, ctx, t, beat):
        count = 1 + min(9, int(t / 6))
        rowc = self.copper.build(t, amp=55, speed=0.18, spread=0.45, flash=beat["kick"], count=count)
        fx.fill_rows(ctx.fb, rowc, 0, _H)
        if 6 < t < 30 and int(t * 2) % 24 < 21:
            text_center(ctx, "a szuszjan production", 63, (255, 255, 255), None)
        if t > 32:
            # NEON falls from above with a bounce
            k = min(1.0, (t - 32) / 10)
            bounce = abs(math.cos(k * 4.7)) * (1 - k)
            y1 = int(-4 - 70 * bounce)
            self.l1.draw(ctx, (_W - self.l1.width(1)) // 2, y1, amp=4, phase=int(t * 6),
                         goff=int(t * 2), shadow=ctx.c((0, 0, 40)))
        if t > 44:
            k = min(1.0, (t - 44) / 10)
            bounce = abs(math.cos(k * 4.7)) * (1 - k)
            y2 = int(58 + 70 * bounce)
            self.l2.draw(ctx, (_W - self.l2.width(1)) // 2, y2, amp=4, phase=int(t * 6) + 60,
                         goff=int(t * 2) + 20, shadow=ctx.c((0, 0, 40)))
        if t > 64:
            msgs = ("for the M5 Cardputer", "running MicroHydra", "100% MicroPython + viper",
                    "turn the volume up!")
            i = int((t - 64) / 16) % len(msgs)
            if int(t * 2) % 32 < 28:
                text_center(ctx, msgs[i], 125, (255, 255, 255), None)


class Scroller:
    """Big sine scroller over a starfield with raster bars."""

    TEXT = ("HELLO CARDPUTER!  THIS IS NEON HYDRA, A LITTLE OLD SCHOOL DEMO.  "
            "EVERY PIXEL AND EVERY NOTE IS COMPUTED LIVE ON THE ESP32-S3 ...  "
            "SPACE = NEXT PART   ESC = QUIT")

    def start(self, ctx):
        self.stars = Stars(ctx)
        grad = gradient64(ctx, ((255, 220, 0), (255, 80, 0), (255, 0, 120), (120, 0, 255),
                                (0, 160, 255), (0, 255, 160)))
        self.txt = BigText(ctx, self.TEXT, grad)
        self.top = copper_grad(ctx, C64[14], 9)
        self.bot = copper_grad(ctx, C64[4], 9)
        self.shadow = ctx.c((30, 0, 50))

    def draw(self, ctx, t, beat):
        fb = ctx.fb
        fb.fill(ctx.c((0, 0, 0)))
        self.stars.draw(t, 1.0)
        k = beat["kick"]
        for i, col in enumerate(self.top):
            fb.hline(0, i, _W, col)
        for i, col in enumerate(self.bot):
            fb.hline(0, _H - 9 + i, _W, col if k < 0.5 else self.top[i])
        total = self.txt.width(1) + _W
        x = _W - int(t * total / 256)
        self.txt.draw(ctx, x, 36, amp=26, phase=int(t * 8), xs=2, sh=1, ys=2,
                      goff=int(t * 3), shadow=self.shadow, y0=9, y1=_H - 9)


class Plasma:
    """Full screen plasma with changing palettes and messages."""

    MSGS = ("PLASMA!", "4 CHANNELS", "50 HZ ARPEGGIOS", "PWM LEAD",
            "NO SAMPLES", "NO PSRAM", "VIPER POWER", "CARDPUTER")

    def start(self, ctx):
        self.prm = array("i", [0] * 5)
        self.pals = []
        for ph in ((0.0, 2.1, 4.2), (0.0, 1.0, 3.0), (3.5, 0.5, 2.0)):
            pal = array("H", [0] * 256)
            for i in range(256):
                a = i * 6.2832 / 256
                r = int(128 + 127 * math.sin(a + ph[0]))
                g = int(128 + 127 * math.sin(a * 2 + ph[1]))
                b = int(128 + 127 * math.sin(a + ph[2]))
                pal[i] = ctx.c((r, g // 2 + 40, b))
            self.pals.append(pal)

    def draw(self, ctx, t, beat):
        q = self.prm
        q[0] = int(t * 5)
        q[1] = int(t * 3)
        q[2] = int(-t * 4)
        q[3] = int(t * 7)
        q[4] = int(t * 2 + beat["kick"] * 40)
        pal = self.pals[int(t / 64) % len(self.pals)]
        fx.plasma(ctx.fb, ctx.sint, pal, q)
        msg = self.MSGS[int(t / 32) % len(self.MSGS)]
        y = 52 + int(6 * math.sin(t * 0.3))
        text_center(ctx, msg, y, (255, 255, 255), ctx.BIG)


class Balls:
    """Vector balls morphing between shapes."""

    def start(self, ctx):
        self.stars = Stars(ctx, 40)
        n = 27
        cube = [((i % 3) - 1, ((i // 3) % 3) - 1, (i // 9) - 1) for i in range(n)]
        sphere = []
        for i in range(n):
            y = 1 - 2 * (i + 0.5) / n
            r = math.sqrt(1 - y * y)
            a = i * 2.39996
            sphere.append((math.cos(a) * r * 1.3, y * 1.3, math.sin(a) * r * 1.3))
        torus = []
        for i in range(n):
            a = (i // 3) * 6.2832 / 9
            b = (i % 3) * 6.2832 / 3
            rr = 1.0 + 0.4 * math.cos(b)
            torus.append((math.cos(a) * rr, 0.4 * math.sin(b), math.sin(a) * rr))
        helix = []
        for i in range(n):
            a = i * 6.2832 * 2 / n
            helix.append((math.cos(a) * 0.9, (i / n) * 2.4 - 1.2, math.sin(a) * 0.9))
        self.shapes = (cube, sphere, torus, helix)
        hues = ((255, 80, 200), (80, 200, 255), (255, 220, 80))
        self.cols = [[ctx.c(scale(h, 0.3 + 0.7 * k / 7)) for k in range(8)] for h in hues]
        self.hi = ctx.c((255, 255, 255))

    def draw(self, ctx, t, beat):
        fb = ctx.fb
        fb.fill(ctx.c((0, 0, 12)))
        self.stars.draw(t, 0.4)
        seg = t / 32
        i0 = int(seg) % 4
        i1 = (i0 + 1) % 4
        f = seg - int(seg)
        f = 0 if f < 0.5 else (f - 0.5) * 2
        f = f * f * (3 - 2 * f)
        s0, s1 = self.shapes[i0], self.shapes[i1]
        ay = t * 0.07
        ax = t * 0.045
        ca, sa, cb, sb = math.cos(ay), math.sin(ay), math.cos(ax), math.sin(ax)
        zoom = 34 * (1 + 0.12 * beat["kick"])
        pts = []
        for j in range(len(s0)):
            a, b = s0[j], s1[j]
            x = a[0] + (b[0] - a[0]) * f
            y = a[1] + (b[1] - a[1]) * f
            z = a[2] + (b[2] - a[2]) * f
            x, z = x * ca + z * sa, z * ca - x * sa
            y, z = y * cb - z * sb, z * cb + y * sb
            p = 3.2 / (z + 4.0)
            pts.append((z, int(120 + x * zoom * p * 1.4), int(67 + y * zoom * p * 1.4), p, j % 3))
        pts.sort()
        pts.reverse()
        for z, x, y, p, hue in pts:
            r = int(2 + 4.5 * p)
            k = int(max(0, min(7, (1.2 - z) * 3)))
            fb.ellipse(x, y, r, r, self.cols[hue][k], True)
            fb.pixel(x - r // 3, y - r // 3, self.hi)


class Tunnel:
    """XOR tunnel accelerating into the drop, flashes on snares."""

    def start(self, ctx):
        self.prm = array("i", [0, 0])
        pal = array("H", [0] * 256)
        hues = ((255, 0, 128), (255, 80, 0), (255, 220, 0), (0, 255, 120),
                (0, 200, 255), (60, 60, 255), (200, 0, 255), (255, 255, 255))
        for chk in range(2):
            for h in range(8):
                for s in range(16):
                    k = (s / 15) * (1.0 if chk else 0.45)
                    pal[chk * 128 + h * 16 + s] = ctx.c(scale(hues[h], k))
        self.pal = pal

    def draw(self, ctx, t, beat):
        speed = 1 + t * t / 300
        q = self.prm
        q[0] = int(t * 2)
        q[1] = int(t * speed * 4)
        fx.tunnel(ctx.fb, ctx.tunnel_tab, self.pal, q)
        if beat["snare"] > 0.6:
            flash_screen(ctx, (beat["snare"] - 0.6) * 1.2)
        if t > 48:
            flash_screen(ctx, (t - 48) / 16)


class Twister:
    """Twister bar + greetings scroller."""

    TEXT = ("GREETINGS FLY OUT TO ...  THE MICROHYDRA CREW  *  ALL CARDPUTER HACKERS  *  "
            "EVERY DEMOSCENER WHO EVER TYPED LOAD  *  AND YOU, FOR WATCHING!")

    def start(self, ctx):
        self.prm = array("i", [120, 46, 0, 0, 0])
        tabs = array("H", ctx.sin16)
        faces = ((255, 80, 200), (80, 200, 255), (255, 220, 60), (120, 255, 120))
        for f in faces:
            for s in range(16):
                tabs.append(ctx.c(scale(f, 0.2 + 0.85 * s / 15)))
        self.tabs = tabs
        self.copper = Copper(ctx, (6, 14, 6, 4), bg=(0, 0, 20))
        grad = gradient64(ctx, ((255, 255, 255), (255, 200, 0), (255, 60, 60), (255, 200, 0)))
        self.txt = BigText(ctx, self.TEXT, grad)

    def draw(self, ctx, t, beat):
        rowc = self.copper.build(t, amp=60, speed=0.1, spread=1.6, flash=beat["kick"] * 0.6)
        fx.fill_rows(ctx.fb, rowc, 0, _H)
        q = self.prm
        q[0] = 120 + int(50 * math.sin(t * 0.05))
        q[1] = 40 + int(8 * beat["kick"])
        q[2] = int(t * 6)
        q[3] = int(t * 4)
        q[4] = int(90 * math.sin(t * 0.03))
        fx.twister(ctx.fb, q, self.tabs)
        total = self.txt.width(0) + _W
        x = _W - int(t * total / 256)
        self.txt.draw(ctx, x, 92, amp=8, phase=int(t * 10), xs=3, sh=0, ys=1,
                      goff=int(t * 2), shadow=ctx.c((0, 0, 0)), y0=0, y1=_H)


class Roto:
    """Rotozoomer with a pulsing zoom (key change part)."""

    def start(self, ctx):
        self.prm = array("i", [0] * 6)
        tex = array("H", [0] * 4096)
        c1 = (60, 0, 120)
        c2 = (20, 0, 60)
        ring = ((255, 200, 0), (255, 100, 0))
        for y in range(64):
            for x in range(64):
                chk = ((x >> 3) ^ (y >> 3)) & 1
                col = c1 if chk else c2
                d = math.sqrt((x - 31.5) ** 2 + (y - 31.5) ** 2)
                if 16 < d < 26:
                    col = ring[0] if int(d) % 4 < 2 else ring[1]
                if d < 9:
                    k = 1 - d / 9
                    col = scale((80, 220, 255), 0.5 + 0.5 * k)
                tex[y * 64 + x] = ctx.c(col)
        self.tex = tex
        grad = gradient64(ctx, ((255, 255, 255), (80, 220, 255), (255, 255, 255), (255, 100, 220)))
        self.banner = BigText(ctx, "NEON HYDRA", grad)

    def draw(self, ctx, t, beat):
        a = t * 0.04
        z = 1.2 + 0.7 * math.sin(t * 0.025) - 0.25 * beat["kick"]
        ca = math.cos(a) * z * 1024
        sa = math.sin(a) * z * 1024
        q = self.prm
        cu = int(t * 40 * 1024 / 16)
        cv = int(t * 25 * 1024 / 16)
        q[0] = cu - int(120 * ca - 67 * sa)
        q[1] = cv - int(120 * sa + 67 * ca)
        q[2] = int(ca)
        q[3] = int(sa)
        q[4] = int(-sa)
        q[5] = int(ca)
        fx.roto(ctx.fb, self.tex, q)
        phase = t % 64
        if phase > 40:
            x = _W - int((phase - 40) * (self.banner.width(0) + _W) / 24)
            self.banner.draw(ctx, x, 50, amp=10, phase=int(t * 8), xs=3, sh=0, ys=1,
                             goff=int(t * 3), shadow=ctx.c((0, 0, 0)))


class Outro:
    """Fire + rolling credits, fade out."""

    LINES = ("NEON HYDRA", "", "code, music & gfx", "szuszjan + claude", "",
             "made for the", "M5Stack Cardputer", "running MicroHydra", "",
             "greetings to the", "MicroHydra community", "", "thanks for watching!")

    def start(self, ctx):
        self.fire = bytearray(120 * 70)
        self.fprm = array("i", [12345, 110, 4])
        pal = array("H", [0] * 256)
        for i in range(256):
            if i < 64:
                c = (i * 2, 0, i // 2)
            elif i < 128:
                c = (128 + (i - 64) * 2, (i - 64), 0)
            elif i < 192:
                c = (255, 64 + (i - 128) * 2, 0)
            else:
                c = (255, 192 + (i - 192), (i - 192) * 4)
            pal[i] = ctx.c(c)
        self.pal = pal

    def draw(self, ctx, t, beat):
        fb = ctx.fb
        fb.fill(ctx.c((0, 0, 0)))
        q = self.fprm
        q[1] = 110 + int(90 * beat["kick"]) if t < 104 else max(0, 110 - int((t - 104) * 8))
        fx.fire_step(self.fire, q)
        fx.fire_draw(fb, self.fire, self.pal, 0)
        y0 = _H - int(t * 1.6)
        for i, line in enumerate(self.LINES):
            y = y0 + i * 14
            if -16 < y < _H:
                font = ctx.MED if i == 0 else None
                text_center(ctx, line, y, (255, 255, 255) if i else (255, 230, 120), font)
        if t > 112:
            flash_screen(ctx, (t - 112) / 16, (0, 0, 0))


class TheEnd:
    def start(self, ctx):
        grad = gradient64(ctx, ((255, 0, 120), (255, 255, 255), (0, 200, 255), (255, 255, 255)))
        self.txt = BigText(ctx, "THE END", grad)
        self.copper = Copper(ctx, (2, 10, 7, 13, 3, 14, 4))

    def draw(self, ctx, t, beat):
        rowc = self.copper.build(t, amp=60, speed=0.2, spread=0.5)
        fx.fill_rows(ctx.fb, rowc, 0, _H)
        x = (_W - self.txt.width(1)) // 2
        self.txt.draw(ctx, x, 20, amp=8, phase=int(t * 8), xs=2, sh=1, ys=2, goff=int(t * 4),
                      shadow=ctx.c((0, 0, 0)))
        if int(t) % 8 < 6:
            text_center(ctx, "ESC = quit    looping...", 100, (255, 255, 255), None)


# section name -> part class
PARTS = {
    "intro": Intro, "theme A": Scroller, "theme B": Plasma, "break": Balls,
    "build": Tunnel, "theme A2": Twister, "theme C": Roto, "outro": Outro, "end": TheEnd,
}
