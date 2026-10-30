#!/usr/bin/env python3
"""
abc_tool.py - measure, validate and compare ABC scores (stdlib only).

  python abc_tool.py features a.abc [b.abc ...] [--json]
  python abc_tool.py check    a.abc [b.abc ...]
  python abc_tool.py compare  candidate.abc ref1.abc [ref2.abc ...] [--others other_candidate.abc ...]
  python abc_tool.py maqam    score.abc --label Hijaz        (which maqam + tonic does the score really use?)
  python abc_tool.py scale    --maqam Hijaz --tonic D --key-from score.abc   (ABC spelling of the scale)
  python abc_tool.py modal    var.abc --maqam Hijaz --tonic D                (does it obey the maqam?)
  python abc_tool.py traits   score.abc [--peers DIR]    (what is distinctive about this song vs its sibling songs)
  python abc_tool.py survey   ROOT_FOLDER     (run `maqam` on every */score.abc; for calibration)
  python abc_tool.py progress ROOT_FOLDER     (which songs still lack VAR_A/B/C_score.abc + report)

features : what a score "does" (phrase length, repeated-pitch share, notes/second,
           degrees used, short fills + their spacing, length in seconds).
check    : does every bar add up to the meter? do voices end together? (so the
           abcjs editor plays it as intended)
compare  : longest identical melodic run (in intervals, so transposition does not
           hide a copy) between a candidate and references / other candidates.

Handles what auto-transcribed scores contain: voices (V:), chord symbols, ties,
key signatures with bar-long accidental memory, Z multi-bar rests, mid-tune M:/L:
changes, simple tuplets. Ignores grace notes, decorations and lyrics lines.
"""
import difflib
import json
import re
import statistics
import sys
from fractions import Fraction

NOTE_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SHARP_ORDER = "FCGDAEB"
FLAT_ORDER = "BEADGCF"
DEGREE_NAMES = ["1", "b2", "2", "b3", "3", "4", "b5", "5", "b6", "6", "b7", "7"]
MODE_OFFSET = {"maj": 0, "ion": 0, "dor": 2, "phr": 4, "lyd": 5, "mix": 7,
               "aeo": 9, "min": 9, "m": 9, "loc": 11}
# relative-major pitch class -> signed accidental count (+sharps / -flats)
MAJOR_ACC = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: -5, 8: -4, 3: -3,
             10: -2, 5: -1}


# ----------------------------------------------------------------- parsing
def parse_frac(s, default=None):
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)", s or "")
    return Fraction(int(m.group(1)), int(m.group(2))) if m else default


def key_info(kline):
    """Return (tonic_pc, accidental_dict) from the text after 'K:'."""
    m = re.match(r"\s*([A-G])([#b]?)\s*([A-Za-z]*)", kline)
    if not m:
        return 0, {}
    letter, acc, mode = m.group(1), m.group(2), m.group(3).lower()
    tonic = (NOTE_BASE[letter] + (1 if acc == "#" else -1 if acc == "b" else 0)) % 12
    off = 0
    for k, v in MODE_OFFSET.items():
        if mode.startswith(k) and (k != "m" or mode in ("m", "min", "minor")):
            off = v
            break
    if mode.startswith("maj") or mode.startswith("ion"):
        off = 0
    rel = (tonic - off) % 12
    n = MAJOR_ACC[rel]
    if acc == "#" and n < 0:
        n += 12
    if acc == "b" and n > 0:
        n -= 12
    sig = {}
    if n > 0:
        for L in SHARP_ORDER[:n]:
            sig[L] = 1
    elif n < 0:
        for L in FLAT_ORDER[:-n]:
            sig[L] = -1
    return tonic, sig


def parse_dur(g):
    m = re.match(r"(\d+)?(/+)?(\d+)?", g or "")
    num = int(m.group(1)) if m.group(1) else 1
    if m.group(2):
        den = int(m.group(3)) if m.group(3) else 2 ** len(m.group(2))
    else:
        den = 1
    return Fraction(num, den)


NOTE_RE = re.compile(
    r"(?P<tup>\((?P<p>\d)(?::(?P<q>\d))?)|"
    r"(?P<bar>\|\]|\|\||\[\||:\||\|:|\|)|"
    r"(?P<rest>[zZxX])(?P<rd>\d*/*\d*)|"
    r"(?P<acc>\^\^|\^|__|_|=)?(?P<l>[A-Ga-g])(?P<oc>[,']*)(?P<d>\d*/*\d*)(?P<tie>-)?")


