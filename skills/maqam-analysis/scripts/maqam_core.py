#!/usr/bin/env python3
"""Maqam / scale scoring core shared by analyze_abc.py and analyze_f0.py.

Input is a *Profile*: pitch classes in cents (0..1199) with weights. Output is a ranked
interpretation: which tonic, which scale family, how sure, and what is ambiguous.

Design (why it looks like this)
  1. A pitch-class SET does not determine a mode: the 7 rotations of one set are 7
     different modes (D Phrygian = Eb Lydian = G Aeolian = Bb Ionian ...). The tonic
     decides, so tonic evidence is scored separately and shown component by component.
  2. Templates are stored in CENTS (Bayati has a 150-cent 2nd). When the input is 12-TET
     (ABC, MIDI) every template with k quarter-tone degrees is collapsed into 2^k 12-TET
     "shadows". Bayati therefore appears as Kurd-shaped and Nahawand-shaped sets, and the
     ambiguity falls out of the data instead of being hand-written.
  3. Nothing here "hears" anything. Confidence is capped by what the input can express.

Run `python maqam_core.py --list` to print the template table as Markdown.
"""
from __future__ import annotations

import itertools
import math
import re
import sys
from dataclasses import dataclass, field

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# id: (display name, degrees in cents from the tonic, western equivalent or "")
TEMPLATES = {
    "rast":       ("Rast",             [0, 200, 350, 500, 700, 900, 1050], ""),
    "ajam":       ("Ajam",             [0, 200, 400, 500, 700, 900, 1100], "major / Ionian"),
    "bayati":     ("Bayati",           [0, 150, 300, 500, 700, 800, 1000], ""),
    "nahawand":   ("Nahawand",         [0, 200, 300, 500, 700, 800, 1000], "natural minor / Aeolian"),
    "nahawand_h": ("Nahawand (raised 7th)", [0, 200, 300, 500, 700, 800, 1100], "harmonic minor"),
    "kurd":       ("Kurd",             [0, 100, 300, 500, 700, 800, 1000], "Phrygian"),
    "hijaz":      ("Hijaz",            [0, 100, 400, 500, 700, 800, 1000], ""),
    "hijaz_r":    ("Hijaz (Rast upper)", [0, 100, 400, 500, 700, 900, 1000], ""),
    "hijaz_kar":  ("Hijaz Kar",        [0, 100, 400, 500, 700, 800, 1100], ""),
    "saba":       ("Saba",             [0, 150, 300, 400, 700, 800, 1000], ""),
    "nikriz":     ("Nikriz",           [0, 200, 300, 600, 700, 900, 1000], ""),
    "nawa_athar": ("Nawa Athar",       [0, 200, 300, 600, 700, 800, 1100], ""),
    "dorian":     ("(no standard maqam)", [0, 200, 300, 500, 700, 900, 1000], "Dorian"),
    "mixolydian": ("(no standard maqam)", [0, 200, 400, 500, 700, 900, 1000], "Mixolydian"),
    "lydian":     ("(no standard maqam)", [0, 200, 400, 600, 700, 900, 1100], "Lydian"),
}
# Western modes are only meaningful in 12-TET mode; they are kept out of microtonal matching.
WESTERN_ONLY = {"dorian", "mixolydian", "lydian"}   # Locrian is deliberately absent (no usable tonic)

PRESENT_THR = 0.02      # a pitch class "counts" as a scale degree above 2 % of the duration
ABSENT_THR = 0.01       # below 1 % a degree is treated as absent
TOL_12TET = 15.0        # cents
TOL_MICRO = 35.0        # cents (f0 mode)

W_MELODIC = {"dur": 0.25, "final": 0.30, "initial": 0.10, "last": 0.10}
W_TOOL = {"chord": 0.15, "declared": 0.10}   # evidence produced by the transcription tool


def name_of(cents: float) -> str:
    c = cents % 1200
    s = round(c / 100)
    off = c - s * 100
    n = NAMES[s % 12]
    return n if abs(off) < 10 else f"{n}{off:+.0f}c"


def chord_root_cents(symbol: str):
    m = re.match(r"^([A-G])([#b]?)", symbol.strip())
    if not m:
        return None
    base = {"C": 0, "D": 200, "E": 400, "F": 500, "G": 700, "A": 900, "B": 1100}[m.group(1)]
    return (base + (100 if m.group(2) == "#" else -100 if m.group(2) == "b" else 0)) % 1200


@dataclass
class Profile:
    """Weights are fractions (they need not be pre-normalised)."""
    pcs: dict                                   # pc_cents -> duration weight
    finals: dict = field(default_factory=dict)  # pc_cents -> weight of phrase-final notes
    initials: dict = field(default_factory=dict)
    lasts: dict = field(default_factory=dict)   # pc_cents -> weight of last-note-of-section
    chords: dict = field(default_factory=dict)  # pc_cents -> count of chord roots
    declared: dict = field(default_factory=dict)  # pc_cents -> weight of declared-key tonic
    microtonal: bool = False                    # True when the pcs are not all multiples of 100c
    label: str = ""

    def norm(self, d):
        t = sum(d.values())
        return {k: v / t for k, v in d.items()} if t else {}


