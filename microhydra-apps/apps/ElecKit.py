"""ElecKit - pocket electronics calculator for MicroHydra (Cardputer).

Three tools, switched with TAB:
  1. RES   - 4-band resistor color code
  2. OHM   - Ohm's law / power (fill any two of V, I, R, P)
  3. LED   - series resistor for an LED (+ nearest E12 / E24 value)

Keys:
  TAB                 next tool
  RES: , /  (LEFT/RIGHT)  pick band     ; .  (UP/DOWN)  change color
  OHM / LED:
    ; or FN+;  / FN+.    previous / next field
    ENT                 next field (calculates when possible)
    0-9 . k m u M       number with optional SI suffix (4k7 also works)
    BSPC                delete,   c   clear all fields
  ESC (FN + `) / G0    exit
"""

import time

import machine
from font import vga1_8x16 as MED
from lib import display, userinput
from lib.hydra import beeper, config


_W = const(240)
_H = const(135)

DISPLAY = display.Display()
CONFIG = config.Config()
INPUT = userinput.UserInput()
BEEP = beeper.Beeper()

BG = CONFIG.palette[2]
BG_DARK = CONFIG.palette[1]
MID = CONFIG.palette[5]
FG = CONFIG.palette[8]
WHITE = CONFIG.palette[10]
_ERR = const(0xF800)

# name, RGB565 color, digit, multiplier exponent, tolerance text
BANDS = (
    ("black", 0x0000, 0, 0, None),
    ("brown", 0x8A22, 1, 1, "1%"),
    ("red", 0xF800, 2, 2, "2%"),
    ("orange", 0xFC00, 3, 3, None),
    ("yellow", 0xFFE0, 4, 4, None),
    ("green", 0x07E0, 5, 5, "0.5%"),
    ("blue", 0x001F, 6, 6, "0.25%"),
    ("violet", 0x901A, 7, None, "0.1%"),
    ("grey", 0x8410, 8, None, None),
    ("white", 0xFFFF, 9, None, None),
    ("gold", 0xD5A0, None, -1, "5%"),
    ("silver", 0xC618, None, -2, "10%"),
)

E12 = (1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2)
E24 = (1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
       3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1)

SUFFIX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6}
INPUT_CHARS = "0123456789.pnumkKM"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ helpers ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def fmt_si(value, unit):
    """Format a number with an SI prefix, e.g. 4700 -> '4.7k'."""
    if value is None:
        return "-"
    if len(unit) > 1:
        unit = " " + unit
    if value == 0:
        return "0" + unit
    for mult, pre in ((1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "u"), (1e-9, "n")):
        if abs(value) >= mult * 0.9995:
            v = value / mult
            break
    else:
        v, pre = value / 1e-12, "p"
    if abs(v) >= 100:
        s = "%d" % round(v)
    elif abs(v) >= 10:
        s = "%.1f" % v
    else:
        s = "%.2f" % v
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s + pre + unit


def parse_si(text):
    """Parse '4.7k', '4k7', '20m', '330' -> float. Return None if invalid."""
    if not text:
        return None
    for suf, mult in SUFFIX.items():
        if suf in text:
            left, _, right = text.partition(suf)
            if right and "." not in left and right.isdigit():
                text = left + "." + right  # 4k7 style
            else:
                text = left + right
            try:
                return float(text or "1") * mult
            except ValueError:
                return None
    try:
        return float(text)
    except ValueError:
        return None


def nearest_series(value, series, prefer_up=False):
    """Return the nearest standard value (or the next one up if prefer_up)."""
    if value <= 0:
        return None
    exp = 0
    v = value
    while v >= 10:
        v /= 10
        exp += 1
    while v < 1:
        v *= 10
        exp -= 1
    candidates = [s * 10 ** exp for s in series] + [10 * 10 ** exp]
    if prefer_up:
        for c in candidates:
            if c >= value * 0.9999:
                return c
    return min(candidates, key=lambda c: abs(c - value))


