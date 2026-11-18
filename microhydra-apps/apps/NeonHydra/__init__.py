"""NEON HYDRA - an old school demo for MicroHydra (M5Stack Cardputer).

~3 minutes: raster bars, sine scrollers, plasma, vector balls, tunnel,
twister, rotozoomer, fire - with an original 4 channel chiptune soundtrack
synthesized live (see engine.py / song.py).

Keys:
  SPC              skip to the next part
  FN+; / FN+.      volume up / down   (or ; and .)
  f                show FPS
  ESC / G0         exit

Install: copy the whole NeonHydra folder into /apps (flash or SD card).
"""

import gc
import math
import random
import time
from array import array

import machine
from font import vga1_8x16 as MED
from font import vga2_16x32 as BIG
from lib import display, userinput
from lib.hydra import config

try:
    from . import engine, fx, parts, song
except ImportError:
    from apps.NeonHydra import engine, fx, parts, song


_W = const(240)
_H = const(135)
_ROW_MS = 1326 * 1000 / 11025

DISPLAY = display.Display()
CONFIG = config.Config()
INPUT = userinput.UserInput()


# ---------------------------------------------------------------- context
def rgb565(rgb):
    return ((rgb[0] & 0xF8) << 8) | ((rgb[1] & 0xFC) << 3) | (rgb[2] >> 3)


class Ctx:
    pass


ctx = Ctx()
ctx.D = DISPLAY
ctx.fb = DISPLAY.fbuf
ctx.swap = bool(getattr(DISPLAY, "needs_swap", True))
ctx.MED = MED
ctx.BIG = BIG
ctx.rgb565 = rgb565
if ctx.swap:
    ctx.c = lambda rgb: ((rgb565(rgb) & 255) << 8) | (rgb565(rgb) >> 8)
else:
    ctx.c = rgb565
ctx.sin16 = [int(127.5 + 127.5 * math.sin(i * 6.2832 / 256)) for i in range(256)]
ctx.sint = bytearray(ctx.sin16)
ctx.blend_prm = array("i", [0] * 5)
ctx.tunnel_tab = bytearray(3 * 8160)


def tunnel_rows(y0, y1):
    tab = ctx.tunnel_tab
    sqrt = math.sqrt
    atan2 = math.atan2
    for by in range(y0, y1):
        dy = by - 33.5
        for bx in range(120):
            dx = bx - 59.5
            r = sqrt(dx * dx + dy * dy) + 0.01
            i = by * 120 + bx
            tab[i] = int(atan2(dy, dx) * 81.487) & 255  # 2 texture repeats around
            tab[i + 8160] = int(900 / r) & 255
            sh = int(r / 4.2)
            tab[i + 16320] = 15 if sh > 15 else sh


class SilentClock:
    """Fallback timeline if audio can't start."""

    def __init__(self, loop_bars):
        self.loop_rows = loop_bars * 16
        self.t0 = time.ticks_ms()
        self.hits = []

    def start(self):
        self.t0 = time.ticks_ms()

    def heard(self):
        return 0

    def rows(self):
        return (time.ticks_diff(time.ticks_ms(), self.t0) / _ROW_MS) % self.loop_rows

    def seek_bar(self, bar):
        self.t0 = time.ticks_add(time.ticks_ms(), -int(bar * 16 * _ROW_MS))


def show():
    DISPLAY._set_show_y(0, _H)
    DISPLAY.show()


def check_exit(keys):
    if "ESC" in keys or "G0" in keys:
        machine.reset()


