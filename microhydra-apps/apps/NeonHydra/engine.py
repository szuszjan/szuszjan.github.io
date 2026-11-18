"""NEON HYDRA - 4 channel soft synth + tracker-style sequencer.

The sequencer runs inside MicroHydra's I2S audio callback, so every note is
placed with sample accuracy no matter how slow the graphics are.

Channels: 0 bass (saw), 1 arpeggio (pulse 25%), 2 lead (square / PWM / triangle), 3 drums.
"""

import math
import random
import time
from array import array

from lib.audio import Audio
from lib.audio.i2ssound import I2SSound, Register, Sample


_RATE = const(11025)
_BUF = const(2048)
_TICK = const(221)          # samples per tick (~50 Hz)
_TPR = const(6)             # ticks per row
_ROW = const(1326)          # samples per row
_BAR_TICKS = const(96)      # 16 rows * 6 ticks
_WAVE = const(42)           # samples per waveform period (= C4 at native rate)
_AMP = const(9000)

_HOLD = const(-1)
_OFF = const(-2)

CH_BASS = const(0)
CH_ARP = const(1)
CH_LEAD = const(2)
CH_DRUM = const(3)

NOTE_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_to_midi(tok):
    pc = NOTE_PC[tok[0]]
    if tok[1] == "#":
        pc += 1
    return 12 * (int(tok[-1]) + 1) + pc


def parse_melody(bar):
    out = []
    for tok in bar.split():
        out.append(_HOLD if tok == "-" else _OFF if tok == "." else note_to_midi(tok))
    return out


def parse_bass(bar):
    out = []
    for tok in bar.split():
        out.append(_HOLD if tok == "-" else _OFF if tok == "." else int(tok))
    return out


# ---------------------------------------------------------------- samples
def _make(values):
    a = array("h", values)
    return Sample(memoryview(bytearray(a)))


