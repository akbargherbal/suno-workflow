#!/usr/bin/env python3
"""
align_lyrics.py

Align a clean lyrics text file to the timing of a Suno-exported,
word/syllable-level ("karaoke style") .srt file, producing a plain
line-by-line .srt suitable for YouTube and similar players.

This is written to be lyrics/song-agnostic: point it at any `original.txt`
(the correct, full lyrics) plus the matching Suno `.srt` and it will do its
best to line them up. It is NOT specific to any one song.

Usage
-----
    python align_lyrics.py original.txt suno.srt -o output.srt

How it works
------------
Suno's .srt breaks lyrics into small, arbitrarily-sized timed fragments
(often mid-word) and injects section tags such as "[Verse]" or
"[Instrumental Bridge - 15 seconds]" into the fragment text. There is no
reliable 1:1 mapping between Suno's fragments and the "real" lyric lines
you want to display, so this script aligns them by letter content instead
of by line/fragment position:

1. Read every line of `original.txt`. Any line that has no letters left
   after stripping diacritics/tatweel/punctuation is treated as a
   structural marker (blank line, "[Verse]", a comment line, etc.) and
   ignored for timing -- it just becomes a boundary between lyric lines,
   not a subtitle cue itself.
2. Read every entry of the Suno .srt. Each entry contributes only its
   letters (diacritics/tatweel stripped) to one continuous timeline.
   This automatically discards bracket tags and any Latin-script text
   Suno injects, without needing to special-case them.
3. Use difflib's matching-blocks alignment to map the letters of
   `original.txt` onto the letters of the Suno timeline. Since both are
   (mostly) the same lyrics in the same order, this recovers, for each
   original line, the first and last Suno fragment it corresponds to --
   and therefore a start/end time.
4. Emit one subtitle cue per lyric line from `original.txt`, using your
   ORIGINAL text (never Suno's fragment text).
5. Any line that can't be confidently matched (Suno sometimes drops or
   garbles words) is flagged with a warning on stderr, and given an
   interpolated best-effort timing instead of being silently guessed at.

Language note: matching currently keys off the Arabic letter block
(U+0621-U+064A) and strips Arabic diacritics/tatweel. If you use this on
lyrics in another script, adjust `ARABIC_LETTER_RANGE` /
`ARABIC_DIACRITICS_AND_TATWEEL` accordingly (see README.md).
"""

import argparse
import difflib
import re
import sys
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

ARABIC_DIACRITICS_AND_TATWEEL = re.compile(
    r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED\u0640]'
)
ARABIC_LETTER_RANGE = (0x0621, 0x064A)  # inclusive


def normalize(text: str) -> str:
    """Strip diacritics/tatweel, then keep only base letters.

    Everything else (tags, digits, Latin text, punctuation, whitespace)
    disappears -- which is exactly what lets Suno's bracket tags fall away
    on their own without any special-casing.
    """
    text = ARABIC_DIACRITICS_AND_TATWEEL.sub('', text)
    lo, hi = ARABIC_LETTER_RANGE
    return ''.join(ch for ch in text if lo <= ord(ch) <= hi)


# ---------------------------------------------------------------------------
# SRT parsing helpers
# ---------------------------------------------------------------------------

TIME_RE = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})')


def parse_time(ts: str) -> int:
    """SRT timestamp -> milliseconds."""
    m = TIME_RE.match(ts.strip())
    if not m:
        raise ValueError(f"Bad SRT timestamp: {ts!r}")
    h, mnt, s, ms = map(int, m.groups())
    return ((h * 60 + mnt) * 60 + s) * 1000 + ms


def format_time(ms: int) -> str:
    ms = max(0, ms)
    h, rem = divmod(ms, 3_600_000)
    mnt, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1_000)
    return f"{h:02d}:{mnt:02d}:{s:02d},{ms:03d}"


@dataclass
class SrtEntry:
    index: int
    start_ms: int
    end_ms: int
    text: str


def parse_srt(path: str) -> list:
    with open(path, encoding='utf-8') as f:
        raw = f.read()

    blocks = re.split(r'\n\s*\n', raw.strip())
    entries = []
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip() != '']
        if len(lines) < 2:
            continue
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        m = re.match(r'(.+?)-->(.+)', lines[1])
        if not m:
            continue
        start_ms = parse_time(m.group(1))
        end_ms = parse_time(m.group(2))
        text = ' '.join(lines[2:])
        entries.append(SrtEntry(idx, start_ms, end_ms, text))
    return entries


# ---------------------------------------------------------------------------
# Original lyrics parsing
# ---------------------------------------------------------------------------

@dataclass
class LyricLine:
    raw_text: str
    normalized: str
    line_no: int  # 1-based line number in original.txt, for warnings


def parse_original(path: str) -> list:
    with open(path, encoding='utf-8') as f:
        raw_lines = f.read().splitlines()

    lyric_lines = []
    for i, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        norm = normalize(stripped)
        if not norm:
            # Structural marker: [Verse], [Instrumental Bridge ...],
            # "///***///", etc. Not a subtitle cue -- just a boundary.
            continue
        lyric_lines.append(LyricLine(stripped, norm, i))
    return lyric_lines


# ---------------------------------------------------------------------------
# Build the Suno normalized timeline
# ---------------------------------------------------------------------------

