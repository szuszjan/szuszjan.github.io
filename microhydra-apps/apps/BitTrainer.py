"""BitTrainer - binary / decimal / hex conversion trainer for MicroHydra (Cardputer).

Pick a mode, type the answer, press ENT. Score, streak and best streak are shown.

Keys:
  ; .  (or FN + ; .)   move in menu
  ENT                 start / submit answer
  TAB                 toggle 4-bit / 8-bit (in menu)
  BSPC                delete last char
  ESC (FN + `) / G0   back to menu, or exit from menu
"""

import random
import time

import machine
from font import vga2_16x32 as BIG
from lib import display, userinput
from lib.hydra import beeper, config


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ constants ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
_W = const(240)
_H = const(135)
_GREEN = const(0x07E0)
_RED = const(0xF800)

DIRS = {';': 'UP', '.': 'DOWN', ',': 'LEFT', '/': 'RIGHT'}

# (label, source base, answer base)
MODES = (
    ("BIN -> DEC", 2, 10),
    ("DEC -> BIN", 10, 2),
    ("HEX -> DEC", 16, 10),
    ("DEC -> HEX", 10, 16),
    ("BIN -> HEX", 2, 16),
    ("HEX -> BIN", 16, 2),
)
ALLOWED = {
    2: "01",
    10: "0123456789",
    16: "0123456789abcdef",
}
PREFIX = {2: "0b", 10: "", 16: "0x"}


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ objects ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DISPLAY = display.Display()
CONFIG = config.Config()
INPUT = userinput.UserInput()
BEEP = beeper.Beeper()

BG = CONFIG.palette[2]
BG_DARK = CONFIG.palette[1]
MID = CONFIG.palette[5]
FG = CONFIG.palette[8]
WHITE = CONFIG.palette[10]


def to_base(n, base, bits):
    """Format n in the given base (binary is zero padded)."""
    if base == 2:
        s = bin(n)[2:]
        return "0" * (bits - len(s)) + s
    if base == 16:
        return "%X" % n
    return str(n)


def center_text(text, y, color, font=None):
    width = DISPLAY.get_total_width(text, font)
    DISPLAY.text(text, (_W - width) // 2, y, color, font)


def draw_bits(value, bits, y):
    """Draw the value as a row of 'LEDs' (on = ui color)."""
    size = 12 if bits == 8 else 18
    gap = 4
    total = bits * size + (bits - 1) * gap
    x = (_W - total) // 2
    for i in range(bits):
        on = (value >> (bits - 1 - i)) & 1
        DISPLAY.rect(x, y, size, size, FG if on else BG_DARK, fill=True)
        DISPLAY.rect(x, y, size, size, MID)
        x += size + gap


def exit_app():
    machine.reset()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ screens ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def menu(state):
    """Return selected mode index, or None to exit."""
    sel = state["mode"]
    redraw = True
    while True:
        keys = [DIRS.get(k, k) for k in INPUT.get_new_keys()]
        if "UP" in keys:
            sel = (sel - 1) % len(MODES)
            redraw = True
        if "DOWN" in keys:
            sel = (sel + 1) % len(MODES)
            redraw = True
        if "TAB" in keys:
            state["bits"] = 4 if state["bits"] == 8 else 8
            redraw = True
        if "ENT" in keys or "SPC" in keys:
            return sel
        if "ESC" in keys or "G0" in keys or "`" in keys:
            return None

        if redraw:
            redraw = False
            DISPLAY.fill(BG)
            DISPLAY.rect(0, 0, _W, 14, BG_DARK, fill=True)
            DISPLAY.text("BitTrainer", 4, 3, FG)
            DISPLAY.text("%d-bit [TAB]" % state["bits"], _W - 100, 3, MID)
            # scrolling list showing 5 items around selection
            first = min(max(0, sel - 2), len(MODES) - 5)
            for row in range(5):
                idx = first + row
                y = 22 + row * 18
                label = MODES[idx][0]
                if idx == sel:
                    DISPLAY.rect(20, y - 4, _W - 40, 16, FG, fill=True)
                    center_text(label, y, BG)
                else:
                    center_text(label, y, FG)
            DISPLAY.text("best streak: %d" % state["best"], 4, _H - 10, MID)
            DISPLAY.show()
        time.sleep_ms(15)


def new_question(bits):
    n = random.randint(1, (1 << bits) - 1)
    return n


def quiz(state, mode_idx):
    label, src, dst = MODES[mode_idx]
    bits = state["bits"]
    score = 0
    asked = 0
    streak = 0
    value = new_question(bits)
    answer = ""
    flash = None  # (until_ms, ok, correct_text)
    max_len = bits if dst == 2 else 3

    while True:
        now = time.ticks_ms()
        keys = INPUT.get_new_keys()

        if "ESC" in keys or "G0" in keys:
            return

        if flash is None:
            for k in keys:
                k_low = k.lower()
                if len(k) == 1 and k_low in ALLOWED[dst]:
                    if len(answer) < max_len:
                        answer += k_low
                elif k in ("BSPC", "DEL"):
                    answer = answer[:-1]
                elif k == "ENT" and answer:
                    ok = int(answer, dst) == value
                    asked += 1
                    if ok:
                        score += 1
                        streak += 1
                        state["best"] = max(state["best"], streak)
                        BEEP.play(("C5", "G5"), 60)
                    else:
                        streak = 0
                        BEEP.play(("C4", "C3"), 120)
                    flash = (time.ticks_add(now, 900 if ok else 1800), ok,
                             PREFIX[dst] + to_base(value, dst, bits))
        elif time.ticks_diff(flash[0], now) <= 0 or "ENT" in keys:
            flash = None
            value = new_question(bits)
            answer = ""

        # ---- draw ----
        DISPLAY.fill(BG)
        DISPLAY.rect(0, 0, _W, 14, BG_DARK, fill=True)
        DISPLAY.text(label, 4, 3, FG)
        DISPLAY.text("%d/%d  x%d" % (score, asked, streak), _W - 96, 3, MID)

        question = PREFIX[src] + to_base(value, src, bits)
        center_text(question, 22, WHITE, BIG if len(question) <= 14 else None)
        if src == 2:
            draw_bits(value, bits, 60)
        elif dst == 2:
            # live preview of the typed answer as LEDs
            live = value if flash else (int(answer, 2) if answer else 0)
            draw_bits(live, bits, 60)

        box_y = 84
        if flash:
            color = _GREEN if flash[1] else _RED
            DISPLAY.rect(10, box_y, _W - 20, 40, color, fill=True)
            msg = "OK!" if flash[1] else "= " + flash[2]
            center_text(msg, box_y + 4, WHITE, BIG if len(msg) <= 14 else None)
        else:
            DISPLAY.rect(10, box_y, _W - 20, 40, BG_DARK, fill=True)
            DISPLAY.rect(10, box_y, _W - 20, 40, MID)
            shown = PREFIX[dst] + answer.upper()
            blink = "_" if (now // 400) % 2 else " "
            center_text(shown + blink, box_y + 4, FG, BIG)
        DISPLAY.show()
        time.sleep_ms(15)


def main():
    state = {"mode": 0, "bits": 8, "best": 0}
    while True:
        sel = menu(state)
        if sel is None:
            exit_app()
            return
        state["mode"] = sel
        quiz(state, sel)


main()