# ---------------------------------------------------------------- loader
def loader(clock):
    """Retro 'tape loading' screen; does the real precomputation meanwhile."""
    steps = []
    store = {}

    def make_waves():
        store["waves"] = engine.make_waves()

    def make_drums():
        store["drums"] = engine.make_drums()

    steps.append(make_waves)
    steps.append(make_drums)
    for y in range(0, 68, 6):
        steps.append(lambda y=y: tunnel_rows(y, min(68, y + 6)))
    total = len(steps)

    green = rgb565((120, 255, 120))
    black = ctx.c((0, 0, 0))
    stripe_cols = [ctx.c(c) for c in parts.C64]
    rowc = array("H", [0] * _H)
    cmd = 'LOAD"NEON HYDRA",8,1'
    t0 = time.ticks_ms()
    done_at = None
    while True:
        check_exit(INPUT.get_new_keys())
        t = time.ticks_diff(time.ticks_ms(), t0)
        lines = ["MICROHYDRA SYSTEM", "", "READY."]
        typed = cmd[:max(0, (t - 800) // 70)]
        lines.append(typed)
        loading = t > 3400
        if t > 2600:
            lines += ["", "SEARCHING FOR NEON HYDRA"]
        if loading:
            lines.append("LOADING")
            if steps:
                steps.pop(0)()
            elif done_at is None:
                done_at = t
        if done_at is not None and t > max(done_at, 6500):
            lines += ["READY.", "RUN"[:max(0, (t - max(done_at, 6500)) // 150)]]
        if done_at is not None and t > max(done_at, 6500) + 900:
            break

        if loading and (steps or t < 6200):
            # tape loader stripes in the border
            y = 0
            while y < _H:
                h = 2 + random.getrandbits(3)
                col = stripe_cols[random.getrandbits(4)]
                for yy in range(y, min(_H, y + h)):
                    rowc[yy] = col
                y += h
            fx.fill_rows(ctx.fb, rowc, 0, _H)
            ctx.fb.fill_rect(12, 10, _W - 24, _H - 20, black)
        else:
            ctx.fb.fill(black)
        for i, line in enumerate(lines):
            DISPLAY.text(line, 18, 14 + i * 11, green)
        if loading and (steps or t < 6200):
            done = total - len(steps)
            ctx.fb.rect(18, _H - 22, _W - 36, 8, ctx.c((120, 255, 120)))
            ctx.fb.fill_rect(20, _H - 20, (_W - 40) * done // total, 4, ctx.c((120, 255, 120)))
        elif (t // 400) % 2 and len(lines) < 10:
            # blinking cursor
            ctx.fb.fill_rect(18 + 8 * len(lines[-1]), 14 + (len(lines) - 1) * 11, 8, 8,
                             ctx.c((120, 255, 120)))
        show()
        time.sleep_ms(5)
    return store["waves"], store["drums"]


# ---------------------------------------------------------------- main
def main():
    # section table for the visual timeline
    sec_names = [s["name"] for s in song.SECTIONS] + ["end"]
    starts = []
    b = 0
    for s in song.SECTIONS:
        starts.append(b)
        b += s["bars"]
    starts.append(b)  # tail ("end")
    loop_bars = b + song.TAIL_BARS

    try:
        clock = engine.Engine(song=song, config=CONFIG, waves=None, drums=None)
    except Exception as e:  # noqa: BLE001
        print("audio failed:", e)
        clock = SilentClock(loop_bars)

    waves, drums = loader(clock)
    if isinstance(clock, engine.Engine):
        clock.waves = waves
        clock.drums = drums
    del waves, drums
    gc.collect()
    clock.start()

    current = -1
    part = None
    show_fps = False
    osd_until = 0
    frames = 0
    fps = 0
    fps_t = time.ticks_ms()

    while True:
        keys = INPUT.get_new_keys()
        check_exit(keys)
        rows = clock.rows()
        if rows < 0:
            rows = 0
        bar = int(rows // 16)
        si = len(starts) - 1
        for i in range(len(starts) - 1):
            if starts[i] <= bar < starts[i + 1]:
                si = i
                break

        if "SPC" in keys:
            nxt = starts[si + 1] if si + 1 < len(starts) else 0
            if si >= len(starts) - 1:
                nxt = 0
            clock.seek_bar(nxt)
        if "UP" in keys or ";" in keys or "DOWN" in keys or "." in keys:
            v = CONFIG["volume"] + (1 if ("UP" in keys or ";" in keys) else -1)
            CONFIG["volume"] = max(0, min(10, v))
            osd_until = time.ticks_add(time.ticks_ms(), 1200)
        if "f" in keys:
            show_fps = not show_fps

        if si != current:
            current = si
            part = None
            gc.collect()
            part = parts.PARTS[sec_names[si]]()
            part.start(ctx)
            gc.collect()

        # beat detection from the sequencer's drum hits
        kick = 0.0
        snare = 0.0
        heard = clock.heard()
        for at, d in reversed(list(clock.hits)):
            age = heard - at
            if age < 0:
                continue
            if kick == 0.0 and d in "kc":
                kick = max(0.0001, 1 - age / 2800)
            if snare == 0.0 and d == "s":
                snare = max(0.0001, 1 - age / 2800)
            if kick and snare:
                break
        beat = {"kick": kick if kick > 0.001 else 0.0, "snare": snare if snare > 0.001 else 0.0}

        part.draw(ctx, rows - starts[si] * 16, beat)

        now = time.ticks_ms()
        if time.ticks_diff(osd_until, now) > 0:
            v = CONFIG["volume"]
            ctx.fb.fill_rect(70, 58, 100, 18, ctx.c((0, 0, 0)))
            ctx.fb.rect(70, 58, 100, 18, ctx.c((255, 255, 255)))
            DISPLAY.text("VOL %d" % v, 78, 63, 0xFFFF)
            ctx.fb.fill_rect(124, 63, v * 4, 8, ctx.c((120, 255, 120)))
        frames += 1
        if time.ticks_diff(now, fps_t) >= 1000:
            fps = frames
            frames = 0
            fps_t = now
        if show_fps:
            ctx.fb.fill_rect(0, 0, 56, 10, ctx.c((0, 0, 0)))
            DISPLAY.text("%d fps" % fps, 1, 1, 0xFFE0)
        show()


main()