def parse_abc(path):
    """Return dict(meta=..., voices={name: [events]}, bars={name: [bar_len_quarters]})"""
    text = open(path, encoding="utf-8").read()
    unit = Fraction(1, 8)
    meter = Fraction(4, 4)
    qpm = 120.0
    tonic, sig = 0, {}
    meter_str = ""
    voices, bars = {}, {}
    clock = {}
    cur = "default"
    in_body = False
    tie_pending = {}
    mem = {}
    warns = []
    first_k = True

    def bar_q():
        return float(meter * 4)

    def ensure(v):
        voices.setdefault(v, [])
        bars.setdefault(v, [[0.0, bar_q()]])
        clock.setdefault(v, 0.0)

    for ln, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        fm = re.match(r"([A-Za-z]):\s*(.*)", line)
        if fm and not line.startswith("%%"):
            f, v = fm.group(1), fm.group(2)
            if f == "K":
                tonic, sig = key_info(v)
                in_body = True
                first_k = False
            elif f == "M":
                meter = parse_frac(v, meter) if "/" in v else meter
                if not meter_str:
                    meter_str = v.strip()
                for bl in bars.values():
                    if bl[-1][0] == 0:
                        bl[-1][1] = bar_q()
            elif f == "L":
                unit = parse_frac(v, unit)
            elif f == "Q":
                q = re.match(r"\s*(?:(\d+)/(\d+)\s*=\s*)?(\d+)", v)
                if q:
                    a, b = (int(q.group(1)), int(q.group(2))) if q.group(1) else (1, 4)
                    qpm = int(q.group(3)) * (a / b) * 4
            elif f == "V":
                cur = v.split()[0] if v.split() else "default"
                ensure(cur)
            elif f == "w":
                pass
            continue
        if not in_body:
            continue
        body = re.sub(r'"[^"]*"', "", line)          # chord symbols
        body = re.sub(r"!\w+!|\+\w+\+", "", body)    # decorations
        body = re.sub(r"\{[^}]*\}", "", body)        # grace notes
        for fld in re.findall(r"\[([A-Za-z]):([^\]]*)\]", body):
            if fld[0] == "M":
                meter = parse_frac(fld[1], meter)
            elif fld[0] == "V":
                cur = fld[1].split()[0]
                ensure(cur)
        body = re.sub(r"\[[A-Za-z]:[^\]]*\]", "", body)
        body = re.sub(r"%.*$", "", body)
        ensure(cur)
        tup = None
        for t in NOTE_RE.finditer(body):
            if t.group("tup"):
                p = int(t.group("p"))
                q = int(t.group("q")) if t.group("q") else {2: 3, 3: 2, 4: 3, 6: 2}.get(p, 2)
                tup = [p, Fraction(q, p)]
                continue
            if t.group("bar"):
                mem = {}
                if bars[cur][-1][0] > 0:
                    bars[cur].append([0.0, bar_q()])
                continue
            fac = Fraction(1)
            if tup and tup[0] > 0:
                fac = tup[1]
                tup[0] -= 1
            if t.group("rest"):
                r = t.group("rest")
                d = parse_dur(t.group("rd")) * fac
                if r in "ZX":   # multi-measure rest: N bars
                    dq = bar_q() * (int(t.group("rd")) if t.group("rd").isdigit() else 1)
                else:
                    dq = float(unit * d * 4)
                voices[cur].append(("r", clock[cur], dq, None, ln))
                clock[cur] += dq
                bars[cur][-1][0] += dq
                continue
            letter, oc = t.group("l"), t.group("oc")
            d = parse_dur(t.group("d")) * fac
            dq = float(unit * d * 4)
            up = letter.upper()
            octv = (1 if letter.islower() else 0) + oc.count("'") - oc.count(",")
            key = (up, octv)
            if t.group("acc"):
                semis = {"^": 1, "^^": 2, "_": -1, "__": -2, "=": 0}[t.group("acc")]
                mem[key] = semis
            elif key in mem:
                semis = mem[key]
            else:
                semis = sig.get(up, 0)
            pitch = 60 + NOTE_BASE[up] + semis + 12 * octv
            ev = voices[cur][-1] if voices[cur] else None
            if tie_pending.get(cur) and ev and ev[0] == "n" and ev[3] == pitch:
                voices[cur][-1] = ("n", ev[1], ev[2] + dq, pitch, ev[4])  # merge tie
            else:
                voices[cur].append(("n", clock[cur], dq, pitch, ln))
            tie_pending[cur] = bool(t.group("tie"))
            clock[cur] += dq
            bars[cur][-1][0] += dq
    return dict(meta=dict(tonic=tonic, qpm=qpm, meter=float(meter * 4), meter_str=meter_str or str(meter),
                          unit=str(unit)), voices=voices, bars=bars, warns=warns)


# ---------------------------------------------------------------- features
def sec(q, qpm):
    return q * 60.0 / qpm


def phrases(events, gap_q=1.0):
    out, cur, last_end = [], [], None
    for e in events:
        if e[0] == "r":
            continue
        if cur and e[1] - last_end >= gap_q - 1e-6:
            out.append(cur)
            cur = []
        cur.append(e)
        last_end = e[1] + e[2]
    if cur:
        out.append(cur)
    return out


def intervals(notes):
    return [notes[i + 1][3] - notes[i][3] for i in range(len(notes) - 1)]


