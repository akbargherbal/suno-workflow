#!/usr/bin/env python3
"""MIDI (.mid/.midi, incl. pitch bend) and MusicXML (.xml/.musicxml/.mxl) -> the same Score
model that abc_parse.py produces, so analyze_abc.py can analyse all three. Dependency-free.

    python import_score.py song.mid          # prints a summary
    python import_score.py song.musicxml

Microtonal information
  MIDI    note numbers are 12-TET. Quarter tones exist only as PITCH BEND; the bend in force
          (duration-weighted mean over the note) is added in cents. Bend range comes from
          RPN 0 if present, otherwise +-2 semitones. Vocal-to-MIDI converters that write
          vibrato as bend will add small non-zero offsets; a file whose only bends are
          small is effectively 12-TET.
  XML     <alter> may be fractional (0.5 = quarter-tone sharp); all values are honoured.
Not handled: SMPTE time division, tempo maps beyond the first tempo, lyrics, grace notes.
"""
from __future__ import annotations

import os
import re
import struct
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from abc_parse import Note, Score, summary, parse_abc_all           # noqa: E402

MAJOR_BY_FIFTHS = {0: "C", 1: "G", 2: "D", 3: "A", 4: "E", 5: "B", 6: "F#", 7: "C#",
                   -1: "F", -2: "Bb", -3: "Eb", -4: "Ab", -5: "Db", -6: "Gb", -7: "Cb"}
MINOR_BY_FIFTHS = {0: "A", 1: "E", 2: "B", 3: "F#", 4: "C#", 5: "G#", 6: "D#", 7: "A#",
                   -1: "D", -2: "G", -3: "C", -4: "F", -5: "Bb", -6: "Eb", -7: "Ab"}


def key_name(fifths: int, minor: bool) -> str:
    return (MINOR_BY_FIFTHS if minor else MAJOR_BY_FIFTHS).get(fifths, "") + ("m" if minor else "")


