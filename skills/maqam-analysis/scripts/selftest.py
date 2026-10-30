#!/usr/bin/env python3
"""Self-test: generate synthetic ABC melodies in KNOWN maqamat and check the analyzer
recovers tonic and scale family. Run after installing or after editing the scripts:

    python selftest.py            # prints PASS/FAIL per case, exit code 1 on any failure
    python selftest.py --keep     # also leave the generated .abc files in ./selftest_out

Sections
  1. template recovery   - music generated FROM the templates (circular by design: proves the plumbing)
  2. parser regressions  - quarter-tone accidentals, key-field accidentals, volta, %% lines, tempo, multi-tune
  3. importers           - MIDI (with pitch bend) and MusicXML round-trips keep the quarter tones
  4. guards              - quarter-tone tonic (Sikah-like), --brief keeps flags, tempo-normalised gaps,
                           duration-weighted chords, degenerate-audio refusal
  5. calibration         - perturbed synthetic music: overall accuracy and "label means something" checks
What it does NOT prove: accuracy on real transcriptions. Use evaluate.py with your own labelled files.
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


def make_abc(tonic_cents: int, degrees: list, seed: int, phrases: int = 36,
             p_final_tonic: float = 0.65, p_offscale: float = 0.0, drop_degree: int | None = None) -> str:
    """p_final_tonic: share of phrases that end on the tonic (rest end on 5th/3rd, as in pop).
    p_offscale: chance that a note is replaced by a chromatic neighbour (noisy transcription).
    drop_degree: index of a scale degree that is never sung."""
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
            if drop_degree is not None and pos % 7 == drop_degree:
                pos = min(7, pos + 1)
            c = ladder[pos] + (rng.choice([-100, 100]) if rng.random() < p_offscale else 0)
            emit(abc_pitch(6000 + tonic_cents + c), rng.choice([1, 1, 2]))
        final = 0 if rng.random() < p_final_tonic else (4 if rng.random() < 0.7 else 2)
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


# ============================================================================ extra sections
_RESULTS = []


def check(name, ok, detail=""):
    _RESULTS.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail and not ok else ""))
    return ok


def _tmp(name, text, mode="w"):
    d = tempfile.mkdtemp()
    path = os.path.join(d, name)
    with open(path, mode) as f:
        f.write(text)
    return path


class _A(_Args):
    no_sections = True
    phrase_gap = None


def section_parser():
    print("\n-- parser regressions")
    from abc_parse import parse_abc, parse_abc_all, key_signature, parse_tempo
    path = _tmp("p.abc", "X:1\nT:t\nM:4/4\nL:1/8\nQ:1/8=120\nK:D exp _e/ _b/\n%%MIDI program 40\n"
                         "% verse\nD2 E2 _3/2E2 F2 | [1 G4 A4 :|2 B4 d4 |]\n")
    sc = parse_abc(path)
    cents = [n.cents for n in sc.notes]
    check("key-field quarter-flat E applied", cents[1] == 6350, cents[:3])
    check("_3/2E = three-quarter-tone flat", cents[2] == 6250, cents[:3])
    check("volta [1 [2 do not break the bar check", sc.bar_match_ratio == 1.0, sc.bar_mismatches)
    check("%%MIDI line is not a section", [x[0] for x in sc.sections] == ["verse"], sc.sections)
    check("Q:1/8=120 -> 60 quarter-note bpm", sc.tempo_bpm == 60.0, sc.tempo_bpm)
    check("key_signature Gm in cents", key_signature("Gm") == {"B": -100, "E": -100})
    check("tempo with text", parse_tempo('"Allegro" 1/4=90') == 90.0)
    two = _tmp("m.abc", "X:1\nT:a\nM:4/4\nL:1/8\nK:C\nCDEF GABc|\nX:2\nT:b\nM:4/4\nL:1/8\nK:G\nGABc defg|\n")
    tunes = parse_abc_all(two)
    check("two tunes are split, not merged", len(tunes) == 2 and tunes[1].title == "b", len(tunes))
    bad = _tmp("b.abc", "X:1\nM:4/4\nL:1/8\nK:C\nCDEF ?? GABc|\n")
    check("unrecognised characters are reported", any("unrecognised" in w for w in parse_abc(bad).warnings))
    pt = _tmp("pt.abc", "X:1\nM:4/4\nL:1/8\nK:C\nP:Chorus\nCDEF GABc|\n")
    check("P: part label becomes a section", parse_abc(pt).notes[0].section == "Chorus")


def _write_midi(path, notes, ppq=480):
    """notes: (start_quarters, dur_quarters, absolute_cents). Quarter tones become pitch bend (+-2 st range)."""
    def vlq(n):
        out = [n & 0x7F]
        n >>= 7
        while n:
            out.append(0x80 | (n & 0x7F))
            n >>= 7
        return bytes(reversed(out))
    ev = []
    for st, du, c in notes:
        m = int(c // 100)
        bend = int(round(8192 + (c - m * 100) / 200.0 * 8192))
        a, b = int(round(st * ppq)), int(round((st + du) * ppq))
        ev += [(a, 0, bytes([0xE0, bend & 0x7F, bend >> 7])), (a, 1, bytes([0x90, m, 90])),
               (b, 0, bytes([0x80, m, 0]))]
    ev.sort(key=lambda e: (e[0], e[1]))
    tr, last = b"\x00\xff\x51\x03\x07\xa1\x20", 0       # tempo 500000 us = 120 bpm
    for t, _, data in ev:
        tr += vlq(t - last) + data
        last = t
    tr += b"\x00\xff\x2f\x00"
    import struct
    blob = b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + b"MTrk" + struct.pack(">I", len(tr)) + tr
    with open(path, "wb") as f:
        f.write(blob)


def _write_xml(path, notes):
    steps = [(0, "C"), (2, "D"), (4, "E"), (5, "F"), (7, "G"), (9, "A"), (11, "B")]
    body, pos = "", 0.0
    for st, du, c in notes:
        if st > pos:
            body += f"<forward><duration>{int(round((st - pos) * 2))}</duration></forward>"
        semis = int(c // 100)
        octave, pc = divmod(semis, 12)
        base, step = max((x for x in steps if x[0] <= pc), key=lambda x: x[0])
        alter = (c - (octave * 12 + base) * 100) / 100.0
        body += (f"<note><pitch><step>{step}</step><alter>{alter}</alter><octave>{octave - 1}</octave></pitch>"
                 f"<duration>{int(round(du * 2))}</duration></note>")
        pos = st + du
    xml = ('<?xml version="1.0"?><score-partwise><part-list><score-part id="P1"><part-name>Vocal</part-name>'
           '</score-part></part-list><part id="P1"><measure number="1"><attributes><divisions>2</divisions>'
           f'</attributes>{body}</measure></part></score-partwise>')
    with open(path, "w") as f:
        f.write(xml)


def section_importers():
    print("\n-- importers")
    from abc_parse import parse_abc
    from import_score import parse_midi, parse_musicxml
    from analyze_abc import analyze_all
    degs = list(TEMPLATES["bayati"][1])
    abc = _tmp("bay.abc", make_abc(200, degs, seed=5))
    notes = [(n.start, n.dur, n.cents) for n in parse_abc(abc).notes]
    d = tempfile.mkdtemp()
    mid, xml = os.path.join(d, "bay.mid"), os.path.join(d, "bay.musicxml")
    _write_midi(mid, notes)
    _write_xml(xml, notes)
    ref = sorted(round(c) for _, _, c in notes)
    m = parse_midi(mid)
    check("MIDI: pitch bend restores quarter tones", sorted(round(n.cents) for n in m.notes) == ref,
          sorted(set(round(n.cents) % 100 for n in m.notes)))
    check("MIDI: tempo read", abs((m.tempo_bpm or 0) - 120) < 0.5, m.tempo_bpm)
    x = parse_musicxml(xml)
    check("MusicXML: fractional <alter> kept", sorted(round(n.cents) for n in x.notes) == ref)
    for label, path in (("MIDI", mid), ("MusicXML", xml)):
        sc, rep = analyze_all(path, _A())[0]
        top = rep["groups"][0]["hypotheses"][0]
        labels = [f["label"] for f in top["fits"] if f["tied_with_best"]]
        check(f"{label}: analysed end to end (tonic D, Bayati, microtonal)",
              top["tonic"] == "D" and "Bayati" in labels and rep["groups"][0]["microtonal_input"], (top["tonic"], labels))
    # same melody WITHOUT bend: plain 12-TET MIDI cannot prove Bayati
    flat = os.path.join(d, "flat.mid")
    _write_midi(flat, [(a, b, round(c / 100.0 + 1e-9) * 100) for a, b, c in notes])
    sc, rep = analyze_all(flat, _A())[0]
    check("MIDI without bend is treated as 12-TET", not rep["groups"][0]["microtonal_input"])


def section_guards():
    print("\n-- guards from the gap review")
    from analyze_abc import analyze_all, render, phrase_gap_quarters
    from abc_parse import parse_abc
    # Sikah-like: the tonic is a quarter tone (E half-flat = 350 c above C)
    path = _tmp("sikah.abc", make_abc(350, list(TEMPLATES["rast"][1]), seed=3))
    sc, rep = analyze_all(path, _A())[0]
    g = rep["groups"][0]
    check("quarter-tone tonic is flagged and no maqam is named",
          (not g["name_allowed"]) and any("quarter-tone" in f for f in g["flags"]), (g["flags"], g["best_fit"]))
    brief = render(sc, dict(rep, groups=rep["groups"][:1]), True)
    check("--brief still prints the flags", "Flags" in brief and "do not name a maqam" in brief)
    check("--brief does not print a confident maqam name for it", "no single scale identified" in brief)
    # reference table cannot drift from the code
    from maqam_core import list_templates_markdown
    ref = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "maqamat.md"),
               encoding="utf-8").read()
    check("references/maqamat.md template table matches maqam_core --list",
          all(line in ref for line in list_templates_markdown().splitlines()))
    # tempo-normalised phrase gap
    slow = _tmp("s.abc", "X:1\nM:4/4\nL:1/8\nQ:1/4=60\nK:C\nCDEF GABc|\n")
    fast = _tmp("f.abc", "X:1\nM:4/4\nL:1/8\nQ:1/4=180\nK:C\nCDEF GABc|\n")
    gs, gf = phrase_gap_quarters(parse_abc(slow), _A()), phrase_gap_quarters(parse_abc(fast), _A())
    check("phrase gap scales with tempo (same seconds)", abs(gf / gs - 3.0) < 0.01, (gs, gf))
    # chord evidence weighted by duration
    from analyze_abc import annotate, build_profile
    ch = _tmp("c.abc", 'X:1\nM:4/4\nL:1/8\nK:C\n"G"CDEF|"C"GABc|"C"cBAG|"C"FEDC|\n')
    sc = parse_abc(ch)
    prof = build_profile(sc, annotate(sc, 1.0), "x", None)
    check("long chord outweighs short chord", prof.chords.get(0.0, 0) > prof.chords.get(700.0, 0), prof.chords)
    # cue circularity: a melody-only file can never reach 'high'
    high = [r for r in (analyze_all(_tmp(f"m{i}.abc", make_abc(200, list(TEMPLATES["hijaz"][1]), seed=i)), _A())[0][1]
                        for i in range(8)) if r["groups"][0]["tonic_confidence"] == "high"]
    check("melody-only input never reports high tonic confidence", not high)
    # audio: guard helpers and refusal of a one-pitch f0 table (no librosa needed)
    import subprocess
    from analyze_f0 import check_input
    sev, _ = check_input(30.0, [(200.0, 0.8)])
    check("audio guard: one dominant pitch is refused", len(sev) >= 2, sev)
    sev, soft = check_input(30.0, [(0, .2), (200, .2), (300, .2), (500, .2), (700, .2)])
    check("audio guard: healthy input passes", not sev and not soft, (sev, soft))
    import numpy as np
    csvp = _tmp("drone.csv", "".join(f"{i * 0.0116:.4f},220.0\n" for i in range(2600)))
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze_f0.py"),
                        "--csv", csvp], capture_output=True, text=True)
    check("audio: drone-only f0 table exits with code 2 and says why",
          r.returncode == 2 and "REFUSED" in r.stderr, (r.returncode, r.stderr[:120]))


def section_calibration():
    print("\n-- calibration on perturbed synthetic music (stress test, not real data)")
    import contextlib
    import io
    from evaluate import run as eval_run
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rows = eval_run(None, 100)
    n = len(rows)
    acc = sum(r["tonic_ok"] for r in rows) / n
    sure = [r for r in rows if r["tonic_conf"] in ("medium", "high")]
    unsure = [r for r in rows if r["tonic_conf"] == "low"]
    acc_sure = sum(r["tonic_ok"] for r in sure) / max(len(sure), 1)
    acc_unsure = sum(r["tonic_ok"] for r in unsure) / max(len(unsure), 1)
    print(f"      overall {100 * acc:.0f}%  medium/high {100 * acc_sure:.0f}% (n={len(sure)})  low {100 * acc_unsure:.0f}% (n={len(unsure)})")
    check("overall tonic accuracy >= 85%", acc >= 0.85, acc)
    check("medium/high tonic labels are right >= 93% of the time", acc_sure >= 0.93, acc_sure)
    check("low labels are less reliable than medium/high (label is informative)", acc_unsure < acc_sure,
          (acc_unsure, acc_sure))
    check("no wrong answer is labelled high", not [r for r in rows if r["tonic_conf"] == "high" and not r["tonic_ok"]])


if __name__ == "__main__":
    bad = run("--keep" in sys.argv)
    for sec in (section_parser, section_importers, section_guards, section_calibration):
        sec()
    fails = bad + _RESULTS.count(False)
    print(f"\n{'ALL PASSED' if not fails else str(fails) + ' FAILED'}  ({len(CASES) - bad}/{len(CASES)} template cases, "
          f"{_RESULTS.count(True)}/{len(_RESULTS)} extra checks)")
    sys.exit(1 if fails else 0)