def make_waves():
    w = {}
    half = _WAVE // 2
    w["saw"] = _make([int(_AMP * (2 * i / _WAVE - 1)) for i in range(_WAVE)])
    w["tri"] = _make([int(_AMP * 1.4 * (2 * abs(2 * i / _WAVE - 1) - 1)) for i in range(_WAVE)])
    w["sq"] = _make([_AMP if i < half else -_AMP for i in range(_WAVE)])
    w["p25"] = _make([_AMP if i < _WAVE // 4 else -_AMP for i in range(_WAVE)])
    # PWM sweep: duty 8% .. 50% .. 8%
    duties = (4, 6, 9, 12, 15, 18, 21, 18, 15, 12, 9, 6)
    w["pwm"] = [_make([_AMP if i < d else -_AMP for i in range(_WAVE)]) for d in duties]
    return w


def make_drums(step_cb=None):
    """Synthesize drum samples (kick, snare, hats, crash). ~0.5 s on device."""
    rnd = random.getrandbits
    exp = math.exp
    sin = math.sin
    d = {}

    def noise():
        return rnd(16) - 32768

    # kick: pitch drop 300 -> 50 Hz + click
    n = 1800
    v = []
    ph = 0.0
    for i in range(n):
        t = i / _RATE
        f = 50 + 260 * exp(-t * 30)
        ph += 6.2832 * f / _RATE
        s = sin(ph) * exp(-t * 9) * 15000
        if i < 40:
            s += noise() * 0.25 * (1 - i / 40)
        v.append(int(max(-32000, min(32000, s))))
    kick = v
    d["k"] = _make(kick)
    if step_cb:
        step_cb()

    # snare: noise + 185 Hz body
    n = 2400
    v = []
    prev = 0
    for i in range(n):
        t = i / _RATE
        nz = noise()
        hp = nz - prev
        prev = nz
        s = hp * 0.22 * exp(-t * 16) + sin(6.2832 * 185 * t) * 9000 * exp(-t * 28)
        v.append(int(max(-32000, min(32000, s))))
    d["s"] = _make(v)
    if step_cb:
        step_cb()

    # hats (high passed noise)
    for key, n, dec, amp in (("h", 520, 85, 0.22), ("o", 2200, 11, 0.16)):
        v = []
        prev = 0
        for i in range(n):
            t = i / _RATE
            nz = noise()
            s = (nz - prev) * amp * exp(-t * dec)
            prev = nz
            v.append(int(max(-32000, min(32000, s))))
        d[key] = _make(v)
        if step_cb:
            step_cb()

    # crash = kick + long noise
    n = 4400
    v = []
    prev = 0
    for i in range(n):
        t = i / _RATE
        nz = noise()
        s = (nz - prev) * 0.15 * exp(-t * 4.5)
        prev = nz
        if i < len(kick):
            s += kick[i]
        v.append(int(max(-32000, min(32000, s))))
    d["c"] = _make(v)
    if step_cb:
        step_cb()
    return d


# drum volume offsets
DRUM_REL = {"k": 0, "s": 0, "h": -2, "o": -2, "c": 0}


class Section:
    def __init__(self, d):
        self.name = d["name"]
        self.tr = d.get("tr", 0)
        self.bass = [parse_bass(b) if b else None for b in d.get("bass") or (None,)]
        self.drums = list(d.get("drums") or (None,))
        self.drel = d.get("drel", (0,))
        lead = d.get("lead")
        self.lead = [parse_melody(b) for b in lead] if lead else None
        self.lead_oct = d.get("lead_oct", 0)
        self.lead_inst = d.get("lead_inst", "sq")
        self.arp = d.get("arp")
        self.arel = d.get("arel", (0,))
        self.arp_oct = d.get("arp_oct", (0,))
        self.crash = d.get("crash", False)


class Engine(Audio):
    """Audio driver + sequencer. Use start(), seek_bar(), heard(), rows()."""

    def __init__(self, song, config, waves, drums):
        # attributes must exist before I2SSound.__init__ calls _process_buffer
        self.ready = False
        self.playing = False
        self.fill_pos = 0
        self.cb_us = time.ticks_us()
        self.cfg = config
        self.waves = waves
        self.drums = drums
        self.secs = [Section(s) for s in song.SECTIONS]
        self.bars = []  # (pc, minor, section index, bar in section)
        for si, sec in enumerate(song.SECTIONS):
            prog = sec["prog"]
            for b in range(sec["bars"]):
                pc, minor = song.CHORDS[prog[b % len(prog)]]
                self.bars.append((pc, minor, si, b))
        self.nbars = len(self.bars)
        self.loop_bars = self.nbars + song.TAIL_BARS
        self.ratio = [2 ** ((m - 60) / 12) for m in range(128)]
        # voices: [sample, midi, vol, phase, time, ratio]
        self.voice = [[None, 0, 0, 0.0, 0, 1.0] for _ in range(4)]
        self.lead_start = 0
        self.lead_vol = 0
        self.lead_note = -1
        self.hits = []
        self.master = 2
        self.tick_n = 0
        self.next_tick = 0
        self.origin = 0
        super().__init__(buf_size=_BUF, rate=_RATE, channels=4)
        self.ready = True

    # ------------------------------------------------------------ timing API
    def start(self):
        self.tick_n = 0
        self.next_tick = self.fill_pos + 256
        self.origin = self.next_tick
        self.playing = True

    def heard(self):
        """Sample index (absolute) that is playing on the speaker right now (estimate)."""
        el = time.ticks_diff(time.ticks_us(), self.cb_us)
        if el > 400_000:
            el = 400_000
        return self.fill_pos - 2 * _BUF - 512 + el * _RATE // 1_000_000

    def rows(self):
        """Song position in rows (float), wraps with the song loop."""
        r = (self.heard() - self.origin) / _ROW
        return r % (self.loop_bars * 16) if r > 0 else r

    def seek_bar(self, bar):
        loops = self.tick_n // (self.loop_bars * _BAR_TICKS)
        self.tick_n = (loops * self.loop_bars + bar) * _BAR_TICKS
        self.origin = self.next_tick - self.tick_n * _TICK
        for ch in range(4):
            self._off(ch, 0, self.next_tick)

    # ------------------------------------------------------------ audio callback
    def _process_buffer(self, arg):
        if self.ready:
            start = self.fill_pos
            end = start + _BUF
            if self.playing:
                try:
                    while self.next_tick < end:
                        self._tick(self.next_tick - start, self.next_tick)
                        self.next_tick += _TICK
                except Exception as e:  # noqa: BLE001
                    self.playing = False
                    print("sequencer error:", e)
            self.fill_pos = end
            self.cb_us = time.ticks_us()
        I2SSound._process_buffer(self, arg)

    # ------------------------------------------------------------ voices
    def _vol(self, rel):
        v = 7 + self.master + rel
        return 15 if v > 15 else (0 if v < 0 else v)

    def _note(self, ch, off, at, smp, midi, vol, keep_phase=True):
        v = self.voice[ch]
        if keep_phase and v[0] is not None:
            ph = (v[3] + (at - v[4]) * v[5]) % _WAVE
        else:
            ph = 0.0
        r = self.ratio[midi]
        v[0] = smp
        v[1] = midi
        v[2] = vol
        v[3] = ph
        v[4] = at
        v[5] = r
        octave = midi // 12 - 1
        self._queues[ch].append(Register(
            buf_start=off, sample=smp, pointer=int(ph), note=midi % 12,
            period_mult=1 << (octave - 1 if octave > 0 else 0), loop=True, volume=vol))

    def _off(self, ch, off, at):
        if self.voice[ch][0] is not None:
            self.voice[ch][0] = None
            self._queues[ch].append(Register(buf_start=off))

    def _drum(self, off, smp, vol):
        self._queues[CH_DRUM].append(Register(
            buf_start=off, sample=smp, note=0, period_mult=8, loop=False, volume=vol))

    # ------------------------------------------------------------ sequencer
    def _tick(self, off, at):
        t = self.tick_n
        self.tick_n = t + 1
        t %= self.loop_bars * _BAR_TICKS
        row = t // _TPR
        sub = t - row * _TPR
        bar = row >> 4
        step = row & 15

        if bar >= self.nbars:  # tail: silence
            if sub == 0 and step == 0:
                for ch in range(3):
                    self._off(ch, off, at)
            return

        pc, minor, si, bis = self.bars[bar]
        sec = self.secs[si]
        tr = sec.tr

        if sub == 0:
            self.master = self.cfg["volume"]
            # ---- drums
            dp = sec.drums[bis % len(sec.drums)]
            if dp:
                d = dp[step]
                if step == 0 and bis == 0 and sec.crash:
                    d = "c"
                if d != ".":
                    rel = sec.drel[bis % len(sec.drel)] + DRUM_REL[d]
                    self._drum(off, self.drums[d], self._vol(rel))
                    hits = self.hits
                    hits.append((at, d))
                    if len(hits) > 24:
                        hits.pop(0)
            # ---- bass
            bp = sec.bass[bis % len(sec.bass)]
            if bp is None:
                self._off(CH_BASS, off, at)
            else:
                tok = bp[step]
                if tok == _OFF:
                    self._off(CH_BASS, off, at)
                elif tok != _HOLD:
                    root = 45 + (pc - 9) % 12
                    self._note(CH_BASS, off, at, self.waves["saw"], root + tok + tr, self._vol(0), False)
            # ---- lead
            if sec.lead:
                tok = sec.lead[bis % len(sec.lead)][step]
                if tok == _OFF:
                    self._off(CH_LEAD, off, at)
                    self.lead_note = -1
                elif tok != _HOLD:
                    self.lead_note = tok + tr + sec.lead_oct
                    self.lead_start = t
                    self.lead_vol = self._vol(0)
                    self._note(CH_LEAD, off, at, self._lead_wave(sec, 0), self.lead_note,
                               self.lead_vol, False)
            elif self.lead_note >= 0:
                self._off(CH_LEAD, off, at)
                self.lead_note = -1

        # ---- lead: envelope + PWM sweep (phase continuous)
        if self.lead_note >= 0 and sec.lead:
            age = t - self.lead_start
            if age > 0 and (age == 4 or (sec.lead_inst == "pwm" and age % 2 == 0)):
                vol = self.lead_vol - (1 if age >= 4 else 0)
                self._note(CH_LEAD, off, at, self._lead_wave(sec, age), self.lead_note, vol)

        # ---- arpeggio
        if sec.arp:
            third = 3 if minor else 4
            chord = (0, third, 7, 12)
            base = 57 + (pc - 9) % 12 + tr + sec.arp_oct[bis % len(sec.arp_oct)]
            rel = sec.arel[bis % len(sec.arel)]
            if sec.arp == "fast":
                accent = 0 if (sub < 2 and step % 2 == 0) else -1
                self._note(CH_ARP, off, at, self.waves["p25"], base + chord[t % 4],
                           self._vol(rel + accent))
            elif sub == 0:
                # slow broken chord: up and down
                seq = (0, 1, 2, 3, 2, 1)
                self._note(CH_ARP, off, at, self.waves["tri"], base + chord[seq[row % 6]],
                           self._vol(rel), False)
        else:
            self._off(CH_ARP, off, at)

    def _lead_wave(self, sec, age):
        inst = sec.lead_inst
        if inst == "pwm":
            pw = self.waves["pwm"]
            return pw[(age // 2) % len(pw)]
        return self.waves[inst]