def voice_features(ev, meta):
    qpm, tonic = meta["qpm"], meta["tonic"]
    notes = [e for e in ev if e[0] == "n"]
    if not notes:
        return None
    total_q = max(e[1] + e[2] for e in ev)
    snd_q = sum(e[2] for e in notes)
    phr = phrases(ev)
    allp = [n for p in phr for n in p]
    iv = []
    for p in phr:
        iv += intervals(p)
    n_iv = max(len(iv), 1)
    deg = {}
    for n in notes:
        d = DEGREE_NAMES[(n[3] - tonic) % 12]
        deg[d] = deg.get(d, 0) + n[2]
    tot = sum(deg.values())
    S = [intervals(p) for p in phr]
    pairs = [difflib.SequenceMatcher(None, S[i], S[j]).ratio()
             for i in range(len(S)) for j in range(i + 1, len(S))
             if len(S[i]) >= 6 and len(S[j]) >= 6]
    g = {}
    for i in range(len(iv) - 4):
        k = tuple(iv[i:i + 5])
        g[k] = g.get(k, 0) + 1
    top = sorted(g.items(), key=lambda a: -a[1])[:2]
    short = [p for p in phr if len(p) <= 9 and sec(p[0][1], qpm) > 10]
    starts = [sec(p[0][1], qpm) for p in short]
    gaps = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
    best = 0                      # longest run of fills spaced almost evenly (+-25%)
    for i in range(len(gaps)):
        run = [gaps[i]]
        for g in gaps[i + 1:]:
            m = statistics.mean(run)
            if 0.75 * m <= g <= 1.25 * m:
                run.append(g)
            else:
                break
        best = max(best, len(run) + 1)
    streak = best if len(starts) >= 2 else len(starts)
    shapes = {}
    for p in short:
        shapes[tuple(intervals(p))] = shapes.get(tuple(intervals(p)), 0) + 1
    return dict(
        notes=len(notes), length_sec=round(sec(total_q, qpm), 1),
        sounding_pct=round(100 * snd_q / total_q) if total_q else 0,
        notes_per_sec_when_sounding=round(len(notes) / sec(snd_q, qpm), 2) if snd_q else 0,
        median_note_sec=round(sec(statistics.median(n[2] for n in notes), qpm), 2),
        phrases=len(phr), avg_notes_per_phrase=round(len(allp) / len(phr), 1),
        avg_phrase_sec=round(statistics.mean(sec(p[-1][1] + p[-1][2] - p[0][1], qpm) for p in phr), 1),
        repeated_pitch_pct=round(100 * sum(1 for i in iv if i == 0) / n_iv),
        step_pct=round(100 * sum(1 for i in iv if 0 < abs(i) <= 2) / n_iv),
        leap_pct=round(100 * sum(1 for i in iv if abs(i) >= 3) / n_iv),
        range_semitones=max(n[3] for n in notes) - min(n[3] for n in notes),
        similar_phrase_pairs=f"{sum(1 for a in pairs if a >= .7)}/{len(pairs)}",
        most_repeated_5_interval_pattern=[(list(k), c) for k, c in top],
        degrees_pct={k: round(100 * v / tot) for k, v in sorted(deg.items(), key=lambda a: -a[1])},
        short_groups=[dict(at=f"{int(s)//60}:{int(s)%60:02d}", notes=len(p)) for s, p in zip(starts, short)],
        short_group_gap_sec=[round(x) for x in gaps],
        longest_evenly_spaced_run_of_fills=streak,
        distinct_short_shapes=len(shapes),
    )


def features(path):
    P = parse_abc(path)
    out = dict(file=path, key_tonic_pc=P["meta"]["tonic"], tempo_quarter_bpm=P["meta"]["qpm"],
               meter=P["meta"]["meter_str"], voices={})
    for v, ev in P["voices"].items():
        f = voice_features(ev, P["meta"])
        if f:
            out["voices"][v] = f
    return out


# ------------------------------------------------------------------- check
def check(path):
    P = parse_abc(path)
    msgs = []
    ends = {}
    for v, bl in P["bars"].items():
        full = [b for b in bl if b[0] > 0]
        ends[v] = sum(b[0] for b in full)
        for i, (dur, exp) in enumerate(full[:-1]):
            if i == 0 and dur < exp - 1e-6:
                continue  # pickup bar
            ratio = dur / exp
            if abs(ratio - round(ratio)) > 1e-3 or round(ratio) < 1:
                msgs.append(f"voice {v}: bar {i + 1} has {dur:.2f} quarter-notes, meter wants {exp:.2f}")
    if ends and max(ends.values()) - min(ends.values()) > 0.5:
        msgs.append("voices end at different lengths (quarter-notes): " +
                    ", ".join(f"{k}={v:.1f}" for k, v in ends.items()))
    if not any(P["voices"].values()):
        msgs.append("no notes found - is there a K: line before the music?")
    return msgs


# ----------------------------------------------------------------- compare
def main_voice(P, prefer=None):
    cand = {v: [e for e in ev if e[0] == "n"] for v, ev in P["voices"].items()}
    if prefer and prefer in cand and cand[prefer]:
        return prefer
    return max(cand, key=lambda v: len(cand[v]))