def is_microtonal(pcs, tol=12.0) -> bool:
    return any(min(abs(p % 100), 100 - abs(p % 100)) > tol for p in pcs)


def expand_templates(microtonal: bool):
    """Return list of (id, label, degrees, note). 12-TET mode uses collapsed shadows."""
    out = []
    for tid, (label, degs, west) in TEMPLATES.items():
        if microtonal:
            if tid in WESTERN_ONLY:
                continue
            out.append((tid, label, degs, west))
            continue
        halves = [i for i, d in enumerate(degs) if d % 100 == 50]
        for combo in itertools.product((-50, 50), repeat=len(halves)):
            d2 = list(degs)
            for i, off in zip(halves, combo):
                d2[i] = degs[i] + off
            out.append((tid, label, d2, west))
    return out


def _assign(profile_w, tonic, degrees, tol):
    covered, per_degree, outside_pcs = 0.0, [0.0] * len(degrees), {}
    for pc, w in profile_w.items():
        r = (pc - tonic) % 1200
        best, bd = None, 1e9
        for i, d in enumerate(degrees):
            dist = min(abs(r - d), 1200 - abs(r - d))
            if dist < bd:
                best, bd = i, dist
        if bd <= tol:
            covered += w
            per_degree[best] += w
        else:
            outside_pcs[pc] = w
    return covered, per_degree, outside_pcs


def _share_near(w, target, tol=30.0):
    return sum(v for k, v in w.items() if min(abs(k - target), 1200 - abs(k - target)) <= tol)


def tonic_scores(p: Profile):
    """Rank tonic candidates. A tonic is normally backed by a sung 5th (or 4th) above it;
    candidates without one are discounted (this is what stops e.g. 'E Locrian' from winning)."""
    w = p.norm(p.pcs)
    dur, fin, ini, las = w, p.norm(p.finals), p.norm(p.initials), p.norm(p.lasts)
    cho, dec = p.norm(p.chords), p.norm(p.declared)
    rows = []
    for pc, share in w.items():
        if share < PRESENT_THR:
            continue
        comp = {"dur": dur.get(pc, 0), "final": fin.get(pc, 0), "initial": ini.get(pc, 0),
                "last": las.get(pc, 0), "chord": cho.get(pc, 0), "declared": dec.get(pc, 0)}
        support = max(_share_near(w, (pc + 700) % 1200), 0.7 * _share_near(w, (pc + 500) % 1200))
        factor = min(1.0, max(0.35, support / 0.06))
        melodic = factor * sum(W_MELODIC[k] * comp[k] for k in W_MELODIC)
        tool = factor * sum(W_TOOL[k] * comp[k] for k in W_TOOL)
        rows.append({"pc": pc, "name": name_of(pc), "score": melodic + tool, "melodic": melodic,
                     "tool": tool, "fifth_support": round(support, 3), "factor": round(factor, 2), **comp})
    rows.sort(key=lambda r: -r["score"])
    tot = sum(r["score"] for r in rows) or 1.0
    for r in rows:
        r["share"] = r["score"] / tot
    return rows


def fit_templates(p: Profile, tonic: float, top=4):
    """Best templates for one tonic. Equal-fit templates are grouped (ambiguity)."""
    w = p.norm(p.pcs)
    tol = TOL_MICRO if p.microtonal else TOL_12TET
    results = {}
    for tid, label, degs, west in expand_templates(p.microtonal):
        cov, per_deg, outside = _assign(w, tonic, degs, tol)
        present = sum(1 for x in per_deg if x >= PRESENT_THR)
        missing = len(degs) - present
        extra = sum(1 for v in outside.values() if v >= PRESENT_THR)
        fit = cov - 0.02 * missing - 0.05 * extra
        key = (tid, label)
        if key not in results or fit > results[key]["fit"]:
            results[key] = {"id": tid, "label": label, "west": west, "fit": fit, "covered": cov,
                            "has_quarter_tone": any(d % 100 == 50 for d in TEMPLATES[tid][1]),
                            "missing_degrees": [i for i, x in enumerate(per_deg) if x < ABSENT_THR],
                            "degrees": degs, "outside": {name_of(k): round(v, 4) for k, v in outside.items()},
                            "extra": extra}
    ranked = sorted(results.values(), key=lambda r: -r["fit"])
    if not ranked:
        return []
    best = ranked[0]["fit"]
    for r in ranked:
        r["tied_with_best"] = abs(r["fit"] - best) < 0.005
    return ranked[:top + sum(1 for r in ranked[top:] if r["tied_with_best"])]