def build_suno_timeline(entries: list):
    """Returns (suno_norm_chars: str, char_to_entry: list[int])."""
    chars = []
    char_to_entry = []
    for entry in entries:
        norm = normalize(entry.text)
        for ch in norm:
            chars.append(ch)
            char_to_entry.append(entry.index)
    return ''.join(chars), char_to_entry


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

def align(original_lines, suno_norm, char_to_entry, entries_by_index):
    orig_stream_parts = []
    line_ranges = []  # (start_offset, end_offset) per line, in orig_stream
    offset = 0
    for line in original_lines:
        orig_stream_parts.append(line.normalized)
        start = offset
        offset += len(line.normalized)
        line_ranges.append((start, offset))
    orig_stream = ''.join(orig_stream_parts)

    sm = difflib.SequenceMatcher(None, orig_stream, suno_norm, autojunk=False)
    matching_blocks = sm.get_matching_blocks()

    matched_map = {}  # orig_offset -> suno_offset
    for a, b, size in matching_blocks:
        for k in range(size):
            matched_map[a + k] = b + k

    results = []
    for line, (start, end) in zip(original_lines, line_ranges):
        suno_offsets = [matched_map[o] for o in range(start, end) if o in matched_map]
        if not suno_offsets:
            results.append({'line': line, 'start_ms': None, 'end_ms': None, 'aligned': False})
            continue
        first_entry_idx = char_to_entry[min(suno_offsets)]
        last_entry_idx = char_to_entry[max(suno_offsets)]
        start_ms = entries_by_index[first_entry_idx].start_ms
        end_ms = entries_by_index[last_entry_idx].end_ms
        coverage = len(suno_offsets) / (end - start)
        results.append({
            'line': line, 'start_ms': start_ms, 'end_ms': end_ms,
            'aligned': True, 'coverage': coverage,
        })
    return results


def fill_gaps_and_fix_overlaps(results, total_end_ms):
    """Interpolate timing for unaligned lines from aligned neighbours,
    then make sure cues never go backwards or overlap."""
    n = len(results)

    i = 0
    while i < n:
        if results[i]['aligned']:
            i += 1
            continue
        j = i
        while j < n and not results[j]['aligned']:
            j += 1
        prev_end = results[i - 1]['end_ms'] if i > 0 else 0
        next_start = results[j]['start_ms'] if j < n else total_end_ms
        gap = max(next_start - prev_end, 0)
        count = j - i
        for k in range(count):
            s = prev_end + gap * k // (count + 1)
            e = prev_end + gap * (k + 1) // (count + 1)
            if e <= s:
                e = s + 1
            results[i + k]['start_ms'] = s
            results[i + k]['end_ms'] = e
        i = j

    for i in range(1, n):
        if results[i]['start_ms'] < results[i - 1]['end_ms']:
            results[i - 1]['end_ms'] = results[i]['start_ms']
    for r in results:
        if r['end_ms'] <= r['start_ms']:
            r['end_ms'] = r['start_ms'] + 1

    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_srt(results, out_path):
    with open(out_path, 'w', encoding='utf-8') as f:
        for i, r in enumerate(results, start=1):
            f.write(f"{i}\n")
            f.write(f"{format_time(r['start_ms'])} --> {format_time(r['end_ms'])}\n")
            f.write(f"{r['line'].raw_text}\n\n")


def main():
    parser = argparse.ArgumentParser(
        description="Align clean lyrics text to a Suno karaoke-style .srt, "
                    "producing a plain line-by-line .srt."
    )
    parser.add_argument('original', help="Path to the clean lyrics .txt")
    parser.add_argument('suno_srt', help="Path to the Suno-exported .srt")
    parser.add_argument('-o', '--output', default='aligned.srt',
                         help="Output .srt path (default: aligned.srt)")
    parser.add_argument('--min-coverage', type=float, default=0.4,
                         help="Below this fraction of matched letters, a "
                              "line is flagged as low-confidence even "
                              "though it wasn't fully unaligned "
                              "(default: 0.4)")
    args = parser.parse_args()

    original_lines = parse_original(args.original)
    if not original_lines:
        sys.exit("No lyric lines found in original file -- nothing to align.")

    entries = parse_srt(args.suno_srt)
    if not entries:
        sys.exit("No entries found in the Suno .srt -- is the path correct?")

    entries_by_index = {e.index: e for e in entries}
    suno_norm, char_to_entry = build_suno_timeline(entries)

    results = align(original_lines, suno_norm, char_to_entry, entries_by_index)

    total_end_ms = entries[-1].end_ms
    results = fill_gaps_and_fix_overlaps(results, total_end_ms)

    warned = False
    for r in results:
        line = r['line']
        if not r.get('aligned', True) or r.get('coverage', 1.0) < args.min_coverage:
            warned = True
            reason = ("no matching text was found in the Suno file" if not r['aligned']
                       else f"only {r['coverage']:.0%} of its letters matched")
            print(
                f"[warning] original.txt line {line.line_no}: {reason}.\n"
                f"          text: {line.raw_text}\n"
                f"          -> timing was interpolated/estimated; please "
                f"double-check this cue in {args.output}.",
                file=sys.stderr,
            )
    if not warned:
        print("All lines aligned with good confidence.", file=sys.stderr)

    write_srt(results, args.output)
    print(f"Wrote {len(results)} cues to {args.output}", file=sys.stderr)


if __name__ == '__main__':
    main()
