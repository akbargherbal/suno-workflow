#!/usr/bin/env python3
"""Analyse a transcribed ABC score for tonic / scale / maqam evidence.

    python analyze_abc.py score.abc                    # Markdown report, vocal voice
    python analyze_abc.py song.mid song.musicxml       # MIDI (pitch bend honoured) and MusicXML too
    python analyze_abc.py a.abc b.abc --brief          # one block per file (batch)
    python analyze_abc.py score.abc --voice all --json # machine-readable
    python analyze_abc.py score.abc --voice Ins        # analyse the instrument line

Options
  --voice NAME|all   voice id or part of its name (default: the voice named like "vocal")
  --phrase-gap Q     rest length (quarter notes) that ends a phrase. Default: 0.6 s converted with the
                     file's Q: tempo (1.0 quarter note when there is no tempo)
  --min-dur Q        skip sections with less than Q quarter notes of material (default 24)
  --no-sections      whole piece only
  --brief            top-line summary only
  --json             dump the full interpretation as JSON

Read references/maqamat.md for how to turn this output into an answer.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from abc_parse import Score                                       # noqa: E402
from import_score import load_scores                              # noqa: E402
from maqam_core import Profile, interpret, name_of, chord_root_cents     # noqa: E402

DEGREE_NAMES = ["tonic", "2nd", "3rd", "4th", "5th", "6th", "7th"]


def binpc(cents: float) -> float:
    return (round((cents % 1200) / 25.0) * 25) % 1200


def key_tonic(key: str):
    import re
    m = re.match(r"^([A-Ga-g])([#b]?)", key.strip())
    if not m:
        return None
    base = {"C": 0, "D": 200, "E": 400, "F": 500, "G": 700, "A": 900, "B": 1100}[m.group(1).upper()]
    return (base + (100 if m.group(2) == "#" else -100 if m.group(2) == "b" else 0)) % 1200


def pick_voice(sc: Score, wanted: str | None):
    ids = list(sc.voices)
    if wanted and wanted.lower() == "all":
        return None
    if wanted:
        for vid, nm in sc.voices.items():
            if wanted.lower() in (vid.lower(), nm.lower()) or wanted.lower() in nm.lower():
                return vid
        raise SystemExit(f"voice '{wanted}' not found; voices: {sc.voices}")
    for vid, nm in sc.voices.items():
        if "vocal" in nm.lower() or "vocal" in vid.lower() or "voice" in nm.lower():
            return vid
    return None if len(ids) != 1 else ids[0]


def annotate(sc: Score, gap: float):
    """Yield (note, is_phrase_final, is_phrase_initial, is_block_last) per voice, in time order."""
    out = []
    by_voice = defaultdict(list)
    for n in sc.notes:
        by_voice[n.voice].append(n)
    for vid, ns in by_voice.items():
        for i, n in enumerate(ns):
            nxt_gap = (ns[i + 1].start - (n.start + n.dur)) if i + 1 < len(ns) else 1e9
            prev_gap = (n.start - (ns[i - 1].start + ns[i - 1].dur)) if i else 1e9
            block_last = (i + 1 == len(ns)) or ns[i + 1].section != n.section
            out.append((n, nxt_gap >= gap, prev_gap >= gap, block_last, i + 1 == len(ns)))
    return out


def build_profile(sc: Score, ann, label, voice, section=None, exclude_voice=None) -> Profile | None:
    pcs, fin, ini, las, dec, cho = (defaultdict(float) for _ in range(6))
    total = 0.0
    for n, is_fin, is_ini, blk_last, piece_last in ann:
        if voice is not None and n.voice != voice:
            continue
        if exclude_voice is not None and n.voice == exclude_voice:
            continue
        if section is not None and n.section != section:
            continue
        pc = binpc(n.cents)
        pcs[pc] += n.dur
        total += n.dur
        fin[pc] += 1.0 if is_fin else 0.0
        ini[pc] += 1.0 if is_ini else 0.0
        las[pc] += (2.0 if piece_last and section is None else 0.0) + (1.0 if blk_last else 0.0)
        t = key_tonic(n.key)
        if t is not None:
            dec[t] += n.dur
    ends = {}
    for n in sc.notes:
        ends[n.voice] = max(ends.get(n.voice, 0.0), n.start + n.dur)
    per_voice = defaultdict(list)
    for vid, t, sym, sec in sc.chords:
        per_voice[vid].append((t, sym, sec))
    for vid, lst in per_voice.items():
        lst.sort()
        for k, (t, sym, sec) in enumerate(lst):
            if section is not None and sec != section:
                continue
            nxt = lst[k + 1][0] if k + 1 < len(lst) else ends.get(vid, t + 1.0)
            r = chord_root_cents(sym)
            if r is not None:
                cho[binpc(r)] += max(nxt - t, 0.0) or 1.0       # weight = how long the chord is in force
    if total <= 0:
        return None
    p = Profile(pcs=dict(pcs), finals=dict(fin), initials=dict(ini), lasts=dict(las),
                chords=dict(cho), declared={binpc(k): v for k, v in dec.items()}, label=label)
    p.total_dur = total
    return p


def fmt_pct(x):
    return f"{100 * x:.1f}%"


def describe_fit(f):
    if f["label"].startswith("(no standard"):
        return f"{f['west']} (Western mode, no standard maqam)"
    return f["label"] + (f" ({f['west']})" if f["west"] else "")


def describe_group(fits, microtonal):
    """Exact 12-TET matches first; maqamat that need a quarter tone are shown as possible readings."""
    tied = [f for f in fits if f["tied_with_best"]]
    if microtonal:
        return " | ".join(dict.fromkeys(describe_fit(f) for f in tied[:2]))
    exact = [f for f in tied if not f["has_quarter_tone"]]
    shadow = [f for f in tied if f["has_quarter_tone"]]
    txt = " | ".join(dict.fromkeys(describe_fit(f) for f in exact)) or "(none exact)"
    if shadow:
        txt += "  [12-TET shadow of: " + ", ".join(dict.fromkeys(f["label"] for f in shadow)) + "]"
    return txt


def render_group(res, total_dur, brief=False, unit="quarter-notes"):
    L = []
    top = res["hypotheses"][0] if res["hypotheses"] else None
    title = f"### {res['label']}  ({total_dur:.0f} {unit} of material)"
    L.append(title)
    L.append("Pitch classes (share of duration): " + ", ".join(f"{n} {fmt_pct(s)}" for n, s in res["present_pcs"]))
    if not top:
        return "\n".join(L)
    names = describe_group(top["fits"], res["microtonal_input"])
    inp = "microtonal" if res["microtonal_input"] else "12-TET only, quarter tones invisible"
    L.append(f"**Most likely tonic: {top['tonic']}**  (confidence: **{res['tonic_confidence']}**, tonic margin {res['tonic_margin']:.2f})")
    cue_txt = ", ".join(f"{k} {'agrees' if v['agrees'] else 'says ' + v['points_to']}" for k, v in res["cues"].items())
    if cue_txt:
        L.append(f"  cues: {cue_txt}")
    fit0 = top["fits"][0]["fit"]
    if res.get("name_allowed", True):
        L.append(f"**Scale shape: {names}**  (fit {fit0:.2f}; confidence: **{res['shape_confidence']}**; input: {inp})")
    else:
        L.append(f"**Scale shape: no single scale identified - do not name a maqam**  "
                 f"(closest partial match {names}, fit {fit0:.2f}; confidence: **low**; input: {inp})")
    g = res.get("ghammaz")
    if g:
        L.append(f"  secondary resting note (candidate ghammaz): {g['note']}, {g['interval_cents']} c above the tonic "
                 f"({100 * g['final_share']:.0f}% of phrase endings) - a pop melody may rest here for other reasons")
    if res.get("flags"):
        L.append("**Flags:**")
        L.extend("- " + f for f in res["flags"])
    if brief:
        return "\n".join(L)
    L.append("")
    L.append("| tonic candidate | share | melody-only | dur | final | initial | last | chord* | declared* | best-fit scale |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for h in res["hypotheses"]:
        r = h["tonic_row"]
        fit = h["fits"][0] if h["fits"] else None
        fn = (describe_group(h["fits"], res["microtonal_input"]) + f" ({fit['fit']:.2f})") if fit else "-"
        L.append(f"| {h['tonic']} | {r['share']:.2f} | {r['melodic']:.2f} | {r['dur']:.2f} | {r['final']:.2f} | {r['initial']:.2f} "
                 f"| {r['last']:.2f} | {r['chord']:.2f} | {r['declared']:.2f} | {fn} |")
    L.append("(* chord / declared-key columns come from the transcription tool, not from the melody)")
    fit_top = top["fits"][0]
    notes = []
    if fit_top["outside"]:
        outs = sorted(fit_top["outside"].items(), key=lambda kv: -kv[1])
        big = [(k, v) for k, v in outs if v >= 0.015]
        if big:
            notes.append("Notes outside this scale: " + ", ".join(f"{k} {fmt_pct(v)}" for k, v in big)
                         + "  -> modulation, alteration, or a neutral degree rounded to the wrong side")
    miss = [DEGREE_NAMES[i] for i in fit_top["missing_degrees"] if i > 0]
    if miss:
        notes.append("Scale degrees almost never sung: " + ", ".join(miss)
                     + "  -> avoided on purpose, or microtonal and lost in transcription")
    out_names = set(fit_top["outside"])
    pairs = [p for p in res["semitone_pairs"] if set(p["pair"].split("/")) & out_names]
    if pairs:
        notes.append("Both semitone neighbours sung (one is outside the scale): "
                     + ", ".join(f"{p['pair']} ({fmt_pct(p['share_a'])}/{fmt_pct(p['share_b'])})" for p in pairs[:5])
                     + "  -> typical of a neutral/quarter-tone degree rounded both ways, or of modulation")
    if notes:
        L.append("")
        L.extend("- " + n for n in notes)
    return "\n".join(L)


def phrase_gap_quarters(sc, args):
    g = getattr(args, "phrase_gap", None)
    if g is not None:
        return g
    if sc.tempo_bpm:
        return min(4.0, max(0.5, 0.6 * sc.tempo_bpm / 60.0))       # 0.6 s of silence ends a phrase
    return 1.0


def analyze_score(sc, path, args, tune_label=""):
    voice = pick_voice(sc, args.voice)
    gap = phrase_gap_quarters(sc, args)
    ann = annotate(sc, gap)
    name = os.path.basename(path) + (f"  [{tune_label}]" if tune_label else "")
    warnings = list(sc.warnings)
    if voice is None and len(sc.voices) > 1:
        warnings.append(f"{len(sc.voices)} voices merged into one profile ({', '.join(sc.voices.values())}); "
                        "pass --voice NAME to analyse one line (accompaniment can outvote the melody)")
    report = {"file": name, "source": sc.source, "declared_key": sc.declared_key, "tempo": sc.tempo_bpm,
              "voices": sc.voices, "voice_analysed": voice or "all", "phrase_gap_quarters": round(gap, 3),
              "bar_match_ratio": round(sc.bar_match_ratio, 4), "key_changes": sc.keys,
              "warnings": warnings, "groups": []}
    whole = build_profile(sc, ann, "Whole piece", voice)
    groups = [(whole, None)] if whole else []
    if not args.no_sections:
        for sec in dict.fromkeys(n.section for n in sc.notes if n.section):
            p = build_profile(sc, ann, f"Section: {sec}", voice, sec)
            if p and p.total_dur >= args.min_dur:
                groups.append((p, sec))
    for p, sec in groups:
        other = None
        if voice is not None:
            other = build_profile(sc, ann, "other voices", None, sec, exclude_voice=voice)
            if other is not None:
                other.chords, other.declared = {}, {}   # chords/key are counted once, on the main profile
        res = interpret(p, other)
        res["total_dur"] = p.total_dur
        res["section"] = sec
        if p.total_dur < 16:
            res["flags"].append(f"only {p.total_dur:.0f} quarter-notes of material: treat every number as anecdotal")
        report["groups"].append(res)
    return sc, report


def analyze_all(path, args):
    """One (Score, report) per tune; ABC, MIDI and MusicXML are told apart by extension."""
    scores = load_scores(path)
    out = []
    for i, sc in enumerate(scores):
        label = f"tune {i + 1}/{len(scores)}: {sc.title}" if len(scores) > 1 else ""
        out.append(analyze_score(sc, path, args, label))
    return out


def analyze_file(path, args):
    """First tune only (kept for selftest and scripts)."""
    return analyze_all(path, args)[0]


def render(sc, report, brief):
    L = [f"## {report['file']}", ""]
    vname = sc.voices.get(report["voice_analysed"], report["voice_analysed"])
    L.append(f"- declared key (transcription tool): **{report['declared_key']}**, tempo {report['tempo']}, "
             f"voice analysed: **{vname}**")
    ch = sorted({k for _, _, k in report["key_changes"]})
    if ch:
        L.append(f"- key signature changes inside the file: {', '.join(ch)}  (tool-detected; see sections below)")
    ok = report["bar_match_ratio"]
    if report.get("source", "abc") == "abc":
        L.append(f"- parse check: {100 * ok:.0f}% of bars sum to the meter"
                 + ("" if ok >= 0.95 else "  **<- parse is unreliable, do not trust the numbers**"))
    else:
        L.append(f"- parse check: not applicable to {report['source']} input (no bar-sum test); "
                 "microtones only exist where pitch bend / fractional alter is present")
    if report["warnings"]:
        L.append(f"- parser warnings: {'; '.join(report['warnings'])}")
    L.append("")
    for g in report["groups"]:
        L.append(render_group(g, g["total_dur"], brief))
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--voice")
    ap.add_argument("--phrase-gap", type=float, default=None)
    ap.add_argument("--min-dur", type=float, default=24.0)
    ap.add_argument("--no-sections", action="store_true")
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    all_reports = []
    for f in args.files:
        for sc, rep in analyze_all(f, args):
            all_reports.append(rep)
            if not args.json:
                groups = rep["groups"][:1] if args.brief else rep["groups"]
                rep2 = dict(rep, groups=groups)
                print(render(sc, rep2, args.brief))
    if args.json:
        print(json.dumps(all_reports if len(all_reports) > 1 else all_reports[0], ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
