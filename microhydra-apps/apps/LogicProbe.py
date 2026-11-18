"""LogicProbe - mini logic analyzer for MicroHydra (Cardputer).

Samples the Grove port pins (G1, G2) with a fast viper loop, shows the
waveforms, measures frequency / duty and decodes UART or I2C.
Captures can be saved as .vcd files (open them in PulseView or GTKWave).

Wiring: Grove port. G1 = CH1, G2 = CH2, plus GND (check your cable's pinout).
Signals must be 3.3 V logic!  Do NOT connect 5 V signals directly.
For I2C decoding: SCL -> G1, SDA -> G2.

Keys (view):
  SPC         run / stop (continuous capture)
  ENT         single capture
  , /         scroll left / right      < ?   fine scroll
  ; .         zoom in / out
  g           jump to trigger point
  s           save capture as .vcd (SD card if present, else flash)
  TAB         settings
  ESC / G0    exit
Keys (settings):
  ; .  choose,   , /  change value,   TAB / ENT  back to view

"Test out" outputs a PWM signal on the last pin (G2), so you can try the
app without any wiring (CH2 shows its own output), or bridge G2 -> G1.
"Source: DEMO" fills the buffer with generated example signals.
"""

import os
import time
from array import array

import machine
from machine import PWM, Pin
from lib import display, userinput
from lib.hydra import config


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ hardware config ~~~~~~~~~~~~~~~~~~~~~~~~~
# Pins to sample. They must lie within 8 consecutive GPIO numbers.
# (Cardputer ADV users can add pins from the EXT header here, max 4.)
PINS = (1, 2)
NAMES = ("G1", "G2")

_GPIO_IN = const(0x6000403C)    # ESP32-S3 GPIO_IN_REG (GPIO 0..31)
_IO_MUX_GPIO0 = const(0x60009004)  # ESP32-S3 IO_MUX_GPIO0_REG
_FUN_IE = const(0x200)          # input enable bit in IO_MUX register

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ constants ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
_W = const(240)
_H = const(135)
_TOP = const(12)

RATES = (0, 1_000_000, 500_000, 200_000, 100_000, 50_000, 20_000, 10_000, 5_000, 2_000, 1_000)
RATE_LABELS = ("max", "1M", "500k", "200k", "100k", "50k", "20k", "10k", "5k", "2k", "1k")
SIZES = (1024, 4096, 16384)
BAUDS = (9600, 19200, 38400, 57600, 115200)
TEST_FREQS = (0, 1000, 10_000, 100_000)
PRE = (0, 10, 50)
CH_COLORS = (0xFFE0, 0x07FF, 0xF81F, 0x07E0)  # yellow, cyan, magenta, green

SETTINGS = (
    ("Rate", "rate", RATE_LABELS),
    ("Samples", "size", ("1k", "4k", "16k")),
    ("Trigger", "trig", ("off", "rising", "falling", "any edge")),
    ("Trig ch", "tch", NAMES),
    ("Pre-trigger", "pre", ("0%", "10%", "50%")),
    ("Pull", "pull", ("none", "up", "down")),
    ("Decoder", "dec", ("none", "UART", "I2C (G1=SCL)")),
    ("UART ch", "uch", NAMES),
    ("Baud", "baud", tuple(str(b) for b in BAUDS)),
    ("Test out " + NAMES[-1], "tout", ("off", "1 kHz", "10 kHz", "100 kHz")),
    ("Source", "src", ("Grove", "DEMO")),
)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ objects ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DISPLAY = display.Display()
CONFIG = config.Config()
INPUT = userinput.UserInput()

BG = CONFIG.palette[2]
BG_DARK = CONFIG.palette[1]
GRID = CONFIG.palette[3]
MID = CONFIG.palette[5]
FG = CONFIG.palette[8]
WHITE = CONFIG.palette[10]

