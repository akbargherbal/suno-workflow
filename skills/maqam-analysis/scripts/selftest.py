#!/usr/bin/env python3
"""Self-test: generate synthetic ABC melodies in KNOWN maqamat and check the analyzer
recovers tonic and scale family. Run after installing or after editing the scripts:

    python selftest.py            # prints PASS/FAIL per case, exit code 1 on any failure
    python selftest.py --keep     # also leave the generated .abc files in ./selftest_out

What it proves: the parser, the scoring and the microtonal path work on clean data.
What it does NOT prove: accuracy on real transcriptions (those are noisy; see SKILL.md).
"""
from __future__ import annotations

import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from maqam_core import TEMPLATES                         # noqa: E402
from analyze_abc import analyze_file                     # noqa: E402

NAT = {0: "C", 2: "D", 4: "E", 5: "F", 7: "G", 9: "A", 11: "B"}


def abc_pitch(cents: int) -> str:
    """Absolute cents (C4 = 6000) -> ABC token with an explicit accidental on every note."""
    c = int(round(cents / 50.0)) * 50
    quarter = c % 100 == 50
    if quarter:
        up = (c + 50) // 100               # semitone above
        down = (c - 50) // 100
        if up % 12 in NAT:
            sym, semi = "_/", up
        else:
            sym, semi = "^/", down
    else:
        semi = c // 100
        sym = ""
    pc = semi % 12
    if pc in NAT:
        letter, acc = NAT[pc], ("=" if not quarter else sym)
    elif (pc + 1) % 12 in NAT:             # flat spelling
        letter, acc = NAT[(pc + 1) % 12], "_"
    else:
        letter, acc = NAT[(pc - 1) % 12], "^"
    octave = semi // 12 - 1
    base = letter if octave <= 4 else letter.lower()
    marks = ("'" * (octave - 5)) if octave > 5 else ("," * (4 - octave)) if octave < 4 else ""
    return f"{acc}{base}{marks}"


def make_abc(tonic_cents: int, degrees: list, seed: int, phrases: int = 36) -> str:
    rng = random.Random(seed)
    ladder = degrees + [degrees[0] + 1200]         # 8 steps: tonic .. upper tonic
    units = 0                                      # eighth-notes in current bar (8 per 4/4 bar)
    out = []

    def emit(tok, n):
        nonlocal units
        n = min(n, 8 - units)
        out.append(f"{tok}{n if n != 1 else ''}")
        units += n
        if units == 8:
            out.append("|")
            units = 0

    def rest(n):
        nonlocal units
        while n > 0:
            take = min(n, 8 - units)
            out.append(f"z{take if take != 1 else ''}")
            units += take
            n -= take
            if units == 8:
                out.append("|")
                units = 0

    for ph in range(phrases):
        pos = rng.choice([0, 2, 4, 4, 5])
        length = rng.randint(4, 7)
        for k in range(length):
            pos = max(0, min(7, pos + rng.choice([-2, -1, -1, 0, 1, 1, 2])))
            emit(abc_pitch(6000 + tonic_cents + ladder[pos]), rng.choice([1, 1, 2]))
        final = 0 if rng.random() < 0.65 else (4 if rng.random() < 0.7 else 2)
        emit(abc_pitch(6000 + tonic_cents + ladder[final]), rng.choice([2, 3]))
        rest(4)
    emit(abc_pitch(6000 + tonic_cents + ladder[0]), 8)   # last note = tonic, full bar
    if units:
        rest(8 - units)
    body = " ".join(out)
    return ("X:1\nT:synthetic\nM:4/4\nL:1/8\nQ:1/4=100\nV:Vocal clef=treble name=\"Vocal Melody\"\n"
            "K:none\nV:Vocal\n" + body + "\n")


# (case id, tonic in cents above C, template id, quarter tones kept?, expected tonic, expected label fragment)
CASES = [
    ("kurd-D-12tet",        200,  "kurd",       False, "D",  "Kurd"),
    ("hijaz-D-12tet",       200,  "hijaz",      False, "D",  "Hijaz"),
    ("nahawand-G-12tet",    700,  "nahawand",   False, "G",  "Nahawand"),
    ("ajam-C-12tet",        0,    "ajam",       False, "C",  "Ajam"),
    ("nikriz-C-12tet",      0,    "nikriz",     False, "C",  "Nikriz"),
    ("bayati-D-microtonal", 200,  "bayati",     True,  "D",  "Bayati"),
    ("rast-C-microtonal",   0,    "rast",       True,  "C",  "Rast"),
    ("saba-D-microtonal",   200,  "saba",       True,  "D",  "Saba"),
    ("hijaz-kar-D-micro",   200,  "hijaz_kar",  True,  "D",  "Hijaz Kar"),
    # Bayati written in plain 12-TET: Kurd/Nahawand-shaped; Bayati must show up as a possible reading
    ("bayati-D-rounded-12tet", 200, "bayati",   "round", "D", "Bayati"),
]


class _Args:
    voice = None
    phrase_gap = 1.0
    min_dur = 24.0
    no_sections = True


def run(keep=False):
    outdir = os.path.join(os.getcwd(), "selftest_out") if keep else tempfile.mkdtemp()
    os.makedirs(outdir, exist_ok=True)
    failures = 0
    for i, (cid, tonic, tid, micro, exp_tonic, exp_label) in enumerate(CASES):
        degs = list(TEMPLATES[tid][1])
        if micro == "round":                         # what a 12-TET transcriber would write
            degs = [int(round(d / 100.0 + 1e-9)) * 100 if d % 100 == 50 else d for d in degs]
            degs = [d - 100 if (d == 200 and tid == "bayati") else d for d in degs]   # E half-flat -> Eb
        elif not micro:
            degs = [d for d in degs]
        path = os.path.join(outdir, f"{cid}.abc")
        open(path, "w").write(make_abc(tonic, degs, seed=100 + i))
        sc, rep = analyze_file(path, _Args)
        g = rep["groups"][0]
        top = g["hypotheses"][0]
        labels = []
        for f in top["fits"]:
            if f["tied_with_best"]:
                labels.append(f["label"])
        ok_tonic = top["tonic"] == exp_tonic
        ok_label = any(exp_label == l or l.startswith(exp_label + " (") for l in labels)
        ok_parse = rep["bar_match_ratio"] >= 0.95
        status = "PASS" if (ok_tonic and ok_label and ok_parse) else "FAIL"
        failures += status == "FAIL"
        print(f"{status}  {cid:26s} tonic={top['tonic']:3s} (want {exp_tonic})  "
              f"shape={labels[:3]}  tonic_conf={g['tonic_confidence']:6s} shape_conf={g['shape_confidence']:6s} "
              f"parse={rep['bar_match_ratio']:.2f}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return failures


if __name__ == "__main__":
    sys.exit(1 if run("--keep" in sys.argv) else 0)