def center_text(text, y, color, font=None):
    width = DISPLAY.get_total_width(text, font)
    DISPLAY.text(text, (_W - width) // 2, y, color, font)


def header(title, idx):
    DISPLAY.rect(0, 0, _W, 14, BG_DARK, fill=True)
    DISPLAY.text("ElecKit", 4, 3, FG)
    x = _W - 3 * 34
    for i, name in enumerate(("RES", "OHM", "LED")):
        c = FG if i == idx else MID
        if i == idx:
            DISPLAY.rect(x - 2, 1, 30, 12, FG, fill=True)
            c = BG
        DISPLAY.text(name, x + 2, 3, c)
        x += 34


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ tool: resistor colors ~~~~~~~~~~~~~~~~~~~~
class ResistorTool:
    # allowed band indexes for each of the 4 bands
    ALLOWED = (
        tuple(range(1, 10)),            # 1st digit (no black)
        tuple(range(0, 10)),            # 2nd digit
        (0, 1, 2, 3, 4, 5, 6, 10, 11),  # multiplier
        (1, 2, 5, 6, 7, 10, 11),        # tolerance
    )

    def __init__(self):
        self.bands = [4, 7, 2, 10]  # yellow violet red gold = 4.7k 5%
        self.sel = 0

    def value(self):
        d1 = BANDS[self.bands[0]][2]
        d2 = BANDS[self.bands[1]][2]
        mul = BANDS[self.bands[2]][3]
        return (d1 * 10 + d2) * (10 ** mul)

    def handle(self, keys):
        for k in keys:
            if k in ("LEFT", ","):
                self.sel = (self.sel - 1) % 4
            elif k in ("RIGHT", "/"):
                self.sel = (self.sel + 1) % 4
            elif k in ("UP", ";", "DOWN", "."):
                allowed = self.ALLOWED[self.sel]
                pos = allowed.index(self.bands[self.sel]) if self.bands[self.sel] in allowed else 0
                step = -1 if k in ("UP", ";") else 1
                self.bands[self.sel] = allowed[(pos + step) % len(allowed)]

    def draw(self):
        # leads + body
        DISPLAY.hline(10, 50, 220, MID)
        DISPLAY.hline(10, 51, 220, MID)
        DISPLAY.rect(50, 32, 140, 38, 0xD69A, fill=True)  # beige body
        DISPLAY.rect(50, 32, 140, 38, MID)
        xs = (70, 92, 114, 160)
        for i, x in enumerate(xs):
            DISPLAY.rect(x, 32, 12, 38, BANDS[self.bands[i]][1], fill=True)
            if i == self.sel:
                DISPLAY.rect(x - 3, 28, 18, 46, WHITE)
                DISPLAY.rect(x - 2, 29, 16, 44, FG)
        # selected band name
        names = ("digit 1", "digit 2", "multiplier", "tolerance")
        center_text("%s: %s" % (names[self.sel], BANDS[self.bands[self.sel]][0]), 80, MID)
        tol = BANDS[self.bands[3]][4]
        center_text("%s  +/-%s" % (fmt_si(self.value(), "ohm"), tol), 98, WHITE, MED)
        e = "E12" if self._in_series(E12) else ("E24" if self._in_series(E24) else "")
        if e:
            center_text("standard %s value" % e, 120, MID)

    def _in_series(self, series):
        v = self.value()
        n = nearest_series(v, series)
        return n is not None and abs(n - v) < v * 1e-6


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ tool: generic form ~~~~~~~~~~~~~~~~~~~~~~~
class FormTool:
    """A list of numeric fields; subclasses implement compute()."""

    FIELDS = ()  # (key, label, unit)

    def __init__(self):
        self.text = {f[0]: "" for f in self.FIELDS}
        self.result = {}
        self.sel = 0
        self.msg = ""

    def handle(self, keys):
        key = self.FIELDS[self.sel][0]
        for k in keys:
            if k in ("UP", ";"):
                self.sel = (self.sel - 1) % len(self.FIELDS)
            elif k in ("DOWN", "ENT"):
                self.sel = (self.sel + 1) % len(self.FIELDS)
                self.recalc()
            elif k in ("BSPC", "DEL"):
                self.text[key] = self.text[key][:-1]
                self.recalc()
            elif k == "c":
                for f in self.text:
                    self.text[f] = ""
                self.recalc()
            elif len(k) == 1 and k in INPUT_CHARS and len(self.text[key]) < 10:
                self.text[key] += k
                self.recalc()
            key = self.FIELDS[self.sel][0]

    def recalc(self):
        vals = {f[0]: parse_si(self.text[f[0]]) for f in self.FIELDS}
        self.msg = ""
        try:
            self.result = self.compute(vals) or {}
        except (ZeroDivisionError, ValueError):
            self.result = {}
            self.msg = "invalid values"

    def compute(self, vals):  # noqa: ARG002
        return {}

    def draw(self):
        y = 20
        for i, (key, label, unit) in enumerate(self.FIELDS):
            selected = i == self.sel
            if selected:
                DISPLAY.rect(2, y - 2, _W - 4, 18, BG_DARK, fill=True)
                DISPLAY.rect(2, y - 2, _W - 4, 18, FG)
            DISPLAY.text(label, 8, y + 2, FG if selected else MID)
            if self.text[key]:
                shown = self.text[key] + ("_" if selected else "")
                DISPLAY.text(shown + " " + unit, 96, y, WHITE, MED)
            elif key in self.result:
                DISPLAY.text(fmt_si(self.result[key], unit), 96, y, FG, MED)
            elif selected:
                DISPLAY.text("_", 96, y, WHITE, MED)
            y += 20
        self.draw_extra(y)
        if self.msg:
            DISPLAY.text(self.msg, 8, _H - 10, _ERR)

    def draw_extra(self, y):
        pass


class OhmTool(FormTool):
    FIELDS = (
        ("V", "voltage U", "V"),
        ("I", "current I", "A"),
        ("R", "resist. R", "ohm"),
        ("P", "power P", "W"),
    )

    def compute(self, v):
        known = [k for k in "VIRP" if v[k] is not None]
        if len(known) < 2:
            return {}
        if len(known) > 2:
            self.msg = "fill only 2 fields (c=clear)"
            return {}
        V, I, R, P = v["V"], v["I"], v["R"], v["P"]
        if V is not None and I is not None:
            R, P = V / I, V * I
        elif V is not None and R is not None:
            I = V / R
            P = V * I
        elif V is not None and P is not None:
            I = P / V
            R = V / I
        elif I is not None and R is not None:
            V = I * R
            P = V * I
        elif I is not None and P is not None:
            V = P / I
            R = V / I
        else:  # R and P
            I = (P / R) ** 0.5
            V = I * R
        return {"V": V, "I": I, "R": R, "P": P}

    def draw_extra(self, y):
        DISPLAY.text("fill any 2 fields   c=clear", 8, y + 4, MID)


class LedTool(FormTool):
    FIELDS = (
        ("S", "supply", "V"),
        ("F", "LED Vf", "V"),
        ("I", "LED I", "A"),
    )

    def __init__(self):
        super().__init__()
        self.text = {"S": "5", "F": "2", "I": "20m"}
        self.recalc()

    def compute(self, v):
        if None in (v["S"], v["F"], v["I"]):
            return {}
        if v["S"] <= v["F"]:
            raise ValueError
        r = (v["S"] - v["F"]) / v["I"]
        return {"R": r, "P": (v["S"] - v["F"]) * v["I"]}

    def draw_extra(self, y):
        r = self.result.get("R")
        if r is None:
            DISPLAY.text("Vf: red 2, green/blue/white 3", 8, y + 4, MID)
            return
        e12 = nearest_series(r, E12, prefer_up=True)
        e24 = nearest_series(r, E24, prefer_up=True)
        DISPLAY.text("R = " + fmt_si(r, "ohm"), 8, y + 2, WHITE, MED)
        DISPLAY.text("use E12 %s / E24 %s" % (fmt_si(e12, ""), fmt_si(e24, "")), 8, y + 22, FG)
        DISPLAY.text("resistor power: " + fmt_si(self.result["P"], "W"), 8, y + 34, MID)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ main loop ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main():
    tools = [ResistorTool(), OhmTool(), LedTool()]
    current = 0
    redraw = True
    while True:
        keys = INPUT.get_new_keys()
        if "ESC" in keys or "G0" in keys:
            machine.reset()
            return
        if "TAB" in keys:
            current = (current + 1) % len(tools)
            BEEP.play("C5", 30)
            keys = [k for k in keys if k != "TAB"]
            redraw = True
        if keys:
            tools[current].handle(keys)
            redraw = True

        if redraw:
            redraw = False
            DISPLAY.fill(BG)
            header("", current)
            tools[current].draw()
            DISPLAY.show()
        time.sleep_ms(15)


main()
