"""Morse - Morse code sender, straight key decoder and trainer for MicroHydra (Cardputer).

Modes (TAB switches):
  SEND   type text, ENT plays it through the speaker (and flashes the screen)
  KEY    hold SPC (or the G0 button) like a telegraph key; it is decoded live
  LEARN  listen to a random character and type what you heard;
         new characters unlock as your streak grows (Koch order)

Keys (all modes):
  TAB              next mode
  FN + ; / FN + .  speed +/- (WPM)
  ESC (FN + `)     exit
SEND:  BSPC delete, FN+BSPC (DEL) clear, ENT play / stop
KEY:   BSPC delete last char, DEL clear
LEARN: SPC replay
"""

import random
import time

import machine
from font import vga1_8x16 as MED
from font import vga2_16x32 as BIG
from lib import display, userinput
from lib.audio import Audio
from lib.hydra import config


_W = const(240)
_H = const(135)
_GREEN = const(0x07E0)
_RED = const(0xF800)
_TONE_NOTE = const(16)  # ~E5 with the square sample, a typical sidetone pitch

CODE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "/": "-..-.", "=": "-...-",
}
DECODE = {v: k for k, v in CODE.items()}
KOCH = "KMRSUAPTLOWI.NJEF0YV,G5/Q9ZH38B?427C1D6X"

_SQUARE = const(
    b'\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80'
    b'\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80'
    b'\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80'
    b'\x00\x80\x00\x80\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F'
    b'\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F'
    b'\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F'
    b'\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\xFF\x7F\x00\x80'
)
SQUARE = memoryview(_SQUARE)

DISPLAY = display.Display()
CONFIG = config.Config()
INPUT = userinput.UserInput()
AUDIO = Audio()

BG = CONFIG.palette[2]
BG_DARK = CONFIG.palette[1]
MID = CONFIG.palette[5]
FG = CONFIG.palette[8]
WHITE = CONFIG.palette[10]

MODES = ("SEND", "KEY", "LEARN")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ tone / player ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class Tone:
    def __init__(self):
        self.on = False

    def start(self):
        if not self.on:
            self.on = True
            vol = min(15, CONFIG["volume"] + 5)
            AUDIO.play(SQUARE, note=_TONE_NOTE, volume=vol, channel=0, loop=True)

    def stop(self):
        if self.on:
            self.on = False
            AUDIO.stop(channel=0)


TONE = Tone()


class Player:
    """Non-blocking Morse player driven from the main loop."""

    def __init__(self):
        self.segments = []  # (tone_on, units, char_index)
        self.idx = 0
        self.seg_end = 0
        self.char_idx = -1

    def play(self, text, unit_ms):
        segs = []
        for ci, ch in enumerate(text.upper()):
            if ch == " ":
                segs.append((False, 7, ci))
                continue
            code = CODE.get(ch)
            if not code:
                continue
            for si, sym in enumerate(code):
                segs.append((True, 1 if sym == "." else 3, ci))
                segs.append((False, 1 if si < len(code) - 1 else 3, ci))
        self.segments = segs
        self.unit = unit_ms
        self.idx = -1
        self.seg_end = time.ticks_ms()

    @property
    def busy(self):
        return self.idx < len(self.segments) and bool(self.segments)

    def stop(self):
        self.segments = []
        self.char_idx = -1
        TONE.stop()

    def update(self):
        if not self.segments:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self.seg_end) < 0:
            return
        self.idx += 1
        if self.idx >= len(self.segments):
            self.stop()
            return
        on, units, ci = self.segments[self.idx]
        self.char_idx = ci
        self.seg_end = time.ticks_add(self.seg_end, units * self.unit)
        if on:
            TONE.start()
        else:
            TONE.stop()