_SHIFT = min(PINS)
CH_BITS = tuple(1 << (p - _SHIFT) for p in PINS)
PARAMS = array("i", [0] * 8)
PARAMS[7] = _GPIO_IN  # only _capture reads slot 7
RESULT = array("i", [0] * 4)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ viper helpers ~~~~~~~~~~~~~~~~~~~~~~~~~~~
@micropython.viper
def _capture(buf, params) -> int:
    """Sample GPIO_IN into buf (ring buffer) with optional edge trigger.

    params: n, delay, shift, trigger mask, mode (0 off, 1 rise, 2 fall, 3 any),
            pre-trigger samples, timeout (samples), GPIO_IN address
    Returns index of the oldest sample, or -1 on trigger timeout.
    """
    prm = ptr32(params)
    n = prm[0]
    delay = prm[1]
    shift = prm[2]
    tmask = prm[3]
    mode = prm[4]
    pre = prm[5]
    timeout = prm[6]
    gpio = ptr32(prm[7])  # GPIO_IN address (passed in: too big for a small-int const)
    b = ptr8(buf)
    i = 0
    count = 0
    remaining = n
    triggered = 0
    if mode == 0:
        triggered = 1
    prev = (gpio[0] >> shift) & tmask
    while True:
        v = (gpio[0] >> shift) & 0xFF
        b[i] = v
        i += 1
        if i >= n:
            i = 0
        if triggered:
            remaining -= 1
            if remaining <= 0:
                break
        else:
            count += 1
            cur = v & tmask
            if count > pre and cur != prev:
                if mode == 3 or (mode == 1 and cur != 0) or (mode == 2 and cur == 0):
                    triggered = 1
                    remaining = n - pre - 1
                    if remaining <= 0:
                        break
            if count > timeout:
                return -1
            prev = cur
        d = delay
        while d > 0:
            d -= 1
    return i


@micropython.viper
def _summary(buf, params, out):
    """For each screen column: OR and AND of all samples in it.

    params: start, samples per column, columns, n
    An 'empty' column (past the end) gets OR=0, AND=0xFF.
    """
    prm = ptr32(params)
    idx = prm[0]
    spp = prm[1]
    cols = prm[2]
    n = prm[3]
    b = ptr8(buf)
    o = ptr8(out)
    c = 0
    while c < cols:
        orv = 0
        andv = 0xFF
        if idx < n:
            k = 0
            while k < spp and idx < n:
                v = b[idx]
                orv |= v
                andv &= v
                idx += 1
                k += 1
        o[2 * c] = orv
        o[2 * c + 1] = andv
        c += 1


@micropython.viper
def _next_edge(buf, params) -> int:
    """Return index of the next change of (sample & mask), or -1.

    params: start, end, mask, kind (0 any, 1 rising, 2 falling)
    """
    prm = ptr32(params)
    i = prm[0]
    end = prm[1]
    mask = prm[2]
    kind = prm[3]
    b = ptr8(buf)
    if i < 1:
        i = 1
    prev = b[i - 1] & mask
    while i < end:
        v = b[i] & mask
        if v != prev:
            if kind == 0:
                return i
            if kind == 1 and v != 0:
                return i
            if kind == 2 and v == 0:
                return i
        prev = v
        i += 1
    return -1


@micropython.viper
def _measure(buf, params, res):
    """Count rising edges and high samples. params: start, end, mask."""
    prm = ptr32(params)
    start = prm[0]
    end = prm[1]
    mask = prm[2]
    b = ptr8(buf)
    r = ptr32(res)
    rises = 0
    first = -1
    last = -1
    high = 0
    prev = b[start] & mask
    i = start
    while i < end:
        v = b[i] & mask
        if v != 0:
            high += 1
            if prev == 0:
                rises += 1
                if first < 0:
                    first = i
                last = i
        prev = v
        i += 1
    r[0] = rises
    r[1] = first
    r[2] = last
    r[3] = high


