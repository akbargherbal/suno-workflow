#!/usr/bin/env python3
"""Careful, dependency-free ABC parser for transcribed (audio -> ABC) scores.

Turns an ABC file into timed note events with *absolute pitch in cents* so that
downstream code can reason about pitch classes, durations, phrase endings and key
changes. It is not a full ABC implementation.

Handled
  voices (V:), per-voice M:/L:/K: changes (own line or inline [K:..]), key signatures
  and modes, accidentals (^ ^^ _ __ = and ABC 2.1 quarter tones ^/ _/) with bar-long
  memory, octave marks, durations (n, /, //, /n, n/m), ties, rests (z x), multi-measure
  rests (Z X), chords [CEG], tuplets, broken rhythm (> <), chord symbols "Gm",
  '%' comments (kept as section labels such as "% chorus").
  ABC 2.1 fractional accidentals (^/ _/ ^3/2 _3/2), key-field accidentals (K:D exp _e/ _b/),
  P: part labels, several tunes per file (parse_abc_all), Q: tempo with beat unit.
Ignored (warning issued): grace notes {}, decorations !..! / +..+, voice overlay &, '%%' directives,
  and any character the tokenizer does not understand (listed in the warnings).

Self-check
  Each bar's summed duration is compared with the meter. `bar_match_ratio` is the share
  of bars that match. A low ratio means the parse (lengths / meters / ties) is untrustworthy.

Usage:  python abc_parse.py score.abc [--json]
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from fractions import Fraction

LETTER_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
SHARP_ORDER = "FCGDAEB"
FLAT_ORDER = "BEADGCF"
MODE_OFFSET = {"": 0, "maj": 0, "ion": 0, "m": -3, "min": -3, "aeo": -3,
               "mix": -1, "dor": -2, "phr": -4, "loc": -5, "lyd": 1}
FIFTHS_BASE = {"F": -1, "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5}
ACC_PAT = r"\^\^|\^\d+/\d+|\^/|\^|__|_\d+/\d+|_/|_|="     # longest alternatives first
_ACC_FIXED = {"^^": 200, "^/": 50, "^": 100, "__": -200, "_/": -50, "_": -100, "=": 0}


def acc_cents(tok: str) -> float:
    """'^' -> 100, '_/' -> -50, '_3/2' -> -150 (ABC 2.1: n/d of a semitone)."""
    if tok in _ACC_FIXED:
        return _ACC_FIXED[tok]
    m = re.match(r"^([\^_])(\d+)/(\d+)$", tok)
    if m and int(m.group(3)):
        return (1 if m.group(1) == "^" else -1) * 100.0 * int(m.group(2)) / int(m.group(3))
    return 0.0


@dataclass
class Note:
    voice: str
    start: float      # quarter-note units from the start of that voice
    dur: float        # quarter-note units (tied notes merged)
    cents: float      # absolute pitch: MIDI*100 (+/- quarter-tone offsets); C4 = 6000
    bar: int
    section: str
    key: str          # key signature in force (as written in K:)
    chord: str = ""   # most recent chord symbol in that voice


@dataclass
class Score:
    path: str
    voices: dict = field(default_factory=dict)       # id -> display name
    notes: list = field(default_factory=list)
    rests: list = field(default_factory=list)        # (voice, start, dur)
    chords: list = field(default_factory=list)       # (voice, start, symbol, section)
    keys: list = field(default_factory=list)         # (voice, start, key string) for mid-file changes
    sections: list = field(default_factory=list)     # (label, voice, start)
    tempo_bpm: float | None = None
    declared_key: str = ""
    warnings: list = field(default_factory=list)
    bars_total: int = 0
    bars_matching: int = 0
    bar_mismatches: list = field(default_factory=list)
    title: str = ""
    source: str = "abc"          # "abc" | "midi" | "musicxml"  (bar check only applies to abc)
    n_tunes: int = 1

    @property
    def bar_match_ratio(self) -> float:
        if not self.bars_total:
            return 1.0 if self.source != "abc" else 0.0
        return self.bars_matching / self.bars_total


# --------------------------------------------------------------------------- helpers
KEY_ACC = re.compile(r"^(" + ACC_PAT + r")([A-Ga-g])$")


def key_signature(key: str, warn=None) -> dict:
    """Key field -> {LETTER: cents}.  'Gm' -> {'B': -100, 'E': -100}.  Handles modes, 'exp'
    (explicit: only the listed accidentals apply) and extra accidentals ('K:D _e/ _b/')."""
    k = key.strip()
    if not k or k.lower().startswith(("none", "hp")):
        return {}
    toks = k.split()
    m = re.match(r"^([A-Ga-g])([#b]?)([A-Za-z]*)$", toks[0])
    if not m:
        if warn:
            warn(f"key '{k}' not understood; assuming no key signature")
        return {}
    letter, acc, mode = m.group(1).upper(), m.group(2), m.group(3).lower()
    rest = toks[1:]
    explicit = False
    if not mode and rest and re.match(r"^[A-Za-z]+$", rest[0]) and rest[0].lower() != "exp":
        mode = rest[0].lower()
        rest = rest[1:]
    if rest and rest[0].lower() == "exp":
        explicit = True
        rest = rest[1:]
    mode = mode[:3] if mode[:3] in MODE_OFFSET else mode
    if mode not in MODE_OFFSET:
        mode = "m" if mode.startswith("m") else ""
    sig = {}
    if not explicit:
        fifths = FIFTHS_BASE[letter] + (7 if acc == "#" else -7 if acc == "b" else 0) + MODE_OFFSET[mode]
        if fifths > 0:
            for l in SHARP_ORDER[:min(fifths, 7)]:
                sig[l] = 100
        elif fifths < 0:
            for l in FLAT_ORDER[:min(-fifths, 7)]:
                sig[l] = -100
    for t in rest:
        t = re.sub(r"^([\^_])([A-Ga-g])/$", r"\1/\2", t)     # lenient: '_e/' means '_/e'
        am = KEY_ACC.match(t)
        if am:
            sig[am.group(2).upper()] = acc_cents(am.group(1))
        elif warn:
            warn(f"key-field token '{t}' ignored")
    return sig


def parse_tempo(val: str):
    """Q: field -> quarter-note beats per minute (None if not understood)."""
    m = re.search(r"(?:(\d+)\s*/\s*(\d+))?\s*=\s*(\d+(?:\.\d+)?)", val)
    if m:
        unit = int(m.group(1)) / int(m.group(2)) if m.group(1) and int(m.group(2)) else 0.25
        return float(m.group(3)) * unit * 4.0
    m = re.match(r'^\s*(?:"[^"]*"\s*)?(\d+)\s*$', val)
    return float(m.group(1)) if m else None


def strip_comment(line: str) -> str:
    inq = False
    for i, ch in enumerate(line):
        if ch == '"':
            inq = not inq
        elif ch == "%" and not inq:
            return line[:i]
    return line


def meter_quarters(m: str) -> float:
    m = m.strip()
    if m in ("C", "C|"):
        return 4.0
    mm = re.match(r"^(\d+)\s*/\s*(\d+)", m)
    return int(mm.group(1)) * 4.0 / int(mm.group(2)) if mm else 4.0


def unit_quarters(l: str) -> float:
    mm = re.match(r"^(\d+)\s*/\s*(\d+)", l.strip())
    return int(mm.group(1)) * 4.0 / int(mm.group(2)) if mm else 0.5


def default_unit(meter_q: float) -> float:
    # ABC default: 1/8 if meter >= 3/4, else 1/16  (in quarter-note units)
    return 0.5 if meter_q >= 3.0 else 0.25


def parse_len(tok: str) -> Fraction:
    """'' -> 1 ; '4' -> 4 ; '/' -> 1/2 ; '//' -> 1/4 ; '3/2' -> 3/2 ; '/3' -> 1/3"""
    if not tok:
        return Fraction(1)
    m = re.match(r"^(\d*)(/*)(\d*)$", tok)
    if not m:
        return Fraction(1)
    num, slashes, den = m.groups()
    n = Fraction(int(num)) if num else Fraction(1)
    if not slashes:
        return n
    return n / int(den) if den else n / (2 ** len(slashes))


def _cents(letter, acc, octmarks, sig, bar_acc):
    base = LETTER_SEMITONE[letter.upper()]
    octave = (4 if letter.isupper() else 5) + octmarks.count("'") - octmarks.count(",")
    key = (letter.upper(), octave)
    if acc:
        off = acc_cents(acc)
        bar_acc[key] = off
    elif key in bar_acc:
        off = bar_acc[key]
    else:
        off = sig.get(letter.upper(), 0)
    return (octave + 1) * 1200 + base * 100 + off


TOKEN = re.compile(r"""
    (?P<inline>\[[A-Za-z]:[^\]]*\])
  | (?P<chordsym>"[^"]*")
  | (?P<deco>![^!]*!|\+[^+\s]*\+)
  | (?P<grace>\{[^}]*\})
  | (?P<tuplet>\(\d(?::\d?)?(?::\d?)?)
  | (?P<bar>(?:\|\]|\[\||\|\||:\||\|:|::|\|)\d?)
  | (?P<volta>\[\d+(?:[,-]\d+)*)
  | (?P<mrest>[ZX](?P<mrl>\d*))
  | (?P<rest>[zx](?P<rl>\d*(?:/+\d*)?))
  | (?P<chord>\[(?P<cin>[^\]]*)\](?P<cl>\d*(?:/+\d*)?))
  | (?P<note>(?P<acc>\^\^|\^\d+/\d+|\^/|\^|__|_\d+/\d+|_/|_|=)?(?P<let>[A-Ga-g])(?P<oct>[,']*)(?P<nl>\d*(?:/+\d*)?))
  | (?P<tie>-)
  | (?P<broken>[<>]+)
  | (?P<amp>&)
  | (?P<ignore>[\s().~\\])
  | (?P<other>.)
""", re.X)
KINDS = ("inline", "chordsym", "deco", "grace", "tuplet", "bar", "volta", "mrest", "rest", "chord",
         "note", "tie", "broken", "amp", "ignore", "other")
NOTE_IN_CHORD = re.compile(r"(" + ACC_PAT + r")?([A-Ga-g])([,']*)")


class _Voice:
    def __init__(self, vid, meter, unit, key, warn=None):
        self.vid, self.meter, self.unit, self.key = vid, meter, unit, key
        self.sig = key_signature(key, warn)
        self.t = 0.0
        self.bar = 0
        self.bar_dur = 0.0
        self.bar_started = False
        self.bar_acc = {}
        self.last_chord = ""
        self.last_note = None
        self.pending_tie = None
        self.tuplet = None
        self.broken = None


def split_tunes(text: str) -> list:
    """Split a multi-tune file at 'X:' lines. A file with 0 or 1 X: lines is one tune."""
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if re.match(r"^X:", l)]
    if len(starts) <= 1:
        return [text]
    starts.append(len(lines))
    return ["\n".join(lines[a:b]) for a, b in zip(starts, starts[1:])]


def parse_abc_all(path: str) -> list:
    """One Score per tune in the file (X:1, X:2, ...)."""
    text = open(path, encoding="utf-8", errors="replace").read()
    chunks = split_tunes(text)
    out = []
    for i, ch in enumerate(chunks):
        sc = _parse_text(ch, path)
        sc.n_tunes = len(chunks)
        out.append(sc)
    return out


def parse_abc(path: str) -> Score:
    """First tune of the file (a warning is added when the file holds several)."""
    tunes = parse_abc_all(path)
    sc = tunes[0]
    if len(tunes) > 1:
        sc.warnings.append(f"file holds {len(tunes)} tunes; only the first was parsed here (use parse_abc_all)")
    return sc


def _parse_text(text: str, path: str) -> Score:
    sc = Score(path=path)
    g_meter, g_unit, g_key = 4.0, None, ""
    other_chars: dict = {}
    in_header = True
    voices: dict[str, _Voice] = {}
    cur: _Voice | None = None
    section = ""

    def warn(msg):
        if msg not in sc.warnings:
            sc.warnings.append(msg)

    def voice(vid) -> _Voice:
        if vid not in voices:
            voices[vid] = _Voice(vid, g_meter, g_unit or default_unit(g_meter), g_key, warn)
        return voices[vid]

    def close_bar(v: _Voice):
        if v.bar_started:
            sc.bars_total += 1
            if abs(v.bar_dur - v.meter) < 1e-6:
                sc.bars_matching += 1
            elif len(sc.bar_mismatches) < 12:
                sc.bar_mismatches.append((v.vid, v.bar, round(v.bar_dur, 3), round(v.meter, 3)))
        v.bar += 1
        v.bar_dur = 0.0
        v.bar_acc = {}
        v.bar_started = False

    def apply_field(v: _Voice, name: str, val: str):
        if name == "M":
            v.meter = meter_quarters(val)
            if g_unit is None:
                v.unit = default_unit(v.meter)
        elif name == "L":
            v.unit = unit_quarters(val)
        elif name == "K":
            v.key = val.strip() or v.key
            v.sig = key_signature(val, warn)
            sc.keys.append((v.vid, round(v.t, 3), val.strip()))

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        ls = line.lstrip()
        if ls.startswith("%%") or ls.startswith("%abc"):
            continue                                    # directives ('%%MIDI program 40', '%%score') are not labels
        if ls.startswith("%"):
            lab = ls.lstrip("% \t").strip()
            if lab:
                section = lab
                sc.sections.append((lab, cur.vid if cur else "", round(cur.t, 3) if cur else 0.0))
            continue
        line = strip_comment(line).rstrip()
        if not line.strip():
            continue
        fm = re.match(r"^([A-Za-z]):\s*(.*)$", line)
        if fm:
            name, val = fm.group(1), fm.group(2)
            if name == "P":                             # ABC part label = section label
                if val.strip():
                    section = val.strip()
                    sc.sections.append((section, cur.vid if cur else "", round(cur.t, 3) if cur else 0.0))
                continue
            if name == "T" and not sc.title:
                sc.title = val.strip()
            if name == "V":
                vid = val.split()[0] if val.split() else "1"
                nm = re.search(r'name="([^"]*)"', val)
                if nm or vid not in sc.voices:
                    sc.voices[vid] = nm.group(1) if nm else vid
                cur = voice(vid)
                continue
            if in_header:
                if name == "M":
                    g_meter = meter_quarters(val)
                elif name == "L":
                    g_unit = unit_quarters(val)
                elif name == "Q":
                    sc.tempo_bpm = parse_tempo(val)
                elif name == "K":
                    parts = val.strip().split()
                    g_key = val.strip()                 # full field: mode and key accidentals matter
                    sc.declared_key = parts[0] if parts else ""
                    in_header = False
                    for v in voices.values():   # voices declared in header inherit header fields
                        v.meter = g_meter
                        v.unit = g_unit or default_unit(g_meter)
                        v.key, v.sig = g_key, key_signature(g_key, warn)
                continue
            if cur is None:
                cur = voice("1")
                sc.voices.setdefault("1", "1")
            if name in ("M", "L", "K"):
                apply_field(cur, name, val)
            elif name == "Q" and sc.tempo_bpm is None:
                sc.tempo_bpm = parse_tempo(val)
            continue

        # ------------------------------------------------------------ music line
        in_header = False
        if cur is None:
            cur = voice("1")
            sc.voices.setdefault("1", "1")
        v = cur
        for m in TOKEN.finditer(line):
            kind = next(k for k in KINDS if m.group(k) is not None)
            if kind == "inline":
                f = m.group("inline")[1:-1]
                apply_field(v, f[0], f[2:])
            elif kind == "chordsym":
                sym = m.group("chordsym").strip('"')
                if sym[:1] in "^_<>@" or not sym:       # ABC annotation, not a chord symbol
                    continue
                v.last_chord = sym
                sc.chords.append((v.vid, round(v.t, 3), v.last_chord, section))
            elif kind == "volta":
                pass                                    # '[1' '[2' repeat-ending markers carry no music
            elif kind == "other":
                other_chars[m.group(0)] = other_chars.get(m.group(0), 0) + 1
            elif kind == "grace":
                warn("grace notes ignored")
            elif kind == "deco":
                pass
            elif kind == "amp":
                warn("voice overlay '&' not supported")
            elif kind == "tuplet":
                spec = m.group("tuplet")[1:].split(":")
                p = int(spec[0])
                q = int(spec[1]) if len(spec) > 1 and spec[1] else {2: 3, 3: 2, 4: 3, 5: 2, 6: 2, 7: 2, 8: 3, 9: 2}.get(p, 2)
                r = int(spec[2]) if len(spec) > 2 and spec[2] else p
                v.tuplet = [r, Fraction(q, p)]
            elif kind == "bar":
                close_bar(v)               # note: pending_tie deliberately survives barlines
            elif kind == "broken":
                sym = m.group("broken")
                v.broken = (sym[0], len(sym))
                if v.last_note is not None:   # shorten/lengthen the previous note
                    d = 1 - 0.5 ** v.broken[1]
                    adj = (1 + d) if sym[0] == ">" else (1 - d)
                    shift = v.last_note.dur * adj - v.last_note.dur
                    v.last_note.dur += shift
                    v.t += shift
                    v.bar_dur += shift
            elif kind == "tie":
                v.pending_tie = v.last_note       # merge only if a '-' really follows the note
            elif kind == "mrest":
                n = int(m.group("mrl") or 1)
                dur = n * v.meter
                sc.rests.append((v.vid, round(v.t, 6), dur))
                v.t += dur
                sc.bars_total += n
                sc.bars_matching += n
                v.bar += n
                v.bar_dur, v.bar_started, v.bar_acc = 0.0, False, {}
                v.pending_tie = v.last_note = None
            elif kind in ("rest", "note", "chord"):
                lt = m.group({"rest": "rl", "chord": "cl", "note": "nl"}[kind])
                dur = float(parse_len(lt)) * v.unit
                if v.tuplet:
                    dur *= float(v.tuplet[1])
                    v.tuplet[0] -= 1
                    if v.tuplet[0] <= 0:
                        v.tuplet = None
                if v.broken:
                    d = 1 - 0.5 ** v.broken[1]
                    dur *= (1 - d) if v.broken[0] == ">" else (1 + d)
                    v.broken = None
                v.bar_started = True
                if kind == "rest":
                    sc.rests.append((v.vid, round(v.t, 6), dur))
                    v.t += dur
                    v.bar_dur += dur
                    v.pending_tie = v.last_note = None
                    continue
                if kind == "note":
                    pitches = [_cents(m.group("let"), m.group("acc"), m.group("oct") or "", v.sig, v.bar_acc)]
                else:
                    pitches = [_cents(c.group(2), c.group(1), c.group(3) or "", v.sig, v.bar_acc)
                               for c in NOTE_IN_CHORD.finditer(m.group("cin"))]
                    if not pitches:
                        continue
                if (v.pending_tie is not None and len(pitches) == 1
                        and abs(v.pending_tie.cents - pitches[0]) < 1e-6):
                    v.pending_tie.dur += dur          # tied continuation: extend, no new onset
                    v.t += dur
                    v.bar_dur += dur
                    v.pending_tie = None
                    continue
                v.pending_tie = None
                created = None
                for p in pitches:
                    created = Note(v.vid, round(v.t, 6), dur, p, v.bar, section, v.key, v.last_chord)
                    sc.notes.append(created)
                v.last_note = created if len(pitches) == 1 else None
                v.t += dur
                v.bar_dur += dur

    # flush the last (unterminated) bar of every voice
    for v in voices.values():
        close_bar(v)
    if other_chars:
        shown = ", ".join(f"{c!r}x{n}" for c, n in sorted(other_chars.items(), key=lambda kv: -kv[1])[:8])
        warn(f"unrecognised characters ignored: {shown}")
    return sc


def pc_name(cents: float) -> str:
    """Pitch-class label; quarter tones are shown as e.g. 'E+50' ."""
    pc = cents % 1200
    semis = round(pc / 100)
    off = pc - semis * 100
    name = NOTE_NAMES[semis % 12]
    return name if abs(off) < 1e-6 else f"{name}{off:+.0f}c"


def summary(sc: Score) -> str:
    lines = [f"file: {sc.path}", f"declared key: {sc.declared_key}  tempo: {sc.tempo_bpm}",
             f"voices: {sc.voices}", f"notes: {len(sc.notes)}  chords: {len(sc.chords)}  "
             f"key changes: {sc.keys}",
             (f"bar-check: {sc.bars_matching}/{sc.bars_total} bars match the meter ({100 * sc.bar_match_ratio:.1f}%)"
              if sc.source == "abc" else f"bar-check: n/a ({sc.source})")]
    if sc.bar_mismatches:
        lines.append(f"first mismatches (voice, bar, got, expected): {sc.bar_mismatches[:5]}")
    if sc.warnings:
        lines.append(f"warnings: {sc.warnings}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    score = parse_abc(sys.argv[1])
    if "--json" in sys.argv:
        d = asdict(score)
        d["bar_match_ratio"] = score.bar_match_ratio
        print(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        print(summary(score))
