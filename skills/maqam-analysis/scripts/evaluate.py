#!/usr/bin/env python3
"""Ground-truth check: how often is the analyzer right, and does its confidence label mean anything?

    python evaluate.py truth.csv                 # your labelled files
    python evaluate.py --synthetic 80            # perturbed synthetic music (stress test, not real data)
    python evaluate.py truth.csv --synthetic 40  # both

truth.csv (header required; extra columns ignored):
    file,tonic,maqam,voice
    songs/a.abc,D,Bayati,Vocal
    songs/b.mid,G,Nahawand,
  - file    path (relative to the csv); .abc / .mid / .musicxml
  - tonic   note name (C, D#, Eb, F ...); enharmonic spellings are equivalent
  - maqam   optional; compared with the shape the analyzer names
  - voice   optional --voice value

Scoring
  tonic  correct when the winning pitch class equals the truth.
  maqam  "exact"    tonic correct and the truth is among the best-fit labels
         "possible" tonic correct and the truth is a quarter-tone maqam whose 12-TET shadow ties for best
                    (the most a 12-TET file can ever give)
         "withheld" the analyzer declined to name a scale (poor fit / quarter-tone tonic): not counted as a miss
         "miss"     otherwise
Output: accuracy per tonic-confidence label. A trustworthy label shows accuracy rising from low to high.
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import tempfile
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_abc import analyze_all                       # noqa: E402
from maqam_core import TEMPLATES, NAMES                   # noqa: E402

ENH = {"C#": "C#", "DB": "C#", "D#": "Eb", "EB": "Eb", "F#": "F#", "GB": "F#", "G#": "Ab", "AB": "Ab",
       "A#": "Bb", "BB": "Bb"}


def canon(n: str) -> str:
    n = n.strip()
    if not n:
        return ""
    n = n[0].upper() + n[1:]
    return ENH.get(n.upper(), n)


class A:                                   # argparse stand-in
    voice = None
    phrase_gap = None
    min_dur = 24.0
    no_sections = True


def judge(rep, want_tonic, want_maqam=""):
    g = rep["groups"][0]
    top = g["hypotheses"][0]
    got = canon(top["tonic"].split("+")[0].split("-")[0])
    tonic_ok = got == canon(want_tonic)
    labels = [f["label"].split(" (")[0] for f in top["fits"] if f["tied_with_best"]]
    maq = ""
    if want_maqam:
        if not tonic_ok:
            maq = "miss"
        elif not g["name_allowed"]:
            maq = "withheld"
        elif want_maqam.split(" (")[0] in labels:
            tid = [k for k, v in TEMPLATES.items() if v[0] == want_maqam]
            quarter = bool(tid) and any(d % 100 == 50 for d in TEMPLATES[tid[0]][1])
            maq = "possible" if (quarter and not g["microtonal_input"]) else "exact"
        else:
            maq = "miss"
    return tonic_ok, maq, g["tonic_confidence"], g["shape_confidence"], got, labels


def synthetic_cases(n, seed=1):
    from selftest import make_abc
    rng = random.Random(seed)
    ids = [t for t in TEMPLATES if t not in ("dorian", "mixolydian", "lydian")]
    out = []
    for i in range(n):
        tid = rng.choice(ids)
        tonic = rng.choice(range(0, 1200, 100))
        micro = rng.choice([True, False])
        degs = list(TEMPLATES[tid][1])
        if not micro:       # what a 12-TET transcriber writes: quarter tones rounded (down for 2nd, up for 3rd/7th)
            degs = [d - 50 if d % 100 == 50 and i_ == 1 else d + 50 if d % 100 == 50 else d for i_, d in enumerate(degs)]
        level = rng.choice(["clean", "pop-endings", "noisy", "noisy+pop", "missing-degree"])
        kw = {"clean": {}, "pop-endings": {"p_final_tonic": 0.25}, "noisy": {"p_offscale": 0.08},
              "noisy+pop": {"p_final_tonic": 0.3, "p_offscale": 0.06},
              "missing-degree": {"drop_degree": rng.choice([1, 3, 5])}}[level]
        text = make_abc(tonic, degs, seed=seed * 1000 + i, **kw)
        out.append((f"{tid}-{NAMES[(tonic // 100) % 12]}-{'micro' if micro else '12tet'}-{level}", text,
                    NAMES[(tonic // 100) % 12], TEMPLATES[tid][0] if micro else "", level))
    return out


def table(rows, key, title):
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        by[r[key]][0] += 1
        by[r[key]][1] += r["tonic_ok"]
    print(f"\n{title}")
    print("| confidence | n | tonic correct |")
    print("|---|---|---|")
    for lab in ("high", "medium", "low"):
        if lab in by:
            n, k = by[lab]
            print(f"| {lab} | {n} | {k}/{n} = {100 * k / n:.0f}% |")


def run(truth=None, synthetic=0):
    rows = []
    if truth:
        base = os.path.dirname(os.path.abspath(truth))
        for r in csv.DictReader(open(truth, encoding="utf-8")):
            path = os.path.join(base, r["file"])
            a = A()
            a.voice = (r.get("voice") or "").strip() or None
            try:
                sc, rep = analyze_all(path, a)[0]
            except Exception as e:                        # noqa: BLE001
                print(f"ERROR {r['file']}: {e}")
                continue
            ok, maq, tc, shc, got, labels = judge(rep, r["tonic"], (r.get("maqam") or "").strip())
            rows.append({"name": r["file"], "tonic_ok": ok, "maq": maq, "tonic_conf": tc, "shape_conf": shc,
                         "got": got, "want": canon(r["tonic"]), "labels": labels, "group": "real"})
    if synthetic:
        tmp = tempfile.mkdtemp()
        for name, text, tonic, maqam, level in synthetic_cases(synthetic):
            path = os.path.join(tmp, name + ".abc")
            open(path, "w").write(text)
            sc, rep = analyze_all(path, A())[0]
            ok, maq, tc, shc, got, labels = judge(rep, tonic, maqam)
            rows.append({"name": name, "tonic_ok": ok, "maq": maq, "tonic_conf": tc, "shape_conf": shc,
                         "got": got, "want": tonic, "labels": labels, "group": level})
    if not rows:
        sys.exit(__doc__)
    for r in rows:
        if not r["tonic_ok"] or r["maq"] == "miss":
            print(f"MISS {r['name']:44s} tonic {r['got']} (want {r['want']}) conf={r['tonic_conf']:6s} "
                  f"maqam={r['maq'] or '-'} shape={r['labels'][:2]}")
    n = len(rows)
    print(f"\n{n} files: tonic correct {sum(r['tonic_ok'] for r in rows)}/{n}")
    mq = [r["maq"] for r in rows if r["maq"]]
    if mq:
        print("maqam:", ", ".join(f"{k} {mq.count(k)}" for k in ("exact", "possible", "withheld", "miss") if mq.count(k)))
    table(rows, "tonic_conf", "Tonic accuracy by tonic confidence label")
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        by[r["group"]][0] += 1
        by[r["group"]][1] += r["tonic_ok"]
    print("\nBy condition: " + "; ".join(f"{k} {v[1]}/{v[0]}" for k, v in sorted(by.items())))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("truth", nargs="?")
    ap.add_argument("--synthetic", type=int, default=0)
    a = ap.parse_args()
    run(a.truth, a.synthetic)
