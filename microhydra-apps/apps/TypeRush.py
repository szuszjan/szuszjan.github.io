"""TypeRush - typing speed test (WPM) for MicroHydra (Cardputer).

Type the words shown on screen; SPC jumps to the next word.
The timer starts with your first keypress.

Keys (start screen):
  TAB          switch word list (EN / PL)
  1 / 2 / 3    test length 15 / 30 / 60 s
  ENT          start
  ESC / G0     exit
While typing:
  BSPC         delete
  ESC / G0     abort (back to start screen)
"""

import random
import time

import machine
from font import vga1_8x16 as MED
from font import vga2_16x32 as BIG
from lib import display, userinput
from lib.hydra import beeper, config


_W = const(240)
_H = const(135)
_GREEN = const(0x07E0)
_RED = const(0xF800)
_BEST_FILE = const("/typerush.txt")

WORDS = {
    "EN": (
        "the be to of and a in that have it for not on with he as you do at this but "
        "his by from they we say her she or an will my one all would there their what "
        "so up out if about who get which go me when make can like time no just him "
        "know take people into year your good some could them see other than then now "
        "look only come its over think also back after use two how our work first well "
        "way even new want because any these give day most us is was are been has had "
        "were said did very find long down part made may number sound water little "
        "world small place great old under where right still learn plant cover food sun "
        "keyboard pixel byte code python micro hydra signal logic chip clock board"
    ).split(),
    # ASCII only (no Polish diacritics) so every word can be typed directly
    "PL": (
        "kot pies dom las woda okno stol droga miasto rzeka morze niebo chleb mleko "
        "czas praca szkola auto rower kolega mama tata brat siostra ulica park lato "
        "zima jesien wiosna dzien noc rano wieczor obiad kolacja herbata kawa gora "
        "pole trawa kwiat drzewo ptak ryba lampa telefon komputer ekran klawisz "
        "program kod bajt bit plytka zegar sygnal bramka logika procesor pamiec "
        "dobry nowy stary duzy maly szybki wolny cieply zimny jasny ciemny"
    ).split(),
}

DISPLAY = display.Display()
CONFIG = config.Config()
INPUT = userinput.UserInput()
BEEP = beeper.Beeper()

BG = CONFIG.palette[2]
BG_DARK = CONFIG.palette[1]
MID = CONFIG.palette[5]
FG = CONFIG.palette[8]
WHITE = CONFIG.palette[10]


def load_best():
    try:
        with open(_BEST_FILE) as f:
            return int(f.read().strip() or 0)
    except Exception:  # noqa: BLE001
        return 0


def save_best(wpm):
    try:
        with open(_BEST_FILE, "w") as f:
            f.write(str(wpm))
    except Exception:  # noqa: BLE001
        pass


