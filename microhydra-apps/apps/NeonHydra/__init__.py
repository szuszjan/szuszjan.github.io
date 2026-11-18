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
import os
import sys

# ---------------------------------------------------------------- debug log
# Written to the SD card (readable on a phone) or to flash: free memory at every step
# and the full error if something fails.
try:
    _LOG = "/sd/neonhydra_log.txt" if "sd" in os.listdir("/") else "/neonhydra_log.txt"
    with open(_LOG, "w") as _f:
        _f.write("NEON HYDRA debug log\n")
except Exception:  # noqa: BLE001
    _LOG = None


def dbg(msg, err=None):
    if _LOG is None:
        return
    try:
        gc.collect()
        with open(_LOG, "a") as f:
            f.write("%s | free %d B\n" % (msg, gc.mem_free()))
            if err is not None:
                sys.print_exception(err, f)
    except Exception:  # noqa: BLE001
        pass


dbg("start")
import math
import random
import time
from array import array

import machine
from font import vga2_16x32 as BIG
from lib import display, userinput
from lib.hydra import config

dbg("libs imported")
try:
    from . import song
    dbg("song imported")
    from . import engine
    dbg("engine imported")
    from . import fx
    dbg("fx imported")
    from . import parts
    dbg("parts imported")
except ImportError:
    from apps.NeonHydra import engine, fx, parts, song


_W = const(240)
_H = const(135)
_ROW_MS = 1326 * 1000 / 11025

DISPLAY = display.Display()
CONFIG = config.Config()
INPUT = userinput.UserInput()
dbg("display created")


# ---------------------------------------------------------------- context
def rgb565(rgb):
    return ((rgb[0] & 0xF8) << 8) | ((rgb[1] & 0xFC) << 3) | (rgb[2] >> 3)


class Ctx:
    pass


ctx = Ctx()
ctx.D = DISPLAY
ctx.fb = DISPLAY.fbuf
ctx.swap = bool(getattr(DISPLAY, "needs_swap", True))
ctx.BIG = BIG
ctx.rgb565 = rgb565
if ctx.swap:
    ctx.c = lambda rgb: ((rgb565(rgb) & 255) << 8) | (rgb565(rgb) >> 8)
else:
    ctx.c = rgb565
ctx.sin16 = [int(127.5 + 127.5 * math.sin(i * 6.2832 / 256)) for i in range(256)]
ctx.sint = bytearray(ctx.sin16)
ctx.blend_prm = array("i", [0] * 5)
ctx.tunnel_tab = None  # allocated only for the break/build parts (see parts.tunnel_prepare)
ctx.tunnel_done = 0


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


class ErrorPart:
    """Shown instead of a part that failed (e.g. out of memory), so the demo keeps going."""

    def __init__(self, name, err):
        self.msg = "%s: %s" % (name, repr(err)[:40])
        print("part failed:", self.msg)

    def start(self, ctx):
        pass

    def draw(self, ctx, t, beat):
        ctx.fb.fill(ctx.c((0, 0, 0)))
        DISPLAY.text("part failed:", 4, 50, 0xF800)
        DISPLAY.text(self.msg[:29], 4, 62, 0xFFFF)
        DISPLAY.text(self.msg[29:58], 4, 72, 0xFFFF)
        DISPLAY.text("%dK free  SPC = next part" % (gc.mem_free() // 1024), 4, 90, 0x07E0)


def show():
    DISPLAY._set_show_y(0, _H)
    DISPLAY.show()


def check_exit(keys):
    if "ESC" in keys or "G0" in keys:
        machine.reset()


# ---------------------------------------------------------------- loader
def loader(clock):
    """Retro 'tape loading' screen; does the real precomputation meanwhile."""
    store = {"drums": {}}
    errors = []

    def make_waves():
        store["waves"] = engine.make_waves()

    steps = [("waves", make_waves)]
    for key in engine.DRUMS:
        steps.append(("drum " + key, lambda key=key: engine.make_drum(key, store["drums"])))
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
                name, fn = steps.pop(0)
                try:
                    gc.collect()
                    fn()
                    dbg("loader: " + name)
                except Exception as e:  # noqa: BLE001
                    # don't crash: show the problem, continue without that part
                    dbg("loader FAILED: " + name, e)
                    errors.append("%s: %s" % (name, repr(e)[:22]))
                gc.collect()
            elif done_at is None:
                done_at = t
        if done_at is not None and t > max(done_at, 6500):
            lines += ["READY.", "RUN"[:max(0, (t - max(done_at, 6500)) // 150)]]
        if done_at is not None and t > max(done_at, 6500) + (900 if not errors else 5000):
            break
        lines += ["ERR " + e for e in errors]

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
            DISPLAY.text(line, 18, 14 + i * 11, green if not line.startswith("ERR") else 0xF800)
        DISPLAY.text("%dK free" % (gc.mem_free() // 1024), _W - 96, 36, rgb565((60, 160, 60)))
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
    return store.get("waves"), store["drums"]


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
        dbg("audio engine started")
    except Exception as e:  # noqa: BLE001
        dbg("audio engine FAILED", e)
        clock = SilentClock(loop_bars)

    waves, drums = loader(clock)
    if isinstance(clock, engine.Engine):
        if waves is None:
            clock.playing = False
            clock = SilentClock(loop_bars)
        else:
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
            name = sec_names[si]
            part = None
            if name not in ("break", "build"):
                ctx.tunnel_tab = None  # free 24K when the tunnel isn't coming up
            gc.collect()
            try:
                part = parts.PARTS[name]()
                part.start(ctx)
                dbg("part: " + name)
            except Exception as e:  # noqa: BLE001
                dbg("part FAILED: " + name, e)
                part = ErrorPart(name, e)
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

        try:
            part.draw(ctx, rows - starts[si] * 16, beat)
        except Exception as e:  # noqa: BLE001
            dbg("draw FAILED: " + sec_names[si], e)
            part = ErrorPart(sec_names[si], e)
            part.draw(ctx, 0, beat)

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
            ctx.fb.fill_rect(0, 0, 128, 10, ctx.c((0, 0, 0)))
            DISPLAY.text("%d fps %dK" % (fps, gc.mem_free() // 1024), 1, 1, 0xFFE0)
        show()


try:
    main()
except Exception as _e:  # noqa: BLE001
    dbg("FATAL", _e)
    raise
