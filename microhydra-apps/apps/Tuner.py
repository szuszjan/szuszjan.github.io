"""Tuner - chromatic / instrument tuner for MicroHydra (Cardputer).

Uses the built-in PDM microphone (SPM1423) and the YIN pitch detection
algorithm (heavy parts written in viper).

Modes (TAB): Chromatic, Guitar, Bass, Ukulele, Violin.
In instrument modes the nearest string is selected automatically.

Keys:
  TAB          next mode
  ; .          reference A4 +1 / -1 Hz    (r = reset to 440 Hz)
  SPC          hold / release the reading
  ESC / G0     exit

Tip: hold the Cardputer close to the instrument (or the sound hole),
the microphone is small. Bass low E (41 Hz) is hard for the mic: use
harmonics or the 12th fret if it doesn't catch it.
"""

import math
import time
from array import array

import machine
from machine import I2S, Pin
from font import vga2_16x32 as BIG
from lib import display, userinput
from lib.hydra import config


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ hardware / dsp config ~~~~~~~~~~~~~~~~~~~
_MIC_CLK = const(43)   # shared with the speaker WS pin, so no sound while tuning
_MIC_DATA = const(46)
_RATE = const(16000)
_WIN = const(1024)      # YIN integration window
_TMAX_MAX = const(420)  # longest lag (16000/420 = 38 Hz, for bass)
_TMIN = const(8)        # shortest lag (~1.7 kHz usable top)
_GATE = const(120)      # minimum signal peak to try detection
_THRESH = 0.15          # YIN threshold

_W = const(240)
_H = const(135)
_GREEN = const(0x07E0)
_YELLOW = const(0xFFE0)
_RED = const(0xF800)

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# name, MIDI notes of the strings (None = chromatic), longest lag needed
MODES = (
    ("Chromatic", None, 240),
    ("Guitar", (40, 45, 50, 55, 59, 64), 240),   # E2 A2 D3 G3 B3 E4
    ("Bass", (28, 33, 38, 43), _TMAX_MAX),        # E1 A1 D2 G2
    ("Ukulele", (67, 60, 64, 69), 120),           # G4 C4 E4 A4
    ("Violin", (55, 62, 69, 76), 240),            # G3 D4 A4 E5
)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ objects ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DISPLAY = display.Display()
CONFIG = config.Config()
INPUT = userinput.UserInput()

BG = CONFIG.palette[2]
BG_DARK = CONFIG.palette[1]
GRID = CONFIG.palette[4]
MID = CONFIG.palette[5]
FG = CONFIG.palette[8]
WHITE = CONFIG.palette[10]

RAW = bytearray(2 * (_WIN + _TMAX_MAX))
X = array("i", [0] * (_WIN + _TMAX_MAX))
D = array("i", [0] * (_TMAX_MAX + 2))
CM = array("f", [1.0] * (_TMAX_MAX + 2))
PARAMS = array("i", [0] * 4)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ viper dsp ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
@micropython.viper
def _to_int(raw, x, n: int) -> int:
    """Convert little endian int16 samples to int32 array, return their sum."""
    p = ptr16(raw)
    o = ptr32(x)
    s = 0
    i = 0
    while i < n:
        v = int(p[i])
        if v & 0x8000:
            v -= 0x10000
        o[i] = v
        s += v
        i += 1
    return s


@micropython.viper
def _remove_dc(x, n: int, mean: int) -> int:
    """Subtract mean, return peak absolute value."""
    o = ptr32(x)
    peak = 0
    i = 0
    while i < n:
        v = o[i] - mean
        o[i] = v
        if v < 0:
            v = 0 - v
        if v > peak:
            peak = v
        i += 1
    return peak


@micropython.viper
def _scale(x, n: int, mul: int):
    """x = x * mul / 256 (keeps the YIN sums inside 32 bits)."""
    o = ptr32(x)
    i = 0
    while i < n:
        o[i] = (o[i] * mul) >> 8
        i += 1