def next_edge(buf, start, end, mask, kind=0):
    PARAMS[0] = start
    PARAMS[1] = end
    PARAMS[2] = mask
    PARAMS[3] = kind
    return _next_edge(buf, PARAMS)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ formatting ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def fmt(value, unit):
    """Engineering format, e.g. 0.0000125 s -> '12.5us'."""
    if value is None:
        return "-"
    a = abs(value)
    for mult, pre in ((1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "u"), (1e-9, "n")):
        if a >= mult * 0.9995:
            v = value / mult
            break
    else:
        return "0" + unit
    if abs(v) >= 100:
        s = "%d" % round(v)
    elif abs(v) >= 10:
        s = "%.1f" % v
    else:
        s = "%.2f" % v
    return s + pre + unit


def center_text(text, y, color):
    DISPLAY.text(text, (_W - len(text) * 8) // 2, y, color)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ analyzer ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class Analyzer:
    def __init__(self):
        self.s = {"rate": 3, "size": 1, "trig": 0, "tch": 0, "pre": 1, "pull": 0,
                  "dec": 0, "uch": 0, "baud": 4, "tout": 0, "src": 0}
        self.buf = bytearray(SIZES[self.s["size"]])
        self.n = 0              # number of valid samples
        self.period_ns = 1000.0  # sample period of the current capture
        self.trig_idx = -1
        self.view = 0           # first sample on screen
        self.zoom = 0           # >=0: 2**zoom samples per px, <0: 2**-zoom px per sample
        self.decoded = []       # (start, end, label)
        self.meas = []          # per channel (freq, duty)
        self.state = "STOP"     # STOP / ARMED / RUN
        self.msg = "ENT = capture, TAB = settings"
        self.pwm = None
        self.cal_a = 1000.0     # ns per sample with delay 0
        self.cal_b = 10.0       # ns per delay iteration
        self.summ = bytearray(_W * 2)
        self.apply_pins()
        self.calibrate()

    # ---------------------------------------------------------------- hardware
    def apply_pins(self):
        pull = (None, Pin.PULL_UP, Pin.PULL_DOWN)[self.s["pull"]]
        if self.pwm:
            self.pwm.deinit()
            self.pwm = None
        for i, p in enumerate(PINS):
            if i == len(PINS) - 1 and self.s["tout"]:
                self.pwm = PWM(Pin(p), freq=TEST_FREQS[self.s["tout"]], duty_u16=32768)
                # keep the pad input enabled, so CH reads back its own PWM
                try:
                    machine.mem32[_IO_MUX_GPIO0 + 4 * p] |= _FUN_IE
                except Exception:  # noqa: BLE001
                    pass
            else:
                Pin(p, Pin.IN, pull)

    def calibrate(self):
        """Measure how long one sample takes for delay=0 and delay=64."""
        buf = bytearray(2048)
        times = []
        for delay in (0, 64):
            PARAMS[0] = 2048
            PARAMS[1] = delay
            PARAMS[2] = _SHIFT
            PARAMS[3] = 0
            PARAMS[4] = 0
            PARAMS[5] = 0
            PARAMS[6] = 0
            t0 = time.ticks_us()
            _capture(buf, PARAMS)
            times.append(time.ticks_diff(time.ticks_us(), t0) * 1000 / 2048)
        self.cal_a = max(1.0, times[0])
        self.cal_b = max(0.5, (times[1] - times[0]) / 64)

    def delay_for_rate(self):
        """Return (delay loop count, expected sample period in ns)."""
        rate = RATES[self.s["rate"]]
        if rate == 0:
            return 0, self.cal_a
        target = 1e9 / rate
        if target <= self.cal_a:
            return 0, self.cal_a
        delay = int((target - self.cal_a) / self.cal_b + 0.5)
        return delay, self.cal_a + delay * self.cal_b

    # ---------------------------------------------------------------- capture
    def capture(self):
        """Do one capture attempt. Return True if data was captured."""
        size = SIZES[self.s["size"]]
        if len(self.buf) != size:
            self.buf = None
            self.buf = bytearray(size)
        delay, period = self.delay_for_rate()

        if self.s["src"] == 1:
            self.period_ns = period
            self.make_demo()
        else:
            mode = self.s["trig"]
            pre = size * PRE[self.s["pre"]] // 100 if mode else 0
            PARAMS[0] = size
            PARAMS[1] = delay
            PARAMS[2] = _SHIFT
            PARAMS[3] = CH_BITS[self.s["tch"]]
            PARAMS[4] = mode
            PARAMS[5] = pre
            PARAMS[6] = int(1e9 / period)  # ~1 s timeout
            t0 = time.ticks_us()
            start = _capture(self.buf, PARAMS)
            if start < 0:
                return False
            if mode == 0:
                # untriggered capture: measure the real sample rate
                period = time.ticks_diff(time.ticks_us(), t0) * 1000 / size
            if start:
                self.buf[:] = self.buf[start:] + self.buf[:start]
            self.period_ns = period
            self.trig_idx = pre if mode else -1

        self.n = size
        self.analyze()
        if self.trig_idx >= 0:
            self.center_on(self.trig_idx)
        else:
            self.clamp_view()
        return True

    def make_demo(self):
        """Fill the buffer with generated example signals."""
        n = len(self.buf)
        per = self.period_ns
        ch = [bytearray(n) for _ in CH_BITS]
        dec = self.s["dec"]
        self.trig_idx = -1

        def paint(arr, mask, levels, step, offset):
            """Paint a list of 0/1 levels, each `step` samples long."""
            pos = offset
            for lv in levels:
                a = int(pos)
                pos += step
                b = min(n, int(pos))
                if a >= n:
                    break
                if lv:
                    arr[a:b] = bytes([mask]) * (b - a)

        if dec == 2:  # I2C on CH1 (SCL) + CH2 (SDA), 100 kHz
            q = 2500 / per  # quarter bit in samples
            scl, sda = [1, 1], [1, 1]

            def add(s_scl, s_sda):
                scl.append(s_scl)
                sda.append(s_sda)

            def start():
                add(1, 1)
                add(1, 0)
                add(0, 0)

            def stop():
                add(0, 0)
                add(1, 0)
                add(1, 1)
                add(1, 1)

            def clock(d):
                add(0, d)
                add(1, d)
                add(1, d)
                add(0, d)

            def byte(v, ack=True):
                for k in range(7, -1, -1):
                    clock((v >> k) & 1)
                clock(0 if ack else 1)

            start()
            byte(0x3C << 1)
            byte(0x00)
            byte(0xAF)
            stop()
            start()
            byte((0x76 << 1) | 1)
            byte(0x58, ack=False)
            stop()
            for _ in range(12):
                add(1, 1)
            # repeat the transaction until the buffer is full (bus idles high)
            reps = int(n / (len(scl) * q)) + 1
            scl *= reps
            sda *= reps
            paint(ch[0], CH_BITS[0], scl, q, 0)
            if len(ch) > 1:
                paint(ch[1], CH_BITS[1], sda, q, 0)
        else:
            if dec == 1:  # UART "Hello Cardputer!" on the UART channel
                baud = BAUDS[self.s["baud"]]
                spb = 1e9 / (baud * per)
                levels = [1] * 3
                for c in b"Hello Cardputer! ":
                    levels += [0] + [(c >> i) & 1 for i in range(8)] + [1, 1]
                levels = levels * 4
                uch = self.s["uch"]
                paint(ch[uch], CH_BITS[uch], levels, spb, 0)
                other = 1 - uch if len(ch) > 1 else None
            else:
                other = 1 if len(ch) > 1 else None
                # CH1: 10 kHz clock
                half = 50_000 / per
                paint(ch[0], CH_BITS[0], [1, 0] * (int(n / max(1, 2 * half)) + 2), half, 0)
            if other is not None:
                # 1 kHz PWM, 25 % duty
                period = 1_000_000 / per
                pos = 0.0
                while pos < n:
                    a = int(pos)
                    b = min(n, int(pos + period / 4))
                    ch[other][a:b] = bytes([CH_BITS[other]]) * (b - a)
                    pos += period
        buf = self.buf
        for i in range(n):
            v = 0
            for arr in ch:
                v |= arr[i]
            buf[i] = v

    # ---------------------------------------------------------------- analysis
    def analyze(self):
        n = self.n
        self.msg = ""
        self.meas = []
        for bit in CH_BITS:
            PARAMS[0] = 0
            PARAMS[1] = n
            PARAMS[2] = bit
            _measure(self.buf, PARAMS, RESULT)
            rises, first, last, high = RESULT[0], RESULT[1], RESULT[2], RESULT[3]
            freq = None
            if rises >= 2 and last > first:
                freq = (rises - 1) / ((last - first) * self.period_ns * 1e-9)
            self.meas.append((freq, 100 * high // n if n else 0))
        self.decoded = []
        dec = self.s["dec"]
        if dec == 1:
            self.decode_uart()
        elif dec == 2 and len(CH_BITS) > 1:
            self.decode_i2c()

    def decode_uart(self):
        mask = CH_BITS[self.s["uch"]]
        spb = 1e9 / (BAUDS[self.s["baud"]] * self.period_ns)
        if spb < 3:
            self.msg = "rate too low for this baud!"
            return
        buf, n = self.buf, self.n
        i = 1
        while True:
            i = next_edge(buf, i, n, mask, 2)  # start bit = falling edge
            if i < 0 or i + int(10 * spb) >= n:
                break
            value = 0
            for k in range(8):
                if buf[int(i + spb * (1.5 + k))] & mask:
                    value |= 1 << k
            ok = buf[int(i + spb * 9.5)] & mask
            if not ok:
                label = "ERR"
            elif 32 <= value < 127:
                label = chr(value)
            else:
                label = "%02X" % value
            self.decoded.append((i, int(i + spb * 10), label))
            i = int(i + spb * 9.5)
            # wait for the line to be high again before the next start bit
            if not ok:
                i = next_edge(buf, i, n, mask, 1)
                if i < 0:
                    break

    def decode_i2c(self):
        if 10_000 / self.period_ns < 6:  # samples per 100 kHz bit
            self.msg = "rate too low for I2C (use 500k+)"
            return
        scl_m, sda_m = CH_BITS[0], CH_BITS[1]
        both = scl_m | sda_m
        buf, n = self.buf, self.n
        prev = buf[0]
        bits = 0
        nbits = 0
        bstart = 0
        first_byte = False
        i = 1
        while True:
            i = next_edge(buf, i, n, both, 0)
            if i < 0:
                break
            cur = buf[i]
            if prev & scl_m and cur & scl_m:
                if prev & sda_m and not cur & sda_m:
                    self.decoded.append((i, i, "S"))
                    nbits = 0
                    bits = 0
                    first_byte = True
                elif cur & sda_m and not prev & sda_m:
                    self.decoded.append((i, i, "P"))
                    nbits = 0
            elif cur & scl_m and not prev & scl_m:
                if nbits == 0:
                    bstart = i
                bits = (bits << 1) | (1 if cur & sda_m else 0)
                nbits += 1
                if nbits == 9:
                    value = bits >> 1
                    ack = "" if bits & 1 == 0 else "~"
                    if first_byte:
                        label = "%s%02X" % ("R" if value & 1 else "W", value >> 1)
                        first_byte = False
                    else:
                        label = "%02X" % value
                    self.decoded.append((bstart, i, label + ack))
                    nbits = 0
                    bits = 0
            prev = cur
            i += 1

    # ---------------------------------------------------------------- view math
    def visible_samples(self):
        if self.zoom >= 0:
            return _W << self.zoom
        return _W >> -self.zoom

    def clamp_view(self):
        vis = self.visible_samples()
        self.view = max(0, min(self.view, self.n - vis))

    def center_on(self, idx):
        self.view = idx - self.visible_samples() // 2
        self.clamp_view()

    def x_of(self, idx):
        if self.zoom >= 0:
            return (idx - self.view) >> self.zoom
        return (idx - self.view) << -self.zoom

    def set_zoom(self, z):
        max_zoom = 0
        while (_W << max_zoom) < self.n:
            max_zoom += 1
        z = max(-3, min(max_zoom, z))
        center = self.view + self.visible_samples() // 2
        self.zoom = z
        self.center_on(center)

    # ---------------------------------------------------------------- export
    def save_vcd(self):
        if not self.n:
            return "nothing to save"
        folder = "/"
        try:
            from lib import sdcard
            sdcard.SDCard().mount()
            folder = "/sd/"
        except Exception:  # noqa: BLE001
            pass
        num = 1
        while True:
            name = "%sla_%03d.vcd" % (folder, num)
            try:
                os.stat(name)
                num += 1
            except OSError:
                break
        ids = "!#$%"
        buf, per = self.buf, self.period_ns
        with open(name, "w") as f:
            f.write("$timescale 1ns $end\n$scope module cardputer $end\n")
            for i, nm in enumerate(NAMES):
                f.write("$var wire 1 %s %s $end\n" % (ids[i], nm))
            f.write("$upscope $end\n$enddefinitions $end\n#0\n")
            prev = buf[0]
            for i, bit in enumerate(CH_BITS):
                f.write("%d%s\n" % (1 if prev & bit else 0, ids[i]))
            i = 1
            all_mask = 0
            for bit in CH_BITS:
                all_mask |= bit
            while True:
                i = next_edge(buf, i, self.n, all_mask, 0)
                if i < 0:
                    break
                cur = buf[i]
                f.write("#%d\n" % int(i * per))
                for c, bit in enumerate(CH_BITS):
                    if (cur ^ prev) & bit:
                        f.write("%d%s\n" % (1 if cur & bit else 0, ids[c]))
                prev = cur
                i += 1
            f.write("#%d\n" % int(self.n * per))
        return "saved " + name

    # ---------------------------------------------------------------- drawing
    def draw(self):
        DISPLAY.fill(BG)
        s = self.s
        # ---- top bar
        DISPLAY.rect(0, 0, _W, 11, BG_DARK, fill=True)
        rate = 1e9 / self.period_ns if self.n else 1e9 / self.delay_for_rate()[1]
        trig = ("-", "/", "\\", "X")[s["trig"]]
        DISPLAY.text("%sS/s %s T%s%s" % (fmt(rate, ""), ("1k", "4k", "16k")[s["size"]], trig,
                                        NAMES[s["tch"]] if s["trig"] else ""), 2, 2, FG)
        st_color = {"STOP": MID, "ARMED": 0xFD20, "RUN": 0x07E0}[self.state]
        DISPLAY.text(self.state, _W - 8 * len(self.state) - 2, 2, st_color)
        if s["src"]:
            DISPLAY.text("DEMO", _W - 8 * len(self.state) - 42, 2, 0xF800)

        nch = len(CH_BITS)
        dec = s["dec"] != 0
        avail = _H - _TOP - 20 - (14 if dec else 0)
        lane_h = min(30, avail // nch)

        # ---- grid
        for gx in range(40, _W, 40):
            for gy in range(_TOP, _TOP + lane_h * nch, 4):
                DISPLAY.pixel(gx, gy, GRID)

        if not self.n:
            center_text("no capture yet", _TOP + 20, MID)
        else:
            self.draw_lanes(lane_h)
            if self.trig_idx >= 0:
                tx = self.x_of(self.trig_idx)
                if 0 <= tx < _W:
                    for gy in range(_TOP, _TOP + lane_h * nch, 2):
                        DISPLAY.pixel(tx, gy, 0xF800)
            if dec:
                self.draw_decoded(_TOP + lane_h * nch + 1)

        # ---- channel labels
        for c in range(nch):
            ly = _TOP + c * lane_h + (lane_h - 10) // 2
            DISPLAY.rect(0, ly - 1, 8 * len(NAMES[c]) + 2, 10, BG_DARK, fill=True)
            DISPLAY.text(NAMES[c], 1, ly, CH_COLORS[c])

        # ---- bottom info
        y = _H - 19
        DISPLAY.hline(0, y - 2, _W, GRID)
        x = 0
        for c, (freq, duty) in enumerate(self.meas):
            t = "%s %d%%" % (fmt(freq, "Hz"), duty) if freq else ("high" if duty > 50 else "low")
            DISPLAY.text(t, x, y, CH_COLORS[c])
            x += _W // max(1, len(self.meas))
        if self.n:
            per = self.period_ns * 1e-9
            div = 40 * per * (1 << self.zoom if self.zoom >= 0 else 1 / (1 << -self.zoom))
            t0 = (self.view - max(0, self.trig_idx)) * per
            info = "%s/div  t=%s" % (fmt(div, "s"), fmt(t0, "s"))
        else:
            info = ""
        DISPLAY.text(self.msg or info, 0, y + 10, MID if self.msg else FG)
        DISPLAY.show()

    def draw_lanes(self, lane_h):
        summ = self.summ
        if self.zoom >= 0:
            PARAMS[0] = self.view
            PARAMS[1] = 1 << self.zoom
            PARAMS[2] = _W
            PARAMS[3] = self.n
            _summary(self.buf, PARAMS, summ)
        else:
            pps = 1 << -self.zoom
            for x in range(_W):
                idx = self.view + x // pps
                if idx < self.n:
                    v = self.buf[idx]
                    summ[2 * x] = v
                    summ[2 * x + 1] = v
                else:
                    summ[2 * x] = 0
                    summ[2 * x + 1] = 0xFF
        for c, bit in enumerate(CH_BITS):
            top = _TOP + c * lane_h
            yh = top + 3
            yl = top + lane_h - 4
            color = CH_COLORS[c]
            run_start = 0
            run_lvl = -1
            for x in range(_W + 1):
                if x < _W:
                    o = summ[2 * x]
                    a = summ[2 * x + 1]
                    if a & bit and not o & bit:
                        lvl = 3
                    elif a & bit:
                        lvl = 1
                    elif not o & bit:
                        lvl = 0
                    else:
                        lvl = 2
                else:
                    lvl = -2
                if lvl == 2:
                    DISPLAY.vline(x, yh, yl - yh + 1, color)
                if lvl != run_lvl:
                    if run_lvl == 1:
                        DISPLAY.hline(run_start, yh, x - run_start, color)
                    elif run_lvl == 0:
                        DISPLAY.hline(run_start, yl, x - run_start, color)
                    if (run_lvl == 0 and lvl == 1) or (run_lvl == 1 and lvl == 0):
                        DISPLAY.vline(x, yh, yl - yh + 1, color)
                    run_start = x
                    run_lvl = lvl

    def draw_decoded(self, y):
        h = 12
        for s, e, label in self.decoded:
            x0 = self.x_of(s)
            x1 = self.x_of(e)
            if x1 < 0 or x0 >= _W:
                continue
            if s == e:  # I2C START (green) / STOP (red) marker
                if 0 <= x0 < _W:
                    DISPLAY.vline(x0, y - 1, h + 2, 0x07E0 if label == "S" else 0xF800)
                continue
            cx0 = max(0, x0)
            cx1 = min(_W - 1, x1)
            width = cx1 - cx0
            if width < 2:
                DISPLAY.vline(cx0, y + 2, h - 4, MID)
                continue
            DISPLAY.rect(cx0, y, width + 1, h, BG_DARK, fill=True)
            DISPLAY.rect(cx0, y, width + 1, h, MID)
            if len(label) * 8 > width - 2 and len(label) > 2:
                label = label[1:3] if label[0] in "RW" else label[:2]  # short form
            tw = len(label) * 8
            if tw <= width - 2:
                tx = max(cx0 + 1, min(cx1 - tw, (x0 + x1 - tw) // 2))
                DISPLAY.text(label, tx, y + 2, WHITE)

    # ---------------------------------------------------------------- settings
    def settings(self):
        sel = 0
        old = dict(self.s)
        while True:
            keys = INPUT.get_new_keys()
            if "TAB" in keys or "ENT" in keys or "ESC" in keys:
                break
            for k in keys:
                if k in ("UP", ";"):
                    sel = (sel - 1) % len(SETTINGS)
                elif k in ("DOWN", "."):
                    sel = (sel + 1) % len(SETTINGS)
                elif k in ("LEFT", ",", "RIGHT", "/"):
                    key = SETTINGS[sel][1]
                    step = -1 if k in ("LEFT", ",") else 1
                    self.s[key] = (self.s[key] + step) % len(SETTINGS[sel][2])

            DISPLAY.fill(BG)
            DISPLAY.rect(0, 0, _W, 11, BG_DARK, fill=True)
            DISPLAY.text("Settings", 2, 2, FG)
            DISPLAY.text(";. pick  ,/ change", 88, 2, MID)
            rows = 8
            first = min(max(0, sel - rows // 2), len(SETTINGS) - rows)
            for r in range(rows):
                i = first + r
                name, key, opts = SETTINGS[i]
                y = 15 + r * 15
                if i == sel:
                    DISPLAY.rect(0, y - 3, _W, 14, BG_DARK, fill=True)
                    DISPLAY.rect(0, y - 3, _W, 14, FG)
                DISPLAY.text(name, 6, y, FG if i == sel else MID)
                val = opts[self.s[key]]
                if i == sel:
                    val = "< %s >" % val
                DISPLAY.text(val, _W - 6 - 8 * len(val), y, WHITE)
            DISPLAY.show()
            time.sleep_ms(15)

        if self.s["pull"] != old["pull"] or self.s["tout"] != old["tout"]:
            self.apply_pins()
        if self.s != old:
            if self.n and (self.s["dec"] != old["dec"] or self.s["baud"] != old["baud"]
                           or self.s["uch"] != old["uch"]):
                if self.s["src"]:
                    self.capture()
                else:
                    self.analyze()
        self.msg = ""

    # ---------------------------------------------------------------- main loop
    def run(self):
        redraw = True
        while True:
            keys = INPUT.get_new_keys()
            if "ESC" in keys or "G0" in keys:
                if self.pwm:
                    self.pwm.deinit()
                machine.reset()
                return
            for k in keys:
                redraw = True
                if k == "SPC":
                    self.state = "STOP" if self.state == "RUN" else "RUN"
                    self.msg = ""
                elif k == "ENT":
                    self.state = "ARMED"
                    self.msg = ""
                elif k in ("LEFT", ","):
                    self.view -= self.visible_samples() // 4
                elif k in ("RIGHT", "/"):
                    self.view += self.visible_samples() // 4
                elif k == "<":
                    self.view -= max(1, self.visible_samples() // 30)
                elif k == "?":
                    self.view += max(1, self.visible_samples() // 30)
                elif k in ("UP", ";"):
                    self.set_zoom(self.zoom - 1)
                elif k in ("DOWN", "."):
                    self.set_zoom(self.zoom + 1)
                elif k == "g" and self.trig_idx >= 0:
                    self.center_on(self.trig_idx)
                elif k == "s":
                    self.msg = "saving..."
                    self.draw()
                    try:
                        self.msg = self.save_vcd()
                    except Exception as e:  # noqa: BLE001
                        self.msg = "save failed: %s" % e
                elif k == "TAB":
                    self.settings()
                self.clamp_view()

            if self.state in ("RUN", "ARMED"):
                self.draw()  # show ARMED/RUN state before blocking capture
                self.msg = ""
                if self.capture():
                    if self.state == "ARMED":
                        self.state = "STOP"
                else:
                    self.msg = "waiting for trigger..."
                redraw = True

            if redraw:
                self.draw()
                redraw = False
            time.sleep_ms(10)


Analyzer().run()
