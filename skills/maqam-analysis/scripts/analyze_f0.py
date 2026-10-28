#!/usr/bin/env python3
"""Maqam evidence from an AUDIO file (or an f0 table): pitch peaks measured in cents.

    python analyze_f0.py vocals.wav                 # needs librosa (pip install librosa)
    python analyze_f0.py --csv f0.csv               # columns: time_seconds,f0_hz (0/NaN = unvoiced)
    python analyze_f0.py vocals.wav --tuning-cents -12   # if the recording is not at A=440
    python analyze_f0.py --selftest                 # synthetic Bayati/Kurd/Nahawand check

Use an ISOLATED VOCAL STEM when possible (e.g. from a source separator). Guitars and strings
make the pitch tracker jump; the numbers are only as clean as the input.

Why this exists: ABC/MIDI round everything to 12 semitones, so the 150-cent 2nd degree of
Bayati/Saba/Sikah and the 350-cent 3rd of Rast are invisible there. Here they are measured.

Output uses the same report as analyze_abc.py, plus a table of measured degrees relative to the
winning tonic (cents), which is the actual evidence for quarter tones.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from maqam_core import Profile, interpret, name_of, TEMPLATES      # noqa: E402
from analyze_abc import render_group                                # noqa: E402

C0_HZ = 16.3516          # C0 at A4 = 440


def hz_to_cents(f, tuning=0.0):
    return 1200.0 * np.log2(np.asarray(f, float) / C0_HZ) - tuning


def load_f0(path, csv=False, fmin="C2", fmax="C6", sr=22050, hop=512):
    if csv:
        arr = np.genfromtxt(path, delimiter=",", skip_header=0, invalid_raise=False)
        arr = arr[~np.isnan(arr).any(axis=1)] if arr.ndim == 2 else arr
        if arr.ndim != 2 or arr.shape[1] < 2:
            raise SystemExit("csv needs two columns: time_seconds,f0_hz")
        t, f = arr[:, 0], arr[:, 1]
        f = np.where(f > 0, f, np.nan)
        return t, f
    try:
        import librosa
    except ImportError:
        raise SystemExit("librosa is required for audio input: pip install librosa  (or pass --csv)")
    y, sr = librosa.load(path, sr=sr, mono=True)
    f0, voiced, prob = librosa.pyin(y, fmin=librosa.note_to_hz(fmin), fmax=librosa.note_to_hz(fmax),
                                    sr=sr, hop_length=hop)
    t = librosa.times_like(f0, sr=sr, hop_length=hop)
    f0 = np.where(voiced & (prob > 0.5), f0, np.nan)
    return t, f0


def segment_notes(t, cents, max_jump=60.0, min_frames=6, gap_s=0.25):
    """Group voiced frames into steady notes. Returns list of dict(start, dur, cents)."""
    notes, run = [], []
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.023

    def flush():
        if len(run) >= min_frames:
            idx = [i for i in run]
            notes.append({"start": t[idx[0]], "dur": (idx[-1] - idx[0] + 1) * dt,
                          "cents": float(np.median(cents[idx]))})
    for i in range(len(t)):
        if np.isnan(cents[i]):
            flush(); run = []
            continue
        if run:
            ref = np.median(cents[run[-5:]])
            circ = abs((cents[i] - ref + 600) % 1200 - 600)      # octave jumps count as big jumps
            if abs(cents[i] - ref) > max_jump or circ > max_jump:
                flush(); run = []
        run.append(i)
    flush()
    for k, n in enumerate(notes):
        nxt = notes[k + 1]["start"] - (n["start"] + n["dur"]) if k + 1 < len(notes) else 1e9
        prv = n["start"] - (notes[k - 1]["start"] + notes[k - 1]["dur"]) if k else 1e9
        n["final"], n["initial"] = nxt >= gap_s, prv >= gap_s
    return notes


def circular_hist(pc, w, bin_c=10.0, sigma=15.0):
    nb = int(1200 / bin_c)
    h = np.zeros(nb)
    idx = (np.round(pc / bin_c).astype(int)) % nb
    np.add.at(h, idx, w)
    # circular gaussian smoothing
    k = int(4 * sigma / bin_c)
    xs = np.arange(-k, k + 1) * bin_c
    g = np.exp(-0.5 * (xs / sigma) ** 2)
    g /= g.sum()
    hs = np.zeros(nb)
    for off, gv in zip(range(-k, k + 1), g):
        hs += gv * np.roll(h, off)
    return h, hs


def find_peaks(h_raw, hs, bin_c=10.0, min_share=0.015, merge_c=35.0):
    total = h_raw.sum() or 1.0
    nb = len(hs)
    cand = [i for i in range(nb) if hs[i] >= hs[(i - 1) % nb] and hs[i] > hs[(i + 1) % nb]
            and hs[i] / hs.sum() >= min_share / 3]
    cand.sort(key=lambda i: -hs[i])
    peaks = []
    for i in cand:
        c = i * bin_c
        if any(min(abs(c - p), 1200 - abs(c - p)) < merge_c for p, _ in peaks):
            continue
        # mass within +-35c, centroid within +-30c
        offs = np.arange(-4, 5)
        ids = (i + offs) % nb
        mass = h_raw[ids].sum() / total
        if mass < min_share:
            continue
        cen = float(((i + offs) * bin_c * h_raw[ids]).sum() / max(h_raw[ids].sum(), 1e-9)) % 1200
        peaks.append((cen, mass))
    return sorted(peaks)


def build_profile(notes, t, cents, tuning=0.0, steady_weight=1.0):
    valid = ~np.isnan(cents)
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.023
    pc = cents[valid] % 1200
    w = np.full(pc.shape, dt)
    h_raw, hs = circular_hist(pc, w)
    peaks = find_peaks(h_raw, hs)
    if not peaks:
        raise SystemExit("no stable pitch peaks found; is the signal voiced / is the input too noisy?")
    pcs = {round(c, 1): m for c, m in peaks}
    finals, initials, lasts = {}, {}, {}

    def nearest(c):
        return min(pcs, key=lambda p: min(abs(c % 1200 - p), 1200 - abs(c % 1200 - p)))
    for k, n in enumerate(notes):
        p = nearest(n["cents"])
        if n["final"]:
            finals[p] = finals.get(p, 0) + 1
        if n["initial"]:
            initials[p] = initials.get(p, 0) + 1
    if notes:
        p = nearest(notes[-1]["cents"])
        lasts[p] = 2.0
    prof = Profile(pcs=pcs, finals=finals, initials=initials, lasts=lasts, microtonal=True,
                   label="Audio (f0 peaks)")
    prof.total_dur = float(valid.sum() * dt)
    return prof, peaks


def report(prof, peaks, notes):
    res = interpret(prof)
    L = ["## Audio analysis (f0 -> cents)", "",
         f"- voiced material: {prof.total_dur:.1f} s, steady notes found: {len(notes)}",
         "- tuning assumed A4 = 440 Hz (use --tuning-cents if the track is detuned)", ""]
    L.append(render_group(res, prof.total_dur))
    top = res["hypotheses"][0]
    t = top["tonic_pc"]
    L.append("\nMeasured degrees relative to the winning tonic (cents):")
    L.append("| degree (cents above tonic) | share of voiced time | closest ideal degree in best-fit scale |")
    L.append("|---|---|---|")
    ideal = top["fits"][0]["degrees"] if top["fits"] else []
    for c, m in sorted(peaks, key=lambda x: (x[0] - t) % 1200):
        rel = (c - t) % 1200
        near = min(ideal, key=lambda d: min(abs(rel - d), 1200 - abs(rel - d))) if ideal else None
        L.append(f"| {rel:6.0f} | {100 * m:4.1f}% | {near if near is not None else '-'} "
                 f"({rel - near:+.0f}c) |" if near is not None else f"| {rel:6.0f} | {100 * m:4.1f}% | - |")
    L.append("\nA degree measured near 150 / 350 / 1050 cents is a quarter-tone degree "
             "(Bayati/Saba 2nd, Rast 3rd and 7th). Near 100 or 200 it is an ordinary semitone / whole tone.")
    return "\n".join(L), res


# ------------------------------------------------------------------ synthetic self-test
def _synth(tonic_hz, degrees_cents, seed, secs=26.0, sr=16000):
    rng = np.random.default_rng(seed)
    ladder = list(degrees_cents) + [degrees_cents[0] + 1200]
    sig, t_total, pos = [], 0.0, 0
    while t_total < secs:
        for _ in range(rng.integers(4, 7)):
            pos = int(np.clip(pos + rng.choice([-2, -1, -1, 0, 1, 1, 2]), 0, 7))
            dur = float(rng.choice([0.25, 0.35, 0.5]))
            sig.append(_tone(tonic_hz * 2 ** (ladder[pos] / 1200), dur, sr, rng))
            t_total += dur
        pos = 0 if rng.random() < 0.7 else 4
        dur = 0.7
        sig.append(_tone(tonic_hz * 2 ** (ladder[pos] / 1200), dur, sr, rng))
        sig.append(np.zeros(int(0.45 * sr)))
        t_total += dur + 0.45
    return np.concatenate(sig), sr


def _tone(f, dur, sr, rng):
    n = int(dur * sr)
    tt = np.arange(n) / sr
    vib = 1 + (12 / 1200 * math.log(2)) * np.sin(2 * np.pi * 5.5 * tt)   # +-12 cent vibrato
    ph = 2 * np.pi * np.cumsum(f * vib) / sr
    s = sum(a * np.sin(k * ph) for k, a in ((1, 1.0), (2, 0.5), (3, 0.3)))
    env = np.minimum(1, np.minimum(tt / 0.02, (dur - tt) / 0.03))
    return 0.3 * s * np.clip(env, 0, 1)


def selftest():
    import tempfile
    import soundfile as sf
    cases = [("bayati", "Bayati"), ("kurd", "Kurd"), ("nahawand", "Nahawand"), ("rast", "Rast"),
             ("hijaz", "Hijaz")]
    tonic_hz = 293.66           # D4
    bad = 0
    for i, (tid, want) in enumerate(cases):
        y, sr = _synth(tonic_hz, TEMPLATES[tid][1], seed=7 + i)
        path = os.path.join(tempfile.mkdtemp(), f"{tid}.wav")
        sf.write(path, y, sr)
        t, f0 = load_f0(path, sr=sr)
        cents = hz_to_cents(f0)
        notes = segment_notes(t, cents)
        prof, peaks = build_profile(notes, t, cents)
        res = interpret(prof)
        top = res["hypotheses"][0]
        labels = [f["label"] for f in top["fits"] if f["tied_with_best"]]
        ok = top["tonic"] == "D" and want in labels
        bad += not ok
        print(("PASS" if ok else "FAIL"), f"{tid:9s} tonic={top['tonic']:3s} shape={labels[:3]} "
              f"fit={top['fits'][0]['fit']:.2f} peaks={[round((c - 200) % 1200) for c, _ in peaks]}")
    print(f"\n{len(cases) - bad}/{len(cases)} passed")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio", nargs="?")
    ap.add_argument("--csv")
    ap.add_argument("--tuning-cents", type=float, default=0.0)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(1 if selftest() else 0)
    src = a.csv or a.audio
    if not src:
        sys.exit(__doc__)
    t, f0 = load_f0(src, csv=bool(a.csv))
    cents = hz_to_cents(f0, a.tuning_cents)
    notes = segment_notes(t, cents)
    prof, peaks = build_profile(notes, t, cents, a.tuning_cents)
    print(report(prof, peaks, notes)[0])


if __name__ == "__main__":
    main()