@micropython.viper
def _yin_diff(x, d, params):
    """d[tau] = sum((x[i] - x[i + tau])^2), tau = 1..tmax. params: win, tmax."""
    px = ptr32(x)
    pd = ptr32(d)
    prm = ptr32(params)
    win = prm[0]
    tmax = prm[1]
    pd[0] = 0
    tau = 1
    while tau <= tmax:
        s = 0
        i = 0
        while i < win:
            v = px[i] - px[i + tau]
            s += v * v
            i += 1
        pd[tau] = s
        tau += 1


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ pitch detection ~~~~~~~~~~~~~~~~~~~~~~~~~
def detect(mic, tmax):
    """Read the mic and return (frequency or None, peak level)."""
    n = _WIN + tmax
    mv = memoryview(RAW)[:2 * n]
    mic.readinto(mv)
    total = _to_int(RAW, X, n)
    peak = _remove_dc(X, n, total // n)
    if peak < _GATE:
        return None, peak
    _scale(X, n, (200 << 8) // peak)

    PARAMS[0] = _WIN
    PARAMS[1] = tmax
    _yin_diff(X, D, PARAMS)

    # cumulative mean normalized difference
    cum = 0
    for tau in range(1, tmax + 1):
        cum += D[tau]
        CM[tau] = D[tau] * tau / cum if cum else 1.0

    best = -1
    tau = _TMIN
    while tau < tmax:
        if CM[tau] < _THRESH:
            while tau + 1 < tmax and CM[tau + 1] < CM[tau]:
                tau += 1
            best = tau
            break
        tau += 1
    if best < 0:
        m = _TMIN
        for t in range(_TMIN, tmax):
            if CM[t] < CM[m]:
                m = t
        if CM[m] < 0.3:
            best = m
    if best < 0:
        return None, peak

    # parabolic interpolation of the raw difference around the minimum
    shift = 0.0
    if _TMIN < best < tmax:
        a, b, c = D[best - 1], D[best], D[best + 1]
        den = a - 2 * b + c
        if den:
            shift = 0.5 * (a - c) / den
    return _RATE / (best + shift), peak


def note_name(midi):
    return NOTE_NAMES[midi % 12] + str(midi // 12 - 1)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ drawing ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def center_text(text, y, color, font=None):
    width = DISPLAY.get_total_width(text, font)
    DISPLAY.text(text, (_W - width) // 2, y, color, font)


def cents_color(c):
    a = abs(c)
    if a <= 5:
        return _GREEN
    if a <= 15:
        return _YELLOW
    return _RED


def draw_meter(y, cents, active):
    """Horizontal -50..+50 cent scale with a needle."""
    x0, x1 = 20, 220
    mid = (x0 + x1) // 2
    DISPLAY.rect(mid - 10, y, 21, 18, 0x0320, fill=True)  # +-5 cent zone
    for c in range(-50, 51, 10):
        x = mid + c * 2
        h = 8 if c % 50 == 0 else (6 if c == 0 else 4)
        DISPLAY.vline(x, y + 18 - h, h, MID)
    DISPLAY.hline(x0, y + 18, x1 - x0 + 1, MID)
    DISPLAY.text("-50", x0 - 12, y + 22, MID)
    DISPLAY.text("+50", x1 - 12, y + 22, MID)
    DISPLAY.text("0", mid - 4, y + 22, MID)
    if active:
        c = max(-50, min(50, cents))
        x = int(mid + c * 2)
        col = cents_color(cents)
        DISPLAY.rect(x - 1, y - 4, 3, 24, col, fill=True)
        DISPLAY.rect(x - 4, y - 6, 9, 3, col, fill=True)


def draw_history(y, hist, h=22):
    DISPLAY.hline(0, y + h // 2, _W, GRID)
    x = _W - 2 * len(hist)
    for c in hist:
        if c is not None:
            cy = y + h // 2 - int(max(-50, min(50, c)) * (h // 2) / 50)
            DISPLAY.rect(x, cy, 2, 2, cents_color(c), fill=True)
        x += 2


def draw_strings(y, strings, target):
    count = len(strings)
    box = _W // count
    for i, m in enumerate(strings):
        name = note_name(m)
        x = i * box
        if m == target:
            DISPLAY.rect(x + 2, y, box - 4, 20, FG, fill=True)
            col = BG
        else:
            DISPLAY.rect(x + 2, y, box - 4, 20, MID)
            col = FG
        DISPLAY.text(name, x + (box - 8 * len(name)) // 2, y + 6, col)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ main ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def open_mic():
    mic = I2S(
        0,
        sck=Pin(_MIC_CLK),
        sd=Pin(_MIC_DATA),
        mode=I2S.PDM_RX,
        bits=16,
        format=I2S.MONO,
        rate=_RATE,
        ibuf=4096,
    )
    # throw away the first (settling) samples
    for _ in range(3):
        mic.readinto(RAW)
    return mic


def error_screen(text):
    DISPLAY.fill(BG)
    center_text("Tuner", 10, FG, BIG)
    center_text("microphone error:", 56, _RED)
    center_text(text[:29], 70, WHITE)
    center_text("ESC = exit", 118, MID)
    DISPLAY.show()
    while True:
        keys = INPUT.get_new_keys()
        if "ESC" in keys or "G0" in keys:
            machine.reset()
        time.sleep_ms(30)


def main():
    try:
        mic = open_mic()
    except Exception as e:  # noqa: BLE001
        error_screen(str(e) or type(e).__name__)
        return

    mode = 0
    a4 = 440
    hold = False
    recent = []      # last raw frequency readings
    hist = []        # cents history for the graph
    shown = None     # (midi target, cents, freq) currently displayed
    needle = 0.0
    last_good = 0

    while True:
        keys = INPUT.get_new_keys()
        if "ESC" in keys or "G0" in keys:
            mic.deinit()
            machine.reset()
            return
        if "TAB" in keys:
            mode = (mode + 1) % len(MODES)
            recent = []
        if "UP" in keys or ";" in keys:
            a4 = min(466, a4 + 1)
        if "DOWN" in keys or "." in keys:
            a4 = max(415, a4 - 1)
        if "r" in keys:
            a4 = 440
        if "SPC" in keys:
            hold = not hold

        name, strings, tmax = MODES[mode]
        freq, level = detect(mic, tmax)
        now = time.ticks_ms()

        if not hold:
            if freq:
                midi_f = 69 + 12 * math.log(freq / a4) / math.log(2)
                # a jump of more than a semitone = a new note, restart smoothing
                if recent and abs(midi_f - recent[-1]) > 1:
                    recent = []
                recent.append(midi_f)
                if len(recent) > 5:
                    recent.pop(0)
                med = sorted(recent)[len(recent) // 2]
                if strings:
                    target = min(strings, key=lambda s: abs(s - med))
                else:
                    target = round(med)
                cents = (med - target) * 100
                if shown is None or shown[0] != target:
                    needle = cents
                needle = needle * 0.5 + cents * 0.5
                shown = (target, needle, a4 * 2 ** ((med - 69) / 12))
                last_good = now
                hist.append(needle)
            else:
                if time.ticks_diff(now, last_good) > 1500:
                    shown = None
                    recent = []
                hist.append(None)
            if len(hist) > _W // 2:
                hist.pop(0)

        # ---- draw ----
        DISPLAY.fill(BG)
        DISPLAY.rect(0, 0, _W, 12, BG_DARK, fill=True)
        DISPLAY.text(name, 2, 2, FG)
        DISPLAY.text("A4=%dHz" % a4, 92, 2, MID)
        lvl = min(50, level * 50 // 3000)
        DISPLAY.rect(_W - 54, 3, 52, 6, MID)
        DISPLAY.rect(_W - 53, 4, lvl, 4, _GREEN if level >= _GATE else MID, fill=True)

        if shown:
            target, cents, f = shown
            col = cents_color(cents)
            center_text(note_name(target), 16, col, BIG)
            DISPLAY.text("%.1f Hz" % f, 4, 30, MID)
            ct = "%+dc" % round(cents)
            DISPLAY.text(ct, _W - 4 - 8 * len(ct), 30, col)
            if abs(cents) <= 5:
                hint = "in tune"
            elif cents < 0:
                hint = "too low - tune up"
            else:
                hint = "too high - tune down"
            center_text(hint, 50, col)
        else:
            center_text("--", 16, MID, BIG)
            center_text("play a note...", 50, MID)
        if hold:
            DISPLAY.text("HOLD", 4, 16, _YELLOW)

        draw_meter(68, shown[1] if shown else 0, shown is not None)
        if strings:
            draw_strings(108, strings, shown[0] if shown else None)
        else:
            draw_history(104, hist, 28)
        DISPLAY.show()


main()
