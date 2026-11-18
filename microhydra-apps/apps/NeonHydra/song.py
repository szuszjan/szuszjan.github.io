"""NEON HYDRA - soundtrack data (original composition).

Tempo: 1 tick = 221 samples @ 11025 Hz (~50 Hz), 6 ticks per row (16th note),
16 rows per bar  ->  ~125 BPM, 1.92 s per bar.

Tokens in melody / bass strings (16 per bar):
  note name (E5, C#4 ...) or semitone offset (bass)  = new note
  -  = hold previous note
  .  = note off
Drum chars: k kick, s snare, h hat, o open hat, c crash(+kick), . nothing
"""

# chord name -> (pitch class, minor?)
CHORDS = {
    "Am": (9, 1), "F": (5, 0), "C": (0, 0), "G": (7, 0),
    "Em": (4, 1), "E": (4, 0), "Dm": (2, 1),
}

PROG_A = ("Am", "F", "C", "G")
PROG_B = ("F", "G", "Em", "Am", "F", "G", "Em", "E")
PROG_BREAK = ("Am", "Em", "F", "G", "Am", "Em", "F", "E")
PROG_BUILD = ("F", "G", "E", "E")
PROG_OUTRO = ("Am", "F", "C", "G", "Am", "F", "G", "Am")

# ---------------------------------------------------------------- melodies
MEL_A = (
    "E5 - - - D5 - C5 - D5 - E5 - - - A4 -",
    "C5 - - - A4 - - - F5 - E5 - D5 - C5 -",
    "E5 - - - G5 - - - E5 - D5 - C5 - - -",
    "D5 - - - B4 - - - G4 - - - B4 - D5 -",
    "E5 - - - D5 - C5 - D5 - E5 - - - A5 -",
    "G5 - F5 - E5 - - - C5 - - - D5 - E5 -",
    "G5 - - - E5 - C5 - E5 - G5 - C6 - - -",
    "B5 - - - - - - - A5 - G5 - B5 - D6 -",
)

MEL_B = (
    "A5 - - - G5 - F5 - - - E5 - F5 - - -",
    "G5 - - - D5 - - - B4 - D5 - G5 - - -",
    "E5 - - - G5 - B5 - - - A5 - G5 - E5 -",
    "A5 - - - - - - - E5 - - - A4 - - -",
    "C6 - - - A5 - F5 - A5 - C6 - D6 - C6 -",
    "B5 - - - G5 - D5 - G5 - B5 - D6 - - -",
    "E6 - - - D6 - B5 - G5 - - - E5 - G5 -",
    "G#5 - - - B5 - - - E6 - - - D6 - B5 -",
)

MEL_BREAK = (
    "A4 - - - - - - - C5 - - - E5 - - -",
    "B4 - - - - - - - G4 - - - E4 - - -",
    "A4 - - - - - - - C5 - - - F5 - - -",
    "D5 - - - - - - - - - - - B4 - - -",
    "C5 - - - - - - - E5 - - - A5 - - -",
    "G5 - - - - - - - E5 - - - B4 - - -",
    "C5 - - - - - - - A4 - - - F4 - - -",
    "G#4 - - - - - - - B4 - - - E5 - - -",
)

MEL_C = (
    "A5 - - - B5 - C6 - B5 - A5 - E5 - - -",
    "F5 - - - A5 - C6 - - - A5 - F5 - - -",
    "G5 - - - C6 - E6 - - - D6 - C6 - G5 -",
    "B5 - - - D6 - - - G6 - - - D6 - B5 -",
    "C6 - B5 - A5 - - - E6 - - - A5 - - -",
    "A5 - G5 - F5 - - - C6 - - - F5 - - -",
    "E6 - D6 - C6 - - - G6 - - - E6 - - -",
    "D6 - - - - - - - B5 - - - G5 - D6 -",
)

MEL_OUTRO = MEL_A[:4] + (
    "E5 - - - - - - - C5 - - - - - - -",
    "A4 - - - - - - - C5 - - - - - - -",
    "D5 - - - B4 - - - D5 - - - - - - -",
    "A4 - - - - - - - - - - - . . . .",
)

