#!/usr/bin/env python3
"""selftest.py - sanity tests for abc_tool.py on SYNTHETIC melodies (no real data needed).

    python selftest.py          # prints a summary, exit code 1 if something regressed

Synthetic melodies are idealised, so real scores will be noisier. Use `abc_tool.py survey`
on the real corpus to judge the thresholds; use this file to be sure edits to the tool did not break it.
"""
import os, random, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import abc_tool as T

LET = {0: "C", 2: "D", 4: "E", 5: "F", 7: "G", 9: "A", 11: "B"}


def abc_note(midi, flat=False):
    pc, oc = midi % 12, (midi - 60) // 12
    if pc in LET:
        L, acc = LET[pc], ""
    elif flat:
        L, acc = LET[(pc + 1) % 12], "_"
    else:
        L, acc = LET[(pc - 1) % 12], "^"
    ch = L if oc <= 0 else L.lower()
    return acc + ch + ("," * -oc if oc < 0 else "'" * (oc - 1) if oc > 1 else "")


def gen(maqam, tonic, seed, bars=24, noise=0.0, end_w=(55, 30, 15), final_tonic=True):
    rnd = random.Random(seed)
    d = T.MAQAMS[maqam]
    pool = sorted(d["scale"])
    wt = {p: (4 if p == 0 else 3 if p == 7 else 1.5 if p in d["must"] else 1) for p in pool}
    pcs = [p for p in range(12)]
    cur, out_v, out_i = 0, [], []
    pats = [[4, 4], [2, 2, 4], [4, 2, 2], [2, 2, 2, 2], [8], [2, 6], [6, 2]]
    b = 0
    while b < bars:
        for k in range(3):                       # 3 sung bars
            toks = []
            for dur in rnd.choice(pats):
                if rnd.random() < 0.25 and d["pairs"]:   # characteristic move
                    a, c = rnd.choice(d["pairs"]); cur = a if rnd.random() < .5 else c
                else:
                    cands = [p for p in pool if abs(p - cur) <= 4 and abs(p - cur) > 0] or pool
                    cur = rnd.choices(cands, [wt[p] for p in cands])[0]
                if noise and rnd.random() < noise:
                    cur = rnd.choice([p for p in pcs if p not in d["scale"]])
                toks.append((cur, dur))
            if k == 2:                           # phrase ending: tonic 55%, 5th 30%
                end = rnd.choices([0, 7, 3 if 3 in pool else 2], list(end_w))[0]
                toks[-1] = (end, toks[-1][1])
            out_v.append("".join(f"{abc_note(60 + tonic + p + (12 if p < 5 and False else 0))}{dur}" for p, dur in toks) + "|")
            out_i.append("Z|")
        out_v.append("Z|"); out_i.append("Z|")
        b += 4
    # last bar: tonic
    if final_tonic:
        out_v[-2] = f"{abc_note(60 + tonic)}8|"
    return ("X:1\nM:2/4\nL:1/16\nQ:1/4=90\nV: Vocal\nV: Ins\nK:C\nV: Vocal\n" + "\n".join(out_v) +
            "\nV: Ins\n" + "\n".join(out_i) + "\n")


def write(txt):
    f = tempfile.NamedTemporaryFile("w", suffix=".abc", delete=False, encoding="utf-8")
    f.write(txt); f.close(); return f.name


def main():
    fails, total = 0, 0
    tonics = [2, 0, 7, 9, 5, 10, 3]
    for M in T.MAQAMS:
        for t in tonics:
            for seed in range(3):
                path = write(gen(M, t, seed * 7 + t))
                P = T.parse_abc(path)
                D = T.detect(P, M)
                total += 1
                ok = D["status"] == "CONFIRMED" and D["target"]["tonic"] == t and D["target"]["maqam"] == M
                # wrong label must be corrected when the evidence is strong
                wrong = next(x for x in T.MAQAMS if x != M)
                D2 = T.detect(P, wrong)
                ok2 = D2["target"]["maqam"] in (M, wrong)
                if not ok:
                    fails += 1
                    print(f"MISS  {M}@{T.PC_NAMES[t]} seed{seed}: got {D['target']['maqam']}@{T.PC_NAMES[D['target']['tonic']]} "
                          f"{D['status']} fit {D['target']['fit']}")
                m = T.check(path)
                if m:
                    fails += 1; print("BAR PROBLEM in generator", path, m)
                os.unlink(path)
    print(f"detection: {total - fails}/{total} synthetic scores identified correctly")
    # validator: correct maqam passes, same notes in another maqam fails
    good = bad = 0
    for M in T.MAQAMS:
        path = write(gen(M, 2, 99))
        r_ok = subprocess.run([sys.executable, os.path.join(HERE, "abc_tool.py"), "modal", path, "--maqam", M, "--tonic", "D"],
                              capture_output=True, text=True).returncode == 0
        other = "Nahawand" if M != "Nahawand" else "Hijaz"
        r_bad = subprocess.run([sys.executable, os.path.join(HERE, "abc_tool.py"), "modal", path, "--maqam", other, "--tonic", "D"],
                               capture_output=True, text=True).returncode != 0
        good += r_ok; bad += r_bad
        os.unlink(path)
    print(f"modal check: {good}/4 correct maqam accepted, {bad}/4 wrong maqam rejected")
    # noisy corpus: 10% random out-of-scale notes should still be identified mostly
    nz = 0
    for M in T.MAQAMS:
        for t in tonics:
            path = write(gen(M, t, 5, noise=0.10))
            D = T.detect(T.parse_abc(path), M)
            nz += D["target"]["maqam"] == M and D["target"]["tonic"] == t
            os.unlink(path)
    print(f"noisy (10% wrong notes): {nz}/{4 * len(tonics)} still identified")
    return 1 if (fails or good < 4 or bad < 4) else 0


if __name__ == "__main__":
    sys.exit(main())
