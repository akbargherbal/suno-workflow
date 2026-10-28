#!/usr/bin/env python3
"""
abc_tool.py - measure, validate and compare ABC scores (stdlib only).

  python abc_tool.py features a.abc [b.abc ...] [--json]
  python abc_tool.py check    a.abc [b.abc ...]
  python abc_tool.py compare  candidate.abc ref1.abc [ref2.abc ...] [--others other_candidate.abc ...]

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

    for raw in text.splitlines():
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
                voices[cur].append(("r", clock[cur], dq, None))
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
                voices[cur][-1] = ("n", ev[1], ev[2] + dq, pitch)  # merge tie
            else:
                voices[cur].append(("n", clock[cur], dq, pitch))
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


# --------------------------------------------------------------------- cli
def main(argv):
    if len(argv) < 3 or argv[1] not in ("features", "check", "compare"):
        print(__doc__)
        return 1
    cmd, args = argv[1], argv[2:]
    if cmd == "features":
        js = "--json" in args
        res = [features(a) for a in args if not a.startswith("--")]
        if js:
            print(json.dumps(res, ensure_ascii=False, indent=1))
        else:
            for r in res:
                print(f"== {r['file']}  (tempo ~{r['tempo_quarter_bpm']:.0f} bpm, meter {r['meter']})")
                for v, f in r["voices"].items():
                    print(f"  [{v}]")
                    for k, val in f.items():
                        print(f"    {k}: {val}")
    elif cmd == "check":
        bad = 0
        for a in args:
            m = check(a)
            print(("OK   " if not m else "FIX  ") + a)
            for x in m:
                print("   -", x)
            bad += bool(m)
        return 1 if bad else 0
    else:
        others = []
        if "--others" in args:
            i = args.index("--others")
            others = args[i + 1:]
            args = args[:i]
        cand, refs = args[0], args[1:]
        for title, paths in (("vs references", refs), ("vs other candidates", others)):
            if not paths:
                continue
            print(f"== {cand} {title}")
            for r in compare(cand, paths):
                print(f"   {r['ref']} [{r['voice']}]: longest identical run = "
                      f"{r['longest_identical_interval_run']} intervals, "
                      f"similarity {r['overall_similarity']} -> {r['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