PLAYER = Player()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ helpers ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def center_text(text, y, color, font=None):
    width = DISPLAY.get_total_width(text, font)
    DISPLAY.text(text, (_W - width) // 2, y, color, font)


def header(mode, wpm):
    DISPLAY.rect(0, 0, _W, 14, BG_DARK, fill=True)
    x = 4
    for i, name in enumerate(MODES):
        if i == mode:
            DISPLAY.rect(x - 2, 1, len(name) * 8 + 4, 12, FG, fill=True)
            DISPLAY.text(name, x, 3, BG)
        else:
            DISPLAY.text(name, x, 3, MID)
        x += len(name) * 8 + 10
    DISPLAY.text("%dwpm" % wpm, _W - 48, 3, MID)


def draw_code(code, y, color):
    """Draw dots and dashes as shapes, centered."""
    width = sum(6 if s == "." else 18 for s in code) + 6 * max(0, len(code) - 1)
    x = (_W - width) // 2
    for s in code:
        if s == ".":
            DISPLAY.ellipse(x + 3, y + 3, 3, 3, color, fill=True)
            x += 12
        else:
            DISPLAY.rect(x, y, 18, 7, color, fill=True)
            x += 24


def wrap_tail(text, chars, lines):
    """Return the last `lines` lines of text wrapped to `chars` columns."""
    out = [text[i:i + chars] for i in range(0, len(text), chars)] or [""]
    return out[-lines:], max(0, len(out) - lines) * chars


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ modes ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class SendMode:
    def __init__(self):
        self.text = "CQ CQ DE CARDPUTER"

    def handle(self, keys, pressed, unit):  # noqa: ARG002
        for k in keys:
            if k == "ENT":
                if PLAYER.busy:
                    PLAYER.stop()
                else:
                    PLAYER.play(self.text, unit)
            elif k == "BSPC":
                self.text = self.text[:-1]
            elif k == "DEL":
                self.text = ""
            elif k == "SPC":
                self.text += " "
            elif len(k) == 1 and k.upper() in CODE and len(self.text) < 120:
                self.text += k.upper()

    def draw(self):
        lines, offset = wrap_tail(self.text, 28, 3)
        y = 22
        active = PLAYER.char_idx if PLAYER.busy else -1
        for li, line in enumerate(lines):
            x = 8
            for ci, ch in enumerate(line):
                idx = offset + li * 28 + ci
                DISPLAY.text(ch, x, y, WHITE if idx == active else (MID if active >= 0 else FG), MED)
                x += 8
            y += 18
        if not PLAYER.busy:
            DISPLAY.vline(8 + 8 * len(lines[-1]), y - 18, 16, FG)
        if 0 <= active < len(self.text):
            ch = self.text[active]
            if ch != " ":
                draw_code(CODE.get(ch, ""), 92, WHITE)
                DISPLAY.text(ch, 8, 86, FG, MED)
        center_text("ENT = play" if not PLAYER.busy else "ENT = stop", 120, MID)


class KeyMode:
    def __init__(self):
        self.text = ""
        self.symbols = ""
        self.down = False
        self.t_down = 0
        self.t_up = time.ticks_ms()

    def handle(self, keys, pressed, unit):
        now = time.ticks_ms()
        for k in keys:
            if k == "BSPC":
                self.text = self.text[:-1]
            elif k == "DEL":
                self.text = ""
                self.symbols = ""
        is_down = "SPC" in pressed or "G0" in pressed or "ENT" in pressed
        if is_down and not self.down:
            self.down = True
            self.t_down = now
            TONE.start()
        elif not is_down and self.down:
            self.down = False
            dur = time.ticks_diff(now, self.t_down)
            self.symbols += "." if dur < 2 * unit else "-"
            self.t_up = now
            TONE.stop()
        elif not is_down:
            gap = time.ticks_diff(now, self.t_up)
            if self.symbols and gap > 3 * unit:
                self.text += DECODE.get(self.symbols, "#")
                self.symbols = ""
            elif not self.symbols and self.text and not self.text.endswith(" ") and gap > 7 * unit:
                self.text += " "
            if len(self.text) > 120:
                self.text = self.text[-120:]

    def draw(self):
        lines, _ = wrap_tail(self.text, 28, 3)
        y = 22
        for line in lines:
            DISPLAY.text(line, 8, y, FG, MED)
            y += 18
        if self.down:
            DISPLAY.rect(0, 78, _W, 34, FG, fill=True)
            draw_code(self.symbols, 92, BG)
        else:
            draw_code(self.symbols, 92, WHITE)
            if self.symbols in DECODE:
                DISPLAY.text(DECODE[self.symbols], 8, 86, MID, MED)
        center_text("hold SPC / G0 = key", 120, MID)


class LearnMode:
    def __init__(self):
        self.level = 2  # number of Koch chars in play
        self.streak = 0
        self.score = 0
        self.asked = 0
        self.target = None
        self.answer = None  # (char typed, correct)
        self.answer_time = 0

    def next_char(self, unit):
        self.target = random.choice(KOCH[:self.level])
        self.answer = None
        PLAYER.play(self.target, unit)

    def handle(self, keys, pressed, unit):  # noqa: ARG002
        if self.target is None:
            self.next_char(unit)
            return
        now = time.ticks_ms()
        if self.answer and time.ticks_diff(now, self.answer_time) > (700 if self.answer[1] else 1600):
            self.next_char(unit)
            return
        for k in keys:
            if k == "SPC":
                PLAYER.play(self.target, unit)
            elif self.answer is None and len(k) == 1 and k.upper() in CODE:
                ok = k.upper() == self.target
                self.answer = (k.upper(), ok)
                self.answer_time = now
                self.asked += 1
                if ok:
                    self.score += 1
                    self.streak += 1
                    if self.streak >= 5 and self.level < len(KOCH):
                        self.level += 1
                        self.streak = 0
                else:
                    self.streak = 0

    def draw(self):
        DISPLAY.text("chars: %s" % KOCH[:self.level], 8, 20, MID)
        DISPLAY.text("%d/%d  streak %d/5" % (self.score, self.asked, self.streak), 8, 30, MID)
        if self.answer is None:
            center_text("?", 46, WHITE, BIG)
            center_text("type what you hear, SPC=replay", 120, MID)
        else:
            typed, ok = self.answer
            color = _GREEN if ok else _RED
            center_text(self.target if ok else "%s (not %s)" % (self.target, typed), 46, color, BIG)
            draw_code(CODE[self.target], 92, WHITE)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ main loop ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main():
    modes = [SendMode(), KeyMode(), LearnMode()]
    current = 0
    wpm = 15
    while True:
        keys = INPUT.get_new_keys()
        pressed = INPUT.key_state
        unit = 1200 // wpm

        if "ESC" in keys:
            PLAYER.stop()
            machine.reset()
            return
        if "G0" in keys and current != 1:
            PLAYER.stop()
            machine.reset()
            return
        if "TAB" in keys:
            PLAYER.stop()
            current = (current + 1) % len(modes)
            keys = [k for k in keys if k != "TAB"]
        if "UP" in keys:
            wpm = min(40, wpm + 1)
        if "DOWN" in keys:
            wpm = max(5, wpm - 1)

        modes[current].handle(keys, pressed, unit)
        PLAYER.update()

        DISPLAY.fill(BG)
        header(current, wpm)
        modes[current].draw()
        # visual "lamp" while the tone is on
        if TONE.on:
            DISPLAY.ellipse(_W - 10, 24, 5, 5, WHITE, fill=True)
        DISPLAY.show()
        time.sleep_ms(5)


main()