def longest_shared(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    m = sm.find_longest_match(0, len(a), 0, len(b))
    return m.size, a[m.a:m.a + m.size]


def contour(events):
    """Pitch-change intervals only: consecutive repeated pitches are collapsed, because
    'the same note ten times' is rhythm/recitation, not a melodic copy."""
    p = [e[3] for e in events if e[0] == "n"]
    q = [x for i, x in enumerate(p) if i == 0 or x != p[i - 1]]
    return [q[i + 1] - q[i] for i in range(len(q) - 1)]


def compare(cand_path, ref_paths):
    C = parse_abc(cand_path)
    rows = []
    for rp in ref_paths:
        R = parse_abc(rp)
        for v in C["voices"]:
            if v not in R["voices"]:
                continue
            a = contour(C["voices"][v])
            b = contour(R["voices"][v])
            if len(a) < 3 or len(b) < 3:
                continue
            n, run = longest_shared(a, b)
            ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
            rows.append(dict(ref=rp, voice=v, longest_identical_interval_run=n,
                             overall_similarity=round(ratio, 2),
                             verdict="TOO CLOSE (>=10 identical moves) - rewrite" if n >= 10
                             else "shares a motif-sized cell (6-9) - fine if intended" if n >= 6 else "ok"))
    return rows



# ============================================================ maqam engine
# Pitch classes are RELATIVE to the tonic (0 = tonic, 1 = semitone above ...).
# The scores are 12-tone snapped, so each maqam is its 12-tone approximation.
#   scale  : the 7 notes of the maqam
#   colour : tolerated guests (counted at half weight, limited share)
#   must   : {degree: minimum share of sounding time}; a maqam without these is not itself
#   pairs  : characteristic neighbour moves (unordered pcs) that give the maqam its identity
MAQAMS = {
    "Ajam":     dict(scale={0, 2, 4, 5, 7, 9, 11}, colour={10}, must={4: .04, 11: .02},
                     pairs=[(4, 5), (11, 0)], pair_text="3->4 semitone or leading-tone 7->1"),
    "Hijaz":    dict(scale={0, 1, 4, 5, 7, 8, 10}, colour={9, 11}, must={1: .03, 4: .03},
                     pairs=[(1, 4)], pair_text="b2<->3 augmented second"),
    "Kurd":     dict(scale={0, 1, 3, 5, 7, 8, 10}, colour=set(), must={1: .03, 3: .04},
                     pairs=[(0, 1), (1, 3)], pair_text="1-b2 or b2-b3 (the Kurd cell)"),
    "Nahawand": dict(scale={0, 2, 3, 5, 7, 8, 10}, colour={11}, must={2: .03, 3: .04},
                     pairs=[(2, 3)], pair_text="2<->b3 semitone"),
}
DEG = {0: "1", 1: "b2", 2: "2", 3: "b3", 4: "3", 5: "4", 6: "b5", 7: "5", 8: "b6", 9: "6", 10: "b7", 11: "7"}
PC_NAMES = ["C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B"]
# starting values: calibrate with `survey` on the real corpus
KEEP_MARGIN = 0.05       # label within this of the best fit -> CONFIRMED
OVERRIDE_MARGIN = 0.15   # best beats label by this much (and is a strong fit) -> OVERRIDE
OVERRIDE_MIN_FIT = 0.65
LOW_FIT = 0.55
OUT_FIX, OUT_WARN = 0.06, 0.03          # share of Vocal time outside scale+colour
INS_OUT_FIX, INS_OUT_WARN = 0.10, 0.05


def parse_tonic(x):
    x = str(x).strip()
    if x.isdigit():
        return int(x) % 12
    m = re.match(r"([A-Ga-g])([#b]?)", x)
    if not m:
        raise SystemExit(f"cannot read tonic '{x}' (use e.g. D, Eb, F#)")
    return (NOTE_BASE[m.group(1).upper()] + (1 if m.group(2) == "#" else -1 if m.group(2) == "b" else 0)) % 12


def maqam_name(x):
    for k in MAQAMS:
        if k.lower() == str(x).lower():
            return k
    raise SystemExit(f"unknown maqam '{x}' (choose from {', '.join(MAQAMS)})")


def main_voice_name(P):
    notes = {v: sum(1 for e in ev if e[0] == "n") for v, ev in P["voices"].items()}
    for v in notes:
        if "vocal" in v.lower() and notes[v]:
            return v
    return max(notes, key=notes.get) if notes else None


def pc_shares(events, tonic):
    w = {}
    for e in events:
        if e[0] == "n":
            pc = (e[3] - tonic) % 12
            w[pc] = w.get(pc, 0.0) + e[2]
    t = sum(w.values())
    return {k: v / t for k, v in w.items()} if t else {}


def phrase_end_shares(events, tonic):
    ends = [(p[-1][3] - tonic) % 12 for p in phrases(events)]
    out = {}
    for x in ends:
        out[x] = out.get(x, 0) + 1 / len(ends)
    return out


def last_pc(events, tonic):
    n = [e for e in events if e[0] == "n"]
    return (n[-1][3] - tonic) % 12 if n else None


def fit_one(M, w, ends, last):
    d = MAQAMS[M]
    g = lambda pcs: sum(w.get(p, 0) for p in pcs)
    cov = g(d["scale"]) + 0.5 * g(d["colour"])
    comp = sum(min(1, w.get(p, 0) / ms) for p, ms in d["must"].items()) / len(d["must"])
    ton = min(1, w.get(0, 0) / 0.14)
    end = 0.5 * (last == 0) + 0.5 * min(1, (ends.get(0, 0) + 0.5 * ends.get(7, 0)) / 0.5)
    return dict(fit=round(0.5 * cov + 0.2 * comp + 0.15 * ton + 0.15 * end, 3),
                coverage=round(cov, 3), must_have=round(comp, 2), tonic_share=round(w.get(0, 0), 3),
                ends_on_tonic=bool(last == 0))


def detect(P, label=None):
    mv = main_voice_name(P)
    if mv is None:
        return None
    res = []
    for t in range(12):
        w = {}
        for v, ev in P["voices"].items():
            wt = 1.0 if v == mv else 0.5
            for k, x in pc_shares(ev, t).items():
                w[k] = w.get(k, 0) + wt * x
        tot = sum(w.values())
        w = {k: x / tot for k, x in w.items()}
        ends = phrase_end_shares(P["voices"][mv], t)
        last = last_pc(P["voices"][mv], t)
        for M in MAQAMS:
            r = fit_one(M, w, ends, last)
            r.update(maqam=M, tonic=t)
            res.append(r)
    res.sort(key=lambda r: -r["fit"])
    best = res[0]
    lab = None
    if label:
        lab = next(r for r in res if r["maqam"] == label)
        if lab["fit"] >= best["fit"] - KEEP_MARGIN:
            status, target = "CONFIRMED", lab
        elif best["fit"] - lab["fit"] >= OVERRIDE_MARGIN and best["fit"] >= OVERRIDE_MIN_FIT:
            status, target = "OVERRIDE", best
        else:
            status, target = "KEEP_LABEL", lab
    else:
        status, target = "NO_LABEL", best
    alt_t = [r for r in res if r["maqam"] == target["maqam"] and r["tonic"] != target["tonic"]
             and r["fit"] >= target["fit"] - 0.04][:2]
    sib = [r for r in res if (r["maqam"], r["tonic"]) != (target["maqam"], target["tonic"])
           and r["fit"] >= target["fit"] - 0.04][:3]
    return dict(main_voice=mv, status=status, target=target, label_best=lab, top=res[:5],
                tonic_alternatives=alt_t, close_rivals=sib, low_fit=target["fit"] < LOW_FIT,
                shares=pc_shares(P["voices"][mv], target["tonic"]))


def cmd_maqam(path, label, as_json=False):
    P = parse_abc(path)
    D = detect(P, label)
    if D is None:
        print(f"{path}: no notes found")
        return 1
    if as_json:
        D2 = dict(D)
        D2["file"] = path
        print(json.dumps(D2, ensure_ascii=False, indent=1, default=list))
        return 0
    T = D["target"]
    print(f"== {path}   (K: tonic in file = {PC_NAMES[P['meta']['tonic']]}; K: is only a transcriber guess)")
    print(f"   label from folder : {label or '-'}")
    print(f"   STATUS            : {D['status']}")
    print(f"   TARGET            : {T['maqam']} on {PC_NAMES[T['tonic']]}   (fit {T['fit']})")
    if D["label_best"]:
        L = D["label_best"]
        print(f"   label's best fit  : {L['maqam']} on {PC_NAMES[L['tonic']]}   (fit {L['fit']})")
    print("   top candidates    : " + "; ".join(f"{r['maqam']}@{PC_NAMES[r['tonic']]} {r['fit']}" for r in D["top"]))
    if D["tonic_alternatives"]:
        print("   TONIC UNSURE      : also " + ", ".join(f"{PC_NAMES[r['tonic']]} ({r['fit']})" for r in D["tonic_alternatives"]))
    if D["close_rivals"]:
        print("   CLOSE RIVALS      : " + ", ".join(f"{r['maqam']}@{PC_NAMES[r['tonic']]} ({r['fit']})" for r in D["close_rivals"])
              + "  (same notes, different home note is common: decide by the ending/tonic evidence)")
    if D["low_fit"]:
        print("   LOW FIT           : no maqam fits well; transcription noise or modulation. Stay inside core notes.")
    sc = MAQAMS[T["maqam"]]
    print(f"   {D['main_voice']} degrees vs target tonic (share of sounding time):")
    for pc, x in sorted(D["shares"].items(), key=lambda a: -a[1]):
        tag = "scale" if pc in sc["scale"] else "colour" if pc in sc["colour"] else "OUTSIDE"
        print(f"      {DEG[pc]:>3}  {round(100 * x):3d}%  {tag}")
    return 0


# ---------------------------------------------------------------- spelling
def spell_midi(target, sig):
    """ABC token (accidental + letter + octave marks) for a MIDI pitch under key signature sig."""
    flat_key = sum(1 for v in sig.values() if v < 0) > 0
    best = None
    for L in "CDEFGAB":
        for oc in (-1, 0, 1, 2):
            for acc, cost in ((None, 0), ("=", 1), ("_" if flat_key else "^", 2), ("^" if flat_key else "_", 3)):
                semis = sig.get(L, 0) if acc is None else {"=": 0, "^": 1, "_": -1}[acc]
                if 60 + NOTE_BASE[L] + semis + 12 * oc == target and (best is None or cost < best[0]):
                    ch = L if oc <= 0 else L.lower()
                    marks = "," * (-oc) if oc < 0 else "'" * (oc - 1) if oc > 1 else ""
                    best = (cost, (acc or "") + ch + marks)
    return best[1] if best else "?"


DEG_LETTER_STEP = {0: 0, 1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 4, 7: 4, 8: 5, 9: 5, 10: 6, 11: 6}


def spell_degree(target, letter, sig):
    """Spell MIDI pitch `target` using the given letter (so F# is written ^F, not _G)."""
    for oc in (-1, 0, 1, 2):
        semis = target - (60 + NOTE_BASE[letter] + 12 * oc)
        if -2 <= semis <= 2:
            acc = "" if semis == sig.get(letter, 0) else {0: "=", 1: "^", -1: "_", 2: "^^", -2: "__"}[semis]
            ch = letter if oc <= 0 else letter.lower()
            return acc + ch + ("," * (-oc) if oc < 0 else "'" * (oc - 1) if oc > 1 else "")
    return spell_midi(target, sig)


def cmd_scale(maq, tonic, key_from):
    M = maqam_name(maq)
    t = parse_tonic(tonic)
    m0 = re.match(r"\s*([A-Ga-g])", str(tonic))
    t_letter = m0.group(1).upper() if m0 else None
    sig = {}
    kline = "C"
    if key_from:
        for l in open(key_from, encoding="utf-8").read().splitlines():
            m = re.match(r"\s*K:\s*(.*)", l)
            if m:
                kline = m.group(1).strip()
                _, sig = key_info(kline)
                break
    d = MAQAMS[M]
    print(f"{M} on {PC_NAMES[t]}, spelled for K:{kline}   (plain letter = already right under this K:; "
          f"^ _ = needs an explicit accidental, which lasts until the barline)")
    base = 60 + t
    if base > 66:
        base -= 12          # keep the tonic near middle C
    def sp(rel, oct_shift=0):
        if t_letter:
            idx = ("CDEFGAB".index(t_letter) + DEG_LETTER_STEP[rel % 12]) % 7
            return spell_degree(base + rel + oct_shift, "CDEFGAB"[idx], sig)
        return spell_midi(base + rel + oct_shift, sig)
    for rel in list(range(12)) + [12]:
        kind = "scale" if rel % 12 in d["scale"] else "colour" if rel % 12 in d["colour"] else "-"
        if kind == "-":
            continue
        print(f"   {DEG[rel % 12]:>3}  {sp(rel):<5} (up an octave: {sp(rel, 12):<5} down: {sp(rel, -12):<5})  {kind}")
    print(f"   characteristic move: {d['pair_text']};  must-have degrees: " +
          ", ".join(f"{DEG[p]} (>= {int(ms * 100)}%)" for p, ms in d["must"].items()))
    return 0


# ------------------------------------------------------------------- modal
def cmd_modal(path, maq, tonic):
    M = maqam_name(maq)
    t = parse_tonic(tonic)
    d = MAQAMS[M]
    P = parse_abc(path)
    mv = main_voice_name(P)
    msgs, info = [], []
    for v, ev in P["voices"].items():
        notes = [e for e in ev if e[0] == "n"]
        if not notes:
            continue
        w = pc_shares(ev, t)
        allowed = d["scale"] | d["colour"]
        out = sum(x for k, x in w.items() if k not in allowed)
        col = sum(x for k, x in w.items() if k in d["colour"])
        fix, warn = (OUT_FIX, OUT_WARN) if v == mv else (INS_OUT_FIX, INS_OUT_WARN)
        tag = f"voice {v}"
        info.append(f"{tag}: outside-scale {round(100 * out)}%, colour notes {round(100 * col)}%")
        if out > fix:
            msgs.append(("FIX", f"{tag}: {round(100 * out)}% of the time is outside {M} on {PC_NAMES[t]}"))
        elif out > warn:
            msgs.append(("WARN", f"{tag}: {round(100 * out)}% outside {M} (passing notes ok, but check)"))
        if col > 0.12:
            msgs.append(("WARN", f"{tag}: colour notes are {round(100 * col)}% (keep guests under ~12%)"))
        bad = [e for e in notes if (e[3] - t) % 12 not in allowed]
        if bad and out > warn:
            lines = {}
            for e in bad:
                lines.setdefault(e[4], set()).add(DEG[(e[3] - t) % 12])
            msgs.append(("  ->", f"{tag} outside notes at source lines: " +
                         "; ".join(f"{l}:{'/'.join(sorted(s))}" for l, s in list(lines.items())[:12])))
        if v == mv:
            for p, ms in d["must"].items():
                if w.get(p, 0) < ms:
                    msgs.append(("FIX", f"{tag}: degree {DEG[p]} is only {round(100 * w.get(p, 0), 1)}% "
                                        f"(needs >= {int(ms * 100)}% for the {M} identity)"))
            cnt = 0
            for p in phrases(ev):
                for a, b in zip(p, p[1:]):
                    x, y = (a[3] - t) % 12, (b[3] - t) % 12
                    if any({x, y} == set(pr) for pr in d["pairs"]):
                        cnt += 1
            info.append(f"{tag}: characteristic moves ({d['pair_text']}) = {cnt}")
            if cnt == 0:
                msgs.append(("FIX", f"{tag}: never plays the characteristic move ({d['pair_text']})"))
            elif cnt < 3:
                msgs.append(("WARN", f"{tag}: characteristic move only {cnt}x ({d['pair_text']})"))
            lp = last_pc(ev, t)
            if lp != 0:
                lvl = "WARN" if lp == 7 else "FIX"
                msgs.append((lvl, f"{tag}: last note is degree {DEG[lp]}, not the tonic (1)"))
            ends = phrase_end_shares(ev, t)
            info.append(f"{tag}: phrase endings on tonic {round(100 * ends.get(0, 0))}%, on 5th {round(100 * ends.get(7, 0))}%")
            if ends.get(0, 0) < 0.15:
                msgs.append(("WARN", f"{tag}: only {round(100 * ends.get(0, 0))}% of phrases rest on the tonic; "
                                     "a maqam needs a clear home note"))
    bad = any(m[0] == "FIX" for m in msgs)
    print(("FIX  " if bad else "OK   ") + f"{path}   [{M} on {PC_NAMES[t]}]")
    for l, m in msgs:
        print(f"   {l:5} {m}")
    for i in info:
        print(f"   info  {i}")
    return 1 if bad else 0


# ------------------------------------------------------------------ traits
TRAIT_METRICS = [  # (key, high means, low means)
    ("avg_notes_per_phrase", "long recited phrases", "short singable phrases"),
    ("avg_phrase_sec", "long phrases in time", "short phrases in time"),
    ("repeated_pitch_pct", "much sitting on one note (recitation)", "little repeated-note recitation"),
    ("step_pct", "very smooth stepwise motion", "less stepwise motion"),
    ("leap_pct", "many leaps", "few leaps"),
    ("notes_per_sec_when_sounding", "busy rhythm", "spacious, slow rhythm"),
    ("sounding_pct", "singer rarely rests", "lots of silence"),
    ("range_semitones", "wide range", "narrow range"),
    ("fills_per_min", "many short answers/fills", "few or no fills"),
    ("distinct_short_shapes", "many unrelated fill shapes", "one or two signature fill shapes"),
    ("ins_sounding_pct", "accompaniment line speaks a lot", "accompaniment line nearly silent"),
    ("length_sec", "long song", "short song"),
]


def trait_vector(path):
    P = parse_abc(path)
    mv = main_voice_name(P)
    if mv is None:
        return None
    f = voice_features(P["voices"][mv], P["meta"])
    if not f:
        return None
    ins = [v for v in P["voices"] if v != mv]
    insf = voice_features(P["voices"][ins[0]], P["meta"]) if ins else None
    f = dict(f)
    f["fills_per_min"] = round(len(f["short_groups"]) / max(f["length_sec"] / 60, 0.1), 2)
    f["ins_sounding_pct"] = insf["sounding_pct"] if insf else 0
    return f


def cmd_traits(path, peers_dir):
    import os
    mine = trait_vector(path)
    if mine is None:
        print("no notes found")
        return 1
    root = peers_dir or os.path.dirname(os.path.dirname(os.path.abspath(path)))
    me = os.path.abspath(path)
    peers = [v for v in (trait_vector(p) for p in find_scores(root) if os.path.abspath(p) != me) if v]
    print(f"== {path}: compared with {len(peers)} sibling songs under {root}")
    if len(peers) < 4:
        print("   too few siblings for a fair comparison; describe the song by its own numbers only.")
    rows = []
    for key, hi, lo in TRAIT_METRICS:
        vals = [p[key] for p in peers if key in p]
        if len(vals) < 4:
            continue
        mu, sd = statistics.mean(vals), statistics.pstdev(vals)
        sd = max(sd, 1e-6, 0.05 * abs(mu))
        z = (mine[key] - mu) / sd
        rows.append((abs(z), z, key, mine[key], round(mu, 2), hi if z > 0 else lo))
    rows.sort(reverse=True)
    for _, z, key, val, mu, txt in rows[:5]:
        print(f"   {key:<28} this={val:<7} siblings~{mu:<7} z={z:+.1f}  -> {txt}")
    if rows:
        print("   (|z| < 1 means ordinary for this folder; the top 2-3 rows with |z| >= 1 are this song's flavor.)")
    return 0


# -------------------------------------------------------- survey / progress
LABEL_RE = re.compile(r"^(Ajam|Hijaz|Kurd|Nahawand)", re.I)


def find_scores(root):
    import os
    out = []
    for dp, dn, fn in os.walk(root):
        if "score.abc" in fn:
            out.append(os.path.join(dp, "score.abc"))
    return sorted(out)


def label_of(path):
    """Maqam label = the folder whose name starts with a maqam name (e.g. Hijaz_Shortlist)."""
    for part in reversed(path.replace("\\", "/").split("/")[:-1]):
        m = LABEL_RE.match(part)
        if m:
            return maqam_name(m.group(1))
    return None


def cmd_survey(root):
    rows = []
    for p in find_scores(root):
        D = detect(parse_abc(p), label_of(p))
        if D is None:
            rows.append((p, label_of(p), "EMPTY", "", "", "", ""))
            continue
        T, L = D["target"], D["label_best"]
        rows.append((p, label_of(p), D["status"], f"{T['maqam']}@{PC_NAMES[T['tonic']]}", T["fit"],
                     L["fit"] if L else "", ("tonic-unsure " if D["tonic_alternatives"] else "") + ("low-fit" if D["low_fit"] else "")))
    print("status,label,target,target_fit,label_fit,notes,path")
    for p, lab, st, tg, tf, lf, nt in rows:
        print(f"{st},{lab},{tg},{tf},{lf},{nt.strip()},{p}")
    from collections import Counter
    c = Counter(r[2] for r in rows)
    print(f"\n# {len(rows)} scores: " + ", ".join(f"{k}={v}" for k, v in c.items()))
    print("# Expect most CONFIRMED. If many are OVERRIDE/KEEP_LABEL, either the labels or the thresholds "
          "(KEEP_MARGIN etc. at the top of abc_tool.py) need a look.")
    return 0


def cmd_progress(root):
    import os
    need = ["VAR_A_score.abc", "VAR_B_score.abc", "VAR_C_score.abc", "VAR_REPORT.md"]
    done = todo = 0
    for p in find_scores(root):
        d = os.path.dirname(p)
        miss = [n for n in need if not os.path.exists(os.path.join(d, n))]
        if miss:
            todo += 1
            print(f"TODO  {d}   missing: {', '.join(miss)}")
        else:
            done += 1
    print(f"# done {done}, todo {todo}")
    return 0


# --------------------------------------------------------------------- cli
def main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="abc_tool.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("features"); a.add_argument("files", nargs="+"); a.add_argument("--json", action="store_true")
    a.add_argument("--tonic", help="override the (unreliable) K: tonic, e.g. D")
    a = sp.add_parser("check"); a.add_argument("files", nargs="+")
    a = sp.add_parser("compare"); a.add_argument("cand"); a.add_argument("refs", nargs="*")
    a.add_argument("--others", nargs="*", default=[])
    a = sp.add_parser("maqam"); a.add_argument("file"); a.add_argument("--label"); a.add_argument("--json", action="store_true")
    a = sp.add_parser("scale"); a.add_argument("--maqam", required=True); a.add_argument("--tonic", required=True)
    a.add_argument("--key-from")
    a = sp.add_parser("modal"); a.add_argument("files", nargs="+"); a.add_argument("--maqam", required=True)
    a.add_argument("--tonic", required=True)
    a = sp.add_parser("traits"); a.add_argument("file"); a.add_argument("--peers")
    a = sp.add_parser("survey"); a.add_argument("root")
    a = sp.add_parser("progress"); a.add_argument("root")
    args = ap.parse_args(argv[1:])
    c = args.cmd
    if c == "features":
        res = []
        for f in args.files:
            P = parse_abc(f)
            if args.tonic:
                P["meta"]["tonic"] = parse_tonic(args.tonic)
            out = dict(file=f, key_tonic_pc=P["meta"]["tonic"], tempo_quarter_bpm=P["meta"]["qpm"],
                       meter=P["meta"]["meter_str"], voices={})
            for v, ev in P["voices"].items():
                ft = voice_features(ev, P["meta"])
                if ft:
                    out["voices"][v] = ft
            res.append(out)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            for r in res:
                print(f"== {r['file']}  (tempo ~{r['tempo_quarter_bpm']:.0f} bpm, meter {r['meter']})")
                for v, ft in r["voices"].items():
                    print(f"  [{v}]")
                    for k, val in ft.items():
                        print(f"    {k}: {val}")
        return 0
    if c == "check":
        bad = 0
        for f in args.files:
            m = check(f)
            print(("OK   " if not m else "FIX  ") + f)
            for x in m:
                print("   -", x)
            bad += bool(m)
        return 1 if bad else 0
    if c == "compare":
        for title, paths in (("vs references", args.refs), ("vs other candidates", args.others)):
            if not paths:
                continue
            print(f"== {args.cand} {title}")
            for r in compare(args.cand, paths):
                print(f"   {r['ref']} [{r['voice']}]: longest identical run = "
                      f"{r['longest_identical_interval_run']} intervals, "
                      f"similarity {r['overall_similarity']} -> {r['verdict']}")
        return 0
    if c == "maqam":
        return cmd_maqam(args.file, maqam_name(args.label) if args.label else None, args.json)
    if c == "scale":
        return cmd_scale(args.maqam, args.tonic, args.key_from)
    if c == "modal":
        return max(cmd_modal(f, args.maqam, args.tonic) for f in args.files)
    if c == "traits":
        return cmd_traits(args.file, args.peers)
    if c == "survey":
        return cmd_survey(args.root)
    if c == "progress":
        return cmd_progress(args.root)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