def center_text(text, y, color, font=None):
    width = DISPLAY.get_total_width(text, font)
    DISPLAY.text(text, (_W - width) // 2, y, color, font)


def make_lines(words, max_chars=28):
    """Split a word list into display lines (list of lists of word indexes)."""
    lines, line, length = [], [], 0
    for i, w in enumerate(words):
        if line and length + 1 + len(w) > max_chars:
            lines.append(line)
            line, length = [], 0
        length += len(w) + (1 if line else 0)
        line.append(i)
    if line:
        lines.append(line)
    return lines


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ screens ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def start_screen(settings, best, last):
    redraw = True
    while True:
        keys = INPUT.get_new_keys()
        if "ESC" in keys or "G0" in keys:
            return False
        if "TAB" in keys:
            settings["lang"] = "PL" if settings["lang"] == "EN" else "EN"
            redraw = True
        for k, sec in (("1", 15), ("2", 30), ("3", 60)):
            if k in keys:
                settings["secs"] = sec
                redraw = True
        if "ENT" in keys or "SPC" in keys:
            return True

        if redraw:
            redraw = False
            DISPLAY.fill(BG)
            center_text("TypeRush", 6, FG, BIG)
            center_text("words: %s  [TAB]" % settings["lang"], 46, WHITE)
            center_text("time: %ds  [1/2/3]" % settings["secs"], 60, WHITE)
            center_text("best: %d WPM" % best, 80, MID)
            if last:
                center_text("last: %d WPM  acc %d%%" % last, 94, FG)
            center_text("ENT = start", 118, MID)
            DISPLAY.show()
        time.sleep_ms(15)


def run_test(settings):
    """Run one test. Return (wpm, accuracy) or None if aborted."""
    pool = WORDS[settings["lang"]]
    words = [random.choice(pool) for _ in range(120)]
    lines = make_lines(words)
    typed = [""] * len(words)  # what the user typed for each word
    cur = 0  # current word index
    total_keys = 0
    wrong_keys = 0
    start = None
    duration = settings["secs"] * 1000

    while True:
        now = time.ticks_ms()
        keys = INPUT.get_new_keys()

        if "ESC" in keys or "G0" in keys:
            return None

        for k in keys:
            if k == "SPC":
                if typed[cur]:
                    cur += 1
                    if cur >= len(words):
                        cur = len(words) - 1
            elif k in ("BSPC", "DEL"):
                typed[cur] = typed[cur][:-1]
            elif len(k) == 1 and k != " ":
                if start is None:
                    start = now
                total_keys += 1
                target = words[cur]
                pos = len(typed[cur])
                if pos >= len(target) or target[pos] != k:
                    wrong_keys += 1
                typed[cur] += k

        elapsed = time.ticks_diff(now, start) if start is not None else 0
        if start is not None and elapsed >= duration:
            break

        # ---- draw ----
        DISPLAY.fill(BG)
        # time bar
        left = duration - elapsed
        bar = _W * left // duration
        DISPLAY.rect(0, 0, bar, 4, FG, fill=True)
        secs_left = (left + 999) // 1000
        DISPLAY.text("%ds" % secs_left, _W - 32, 8, MID)
        if start is None:
            DISPLAY.text("start typing...", 4, 8, MID)

        # find line of current word, show it + 3 next
        line_idx = 0
        for li, line in enumerate(lines):
            if cur in line:
                line_idx = li
                break
        y = 28
        for li in range(line_idx, min(line_idx + 4, len(lines))):
            x = 8
            for wi in lines[li]:
                target = words[wi]
                t = typed[wi]
                if wi < cur:
                    color = _GREEN if t == target else _RED
                    DISPLAY.text(target, x, y, color, MED)
                elif wi == cur:
                    # per-character coloring of the current word
                    cx = x
                    for ci, ch in enumerate(target):
                        if ci < len(t):
                            c = _GREEN if t[ci] == ch else _RED
                        else:
                            c = WHITE
                        DISPLAY.text(ch, cx, y, c, MED)
                        cx += 8
                    extra = t[len(target):]
                    if extra:
                        DISPLAY.text(extra, cx, y, _RED, MED)
                        cx += 8 * len(extra)
                    # cursor + underline
                    cur_x = x + 8 * len(t)
                    DISPLAY.vline(cur_x, y, 16, FG)
                    DISPLAY.hline(x, y + 17, 8 * max(len(target), len(t)), MID)
                else:
                    DISPLAY.text(target, x, y, MID, MED)
                x += 8 * (len(target) + 1)
            y += 24
        DISPLAY.show()
        time.sleep_ms(10)

    # ---- results ----
    correct_chars = 0
    for i in range(cur + 1):
        if typed[i] == words[i]:
            correct_chars += len(words[i]) + 1  # + space
    minutes = duration / 60000
    wpm = int((correct_chars / 5) / minutes)
    acc = 100 if total_keys == 0 else int(100 * (total_keys - wrong_keys) / total_keys)
    BEEP.play(("C5", "E5", "G5"), 80)
    return wpm, acc


def result_screen(wpm, acc, new_best):
    DISPLAY.fill(BG)
    center_text("%d WPM" % wpm, 16, WHITE, BIG)
    center_text("accuracy %d%%" % acc, 58, FG, MED)
    if new_best:
        center_text("NEW BEST!", 80, _GREEN, MED)
    center_text("ENT = continue", 118, MID)
    DISPLAY.show()
    time.sleep_ms(600)  # avoid skipping the screen with a late keypress
    INPUT.get_new_keys()
    while True:
        keys = INPUT.get_new_keys()
        if "ENT" in keys or "ESC" in keys or "G0" in keys or "SPC" in keys:
            return
        time.sleep_ms(20)


def main():
    settings = {"lang": "EN", "secs": 30}
    best = load_best()
    last = None
    while True:
        if not start_screen(settings, best, last):
            machine.reset()
            return
        result = run_test(settings)
        if result is None:
            continue
        wpm, acc = result
        last = result
        new_best = wpm > best
        if new_best:
            best = wpm
            save_best(best)
        result_screen(wpm, acc, new_best)


main()