def semitone_pairs(p: Profile, template_degs=None, tonic=None):
    """Neighbouring pitch classes (100 c apart) that are both used -> alteration, modulation
    or a neutral/quarter-tone degree that the transcription rounded both ways."""
    w = p.norm(p.pcs)
    out = []
    keys = sorted(w)
    for a in keys:
        for b in keys:
            if 80 <= (b - a) % 1200 <= 120 and w[a] >= PRESENT_THR and w[b] >= PRESENT_THR:
                out.append({"pair": f"{name_of(a)}/{name_of(b)}", "share_a": round(w[a], 3),
                            "share_b": round(w[b], 3)})
    return out


def _argmax(d):
    return max(d, key=d.get) if d else None


def interpret(p: Profile, other: "Profile | None" = None):
    """Full interpretation of one profile.

    Two separate confidences are returned because they answer different questions:
      tonic_confidence  - do independent cues (melody, chords, declared key, other voice) agree?
      shape_confidence  - does one scale shape explain the notes, and can the input even
                          express the distinctions that matter (quarter tones)?
    """
    p.microtonal = p.microtonal or is_microtonal(p.pcs)
    w = p.norm(p.pcs)
    tonics = tonic_scores(p)
    hyps = []
    for tr in tonics[:4]:
        hyps.append({"tonic": tr["name"], "tonic_pc": tr["pc"], "tonic_row": tr,
                     "fits": fit_templates(p, tr["pc"])})
    top = hyps[0] if hyps else None
    margin = (tonics[0]["share"] - tonics[1]["share"]) if len(tonics) > 1 else 1.0
    best_fit = top["fits"][0]["fit"] if top and top["fits"] else 0.0
    same_set = bool(len(hyps) > 1 and hyps[1]["fits"] and hyps[1]["fits"][0]["fit"] >= best_fit - 0.03)

    # ---- independent cues voting for the winning tonic -------------------------------
    cues = {}
    if top:
        tpc = top["tonic_pc"]
        melodic_top = max(tonics, key=lambda r: r["melodic"])
        cues["vocal/main melody"] = (melodic_top["pc"] == tpc, melodic_top["name"])
        # chord roots and declared key come from the same transcription tool: ONE vote, not two
        dec = _argmax(p.norm(p.declared)) if p.declared else None
        cho = _argmax(p.norm(p.chords)) if p.chords else None
        if dec is not None or cho is not None:
            vote = dec if dec is not None else cho
            extra = f" (key) / {name_of(cho)} (commonest chord root)" if (dec is not None and cho is not None) else ""
            cues["tool key & chords*"] = (vote == tpc, name_of(vote) + extra)
        if other is not None and other.pcs:
            ot = tonic_scores(other)
            if ot:
                o = max(ot, key=lambda r: r["melodic"])
                cues["other voice"] = (o["pc"] == tpc, o["name"])
    agree = sum(1 for ok, _ in cues.values() if ok)
    avail = len(cues)
    frac = agree / avail if avail else 0.0
    if avail >= 2 and frac >= 0.75 and margin >= 0.08:
        tonic_conf = "high"
    elif avail >= 2 and frac >= 0.5:
        tonic_conf = "medium"
    elif avail < 2 and margin >= 0.15:
        tonic_conf = "medium"
    else:
        tonic_conf = "low"

    # ---- scale-shape confidence -------------------------------------------------------
    if best_fit >= 0.95:
        shape_conf = "high" if p.microtonal else "medium"   # 12-TET can never prove a maqam
    elif best_fit >= 0.88:
        shape_conf = "medium" if p.microtonal else "low"
    else:
        shape_conf = "low"
    return {"label": p.label, "microtonal_input": p.microtonal,
            "present_pcs": [(name_of(x), round(w[x], 3)) for x in sorted(w, key=lambda k: -w[k])],
            "tonics": tonics[:5], "hypotheses": hyps, "tonic_margin": round(margin, 3),
            "best_fit": round(best_fit, 3), "relative_mode_ambiguity": same_set,
            "cues": {k: {"agrees": ok, "points_to": nm} for k, (ok, nm) in cues.items()},
            "tonic_confidence": tonic_conf, "shape_confidence": shape_conf,
            "semitone_pairs": semitone_pairs(p)}


def list_templates_markdown() -> str:
    rows = ["| id | name | western | degrees (cents) | 12-TET shadows (semitones) |", "|---|---|---|---|---|"]
    for tid, (label, degs, west) in TEMPLATES.items():
        shadows = sorted({tuple(d // 100 for d in t[2]) for t in expand_templates(False) if t[0] == tid})
        rows.append(f"| {tid} | {label} | {west or '-'} | {degs} | "
                    + " ; ".join("{" + ",".join(map(str, s)) + "}" for s in shadows) + " |")
    return "\n".join(rows)


if __name__ == "__main__":
    if "--list" in sys.argv:
        print(list_templates_markdown())
    else:
        sys.exit(__doc__)