# ---------------------------------------------------------------- bass
B_INTRO = "0 - - - - - - - 0 - - - 7 - - -"
B_ROCK = "0 - 12 - 0 - 12 - 0 - 12 - 0 - 12 -"
B_FUNK = "0 - . 0 12 - 0 . 0 - . 0 12 - 7 12"
B_LONG = "0 - - - - - - - - - - - - - - -"
B_8TH = "0 - 0 - 0 - 0 - 0 - 0 - 0 - 0 -"
B_END = "0 - - - - - - - - - - - . . . ."

# ---------------------------------------------------------------- drums
D1 = "k.h.s.hkk.h.s.h."
D2 = "k.hhs.hkk.hhs.ho"
FILL1 = "k.h.s.hkk.s.ssss"
FILL2 = "k.hhs.hks.sss.ss"
HATS = "h.h.h.h.h.h.h.h."
HATSF = "h.h.h.h.h.hhhhhh"
DK = "k.......k......."
SN4 = "s...s...s...s..."
SN8 = "s.s.s.s.s.s.s.s."
SN16 = "ssssssssssssssss"
SN16E = "ssssssssssss...."
DEND = "c..............."

# ---------------------------------------------------------------- sections
# keys: name, prog, bars, tr (transpose), bass (list per bar, None = silent),
#       drums (list per bar), drel (drum volume per bar), lead (melody bars),
#       lead_oct, lead_inst ('sq', 'pwm', 'tri'), arp ('fast', 'slow', None),
#       arel (arp volume per bar), crash (crash on first beat), part (visual part)
SECTIONS = (
    dict(name="intro", prog=PROG_A, bars=8, tr=0,
         bass=(None, None, None, None, B_INTRO, B_INTRO, B_INTRO, B_INTRO),
         drums=(None, None, None, None, None, None, HATS, HATSF), drel=(-2,),
         lead=None, arp="fast", arel=(-5, -4, -3, -2, -1, -1, -1, -1), crash=False),
    dict(name="theme A", prog=PROG_A, bars=16, tr=0, bass=(B_ROCK,),
         drums=(D1, D1, D1, FILL1), drel=(0,), lead=MEL_A, lead_oct=0, lead_inst="sq",
         arp="fast", arel=(-1,), crash=True),
    dict(name="theme B", prog=PROG_B, bars=16, tr=0, bass=(B_FUNK,),
         drums=(D2, D2, D2, FILL2), drel=(0,), lead=MEL_B, lead_oct=0, lead_inst="pwm",
         arp="fast", arel=(-1,), crash=True),
    dict(name="break", prog=PROG_BREAK, bars=8, tr=0, bass=(B_LONG,),
         drums=(DK,), drel=(-2,), lead=MEL_BREAK, lead_oct=0, lead_inst="tri",
         arp="slow", arel=(-2,), crash=True),
    dict(name="build", prog=PROG_BUILD, bars=4, tr=0, bass=(B_8TH,),
         drums=(SN4, SN8, SN16, SN16E), drel=(-3, -2, -1, 0), lead=None,
         arp="fast", arel=(-2, -1, -1, 0), arp_oct=(0, 0, 12, 12), crash=False),
    dict(name="theme A2", prog=PROG_A, bars=16, tr=0, bass=(B_ROCK,),
         drums=(D2, D2, D2, FILL1), drel=(0,), lead=MEL_A, lead_oct=12, lead_inst="pwm",
         arp="fast", arel=(-1,), crash=True),
    dict(name="theme C", prog=PROG_A, bars=16, tr=2, bass=(B_FUNK,),
         drums=(D2, D2, D2, FILL2), drel=(0,), lead=MEL_C, lead_oct=0, lead_inst="pwm",
         arp="fast", arel=(-1,), crash=True),
    dict(name="outro", prog=PROG_OUTRO, bars=8, tr=0,
         bass=(B_INTRO, B_INTRO, B_INTRO, B_INTRO, B_INTRO, B_INTRO, B_INTRO, B_END),
         drums=(D1, D1, D1, FILL1, HATS, None, None, DEND), drel=(0, 0, 0, 0, -2, 0, 0, -1),
         lead=MEL_OUTRO, lead_oct=0, lead_inst="sq",
         arp="fast", arel=(-1, -1, -1, -1, -2, -2, -3, -4), crash=True),
)

# bars of silence after the song before it loops ("THE END" screen)
TAIL_BARS = 2