# ----------------------------------------------------------------------------- MIDI
def _vlq(data, i):
    v = 0
    while True:
        b = data[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, i


def parse_midi(path: str) -> Score:
    data = open(path, "rb").read()
    if data[:4] != b"MThd":
        raise SystemExit(f"{path}: not a standard MIDI file")
    fmt, ntrk, div = struct.unpack(">HHH", data[8:14])
    if div & 0x8000:
        raise SystemExit("SMPTE time division is not supported")
    ppq = div
    sc = Score(path=path, source="midi")
    i = 8 + struct.unpack(">I", data[4:8])[0]
    tracks = []
    while i + 8 <= len(data):
        cid, ln = data[i:i + 4], struct.unpack(">I", data[i + 4:i + 8])[0]
        if cid == b"MTrk":
            tracks.append(data[i + 8:i + 8 + ln])
        i += 8 + ln

    pending_voices = {}          # vid -> list of (start_tick, end_tick, midi_note, channel)
    bends = {}                   # (track, channel) -> [(tick, value)]
    bend_range = {}              # (track, channel) -> semitones
    names = {}
    key_meta = None
    for ti, tr in enumerate(tracks):
        pos, tick, status = 0, 0, 0
        active = {}              # (ch, note) -> [start ticks]
        rpn = {}                 # ch -> [msb, lsb]
        tname = ""
        while pos < len(tr):
            delta, pos = _vlq(tr, pos)
            tick += delta
            b = tr[pos]
            if b == 0xFF:        # meta
                mtype = tr[pos + 1]
                ln, p2 = _vlq(tr, pos + 2)
                body = tr[p2:p2 + ln]
                pos = p2 + ln
                if mtype == 0x03 and not tname:
                    tname = body.decode("latin-1", "replace").strip()
                elif mtype == 0x51 and ln == 3 and sc.tempo_bpm is None:
                    sc.tempo_bpm = round(60e6 / int.from_bytes(body, "big"), 2)
                elif mtype == 0x59 and ln == 2 and key_meta is None:
                    sf = body[0] - 256 if body[0] > 127 else body[0]
                    key_meta = key_name(sf, bool(body[1]))
                elif mtype == 0x06 and body.strip():              # marker -> section label
                    sc.sections.append((body.decode("latin-1", "replace").strip(), "", tick / ppq))
                continue
            if b in (0xF0, 0xF7):
                ln, p2 = _vlq(tr, pos + 1)
                pos = p2 + ln
                continue
            if b & 0x80:
                status = b
                pos += 1
            kind, ch = status & 0xF0, status & 0x0F
            nbytes = 1 if kind in (0xC0, 0xD0) else 2
            args = tr[pos:pos + nbytes]
            pos += nbytes
            if kind == 0x90 and args[1] > 0:
                active.setdefault((ch, args[0]), []).append(tick)
            elif kind == 0x80 or (kind == 0x90 and args[1] == 0):
                st = active.get((ch, args[0]))
                if st:
                    s0 = st.pop(0)
                    if ch != 9:                                       # skip percussion
                        pending_voices.setdefault((ti, ch), []).append((s0, tick, args[0]))
            elif kind == 0xE0:
                bends.setdefault((ti, ch), []).append((tick, ((args[1] << 7) | args[0])))
            elif kind == 0xB0:
                cc, val = args[0], args[1]
                r = rpn.setdefault(ch, [None, None])
                if cc == 101:
                    r[0] = val
                elif cc == 100:
                    r[1] = val
                elif cc == 6 and r == [0, 0]:
                    bend_range[(ti, ch)] = float(val)
        names[ti] = tname
    if key_meta:
        sc.declared_key = key_meta
        sc.warnings.append("MIDI key-signature meta is often a DAW default (C major); it counts as tool evidence only")

    for (ti, ch), evs in sorted(pending_voices.items()):
        vid = f"t{ti}c{ch}"
        sc.voices[vid] = (names.get(ti) or f"Track {ti}") + f" ch{ch + 1}"
        blist = sorted(bends.get((ti, ch), []))
        rng = bend_range.get((ti, ch), 2.0)
        used_bend = False
        for s0, e0, nn in sorted(evs):
            off = _mean_bend(blist, s0, e0) * rng * 100.0 if blist else 0.0
            used_bend = used_bend or abs(off) > 1
            sc.notes.append(Note(vid, s0 / ppq, max(e0 - s0, 1) / ppq, nn * 100.0 + off, 0, "", key_meta or ""))
        if used_bend:
            sc.warnings.append(f"{vid}: pitch bend applied (+-{rng:g} semitone range assumed unless RPN set)")
    if not sc.notes:
        sc.warnings.append("no pitched notes found")
    sc.notes.sort(key=lambda n: (n.voice, n.start))
    return sc


def _mean_bend(blist, s0, e0):
    """Duration-weighted mean bend (-1..+1 of full range) over [s0, e0)."""
    cur, total, t = 0.0, 0.0, s0
    for tk, v in blist:
        val = (v - 8192) / 8192.0
        if tk <= s0:
            cur = val
            continue
        if tk >= e0:
            break
        total += cur * (tk - t)
        t, cur = tk, val
    total += cur * (e0 - t)
    return total / max(e0 - s0, 1)


# ------------------------------------------------------------------------- MusicXML
STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _read_xml(path: str):
    if path.lower().endswith(".mxl"):
        with zipfile.ZipFile(path) as z:
            root_name = None
            if "META-INF/container.xml" in z.namelist():
                c = ET.fromstring(z.read("META-INF/container.xml"))
                for rf in c.iter("rootfile"):
                    root_name = rf.get("full-path")
                    break
            root_name = root_name or next(n for n in z.namelist() if n.lower().endswith(".xml") and not n.startswith("META"))
            return ET.fromstring(z.read(root_name))
    txt = open(path, "rb").read()
    txt = re.sub(rb"<!DOCTYPE[^>]*>", b"", txt)          # drop the DTD reference (no network, no entities)
    return ET.fromstring(txt)


def parse_musicxml(path: str) -> Score:
    root = _read_xml(path)
    sc = Score(path=path, source="musicxml")
    names = {sp.get("id"): (sp.findtext("part-name") or sp.get("id")) for sp in root.iter("score-part")}
    ttl = root.findtext(".//movement-title") or root.findtext(".//work/work-title") or ""
    sc.title = ttl.strip()
    for part in root.findall("part"):
        pid = part.get("id") or "P"
        sc.voices[pid] = names.get(pid, pid)
        div, pos, section, key = 1, 0, "", ""
        last_by_pitch = {}
        for meas in part.findall("measure"):
            mstart = pos
            maxpos = pos
            last_start = pos
            for el in meas:
                tag = el.tag
                if tag == "attributes":
                    d = el.findtext("divisions")
                    if d:
                        div = max(int(float(d)), 1)
                    k = el.find("key")
                    if k is not None and k.findtext("fifths") is not None:
                        key = key_name(int(k.findtext("fifths")), (k.findtext("mode") or "") == "minor")
                        if not sc.declared_key:
                            sc.declared_key = key
                        else:
                            sc.keys.append((pid, pos / div, key))
                elif tag == "direction":
                    reh = el.find(".//rehearsal")
                    if reh is not None and (reh.text or "").strip():
                        section = reh.text.strip()
                        sc.sections.append((section, pid, pos / div))
                    snd = el.find("sound")
                    if snd is not None and snd.get("tempo") and sc.tempo_bpm is None:
                        sc.tempo_bpm = float(snd.get("tempo"))
                elif tag == "harmony":
                    r = el.find("root")
                    if r is not None:
                        alt = int(float(r.findtext("root-alter") or 0))
                        sym = r.findtext("root-step") + ("#" * alt if alt > 0 else "b" * -alt)
                        if (el.findtext("kind") or "").startswith("minor"):
                            sym += "m"
                        sc.chords.append((pid, pos / div, sym, section))
                elif tag == "backup":
                    pos -= int(float(el.findtext("duration") or 0))
                elif tag == "forward":
                    pos += int(float(el.findtext("duration") or 0))
                elif tag == "note":
                    if el.find("grace") is not None:
                        continue
                    dur = int(float(el.findtext("duration") or 0))
                    is_chord = el.find("chord") is not None
                    start = last_start if is_chord else pos
                    if not is_chord:
                        last_start = pos
                    if el.find("rest") is None and el.find("pitch") is not None:
                        pt = el.find("pitch")
                        alter = float(pt.findtext("alter") or 0)
                        cents = 100.0 * (12 * (int(pt.findtext("octave")) + 1) + STEP[pt.findtext("step")] + alter)
                        ties = {t.get("type") for t in el.findall("tie")}
                        prev = last_by_pitch.get((pid, cents))
                        if "stop" in ties and prev is not None and abs(prev.start + prev.dur - start / div) < 1e-6:
                            prev.dur += dur / div
                        else:
                            n = Note(pid, start / div, dur / div, cents, 0, section, key)
                            sc.notes.append(n)
                            last_by_pitch[(pid, cents)] = n
                    if not is_chord:
                        pos += dur
                maxpos = max(maxpos, pos)
            pos = max(pos, maxpos)
    if not sc.notes:
        sc.warnings.append("no pitched notes found")
    sc.warnings.append("MusicXML <accidental> marks are ignored; pitch comes from <step>/<alter>/<octave>")
    return sc


# ------------------------------------------------------------------------- dispatch
def load_scores(path: str) -> list:
    """Return a list of Score objects (ABC files may hold several tunes)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".mid", ".midi", ".kar"):
        return [parse_midi(path)]
    if ext in (".xml", ".musicxml", ".mxl"):
        return [parse_musicxml(path)]
    return parse_abc_all(path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for s in load_scores(sys.argv[1]):
        print(summary(s))
