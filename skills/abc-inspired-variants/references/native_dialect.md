# The native ABC dialect (what the scores really look like)

The `score.abc` files come out of the YuE2 / SheetSage2 pipeline, not from a human editor. They use a small, strict
dialect of ABC. If a variant stays inside it, the file can go back into the same pipeline as a seed (for example
as a chord-free melody for a cover) and still plays in abcjs. `abc_tool.py lint` checks this; `verify` runs it for you.
Source of the rules: the public YuE2 skill notes (`skills/yue2-music/references/abc-editing.md` in the YuE repo).
That helper is a bounded implementation of the dialect, not the whole ABC standard, so a rejection means
"outside the dialect", not "invalid ABC".

## Contents
1. Layout of a file
2. Durations and bar totals
3. Accidentals (the one rule that differs from abcjs)
4. Chord symbols
5. What the dialect does not contain
6. Tools in this skill
7. How this was learned (and what it is not for)

## 1. Layout of a file

```
X:1
T:
M:4/4
L:1/16
Q:1/4=104
V: Vocal clef=treble name="Vocal Melody" snm="Vocal"
V: Ins clef=treble name="Ins Melody" snm="Inst."
K:Eb
% verse
V: Vocal
"Cm7"z4e2e2e2e4f2-|"Bb7"f2d4c4B4A2-|
V: Ins
Z2|
```

- Two monophonic voices only: `Vocal` (the sung line) and `Ins` (an instrumental theme or fill, not a chord staff).
- Music comes in short blocks of one to four bars: a `V: Vocal` block, then a `V: Ins` block covering the same bars.
- Section comments (`% intro`, `% verse`, `% chorus`, `% bridge`, `% interlude`, `% outro`) mark the structure. Keep them;
  `structure` and the layout check read them.
- A meter change or key change starts a new block, and **both voices** get the same `M:` / `K:` line.
- `L:` is whatever the exporter needed for its rhythm grid (1/16 in the scores seen so far, 1/32 elsewhere). Keep the source's value.
- `K:` is a plain major or minor key. It is the transcriber's guess for the home note, not the maqam; use `scale` for the real spelling.

## 2. Durations and bar totals

With `L:1/16` one bare letter is 1 unit and a digit multiplies it. Allowed multipliers: 1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48.
A 4/4 bar is 16 units, 3/4 is 12, 2/4 is 8, 1/4 is 4. Ten units is written `C8-C2`.

- `Z`, `Z2`, `Z3`... are whole resting bars in the current meter (counted in bars, not units). `z4` is a 4-unit rest.
- Do not hide a harmonic or key change inside a compressed `Z`; write the rests out so the change lands at its true position.
- A tie joins two equal pitches, never joins a rest, and the file may not end on an open tie. A tied continuation
  across a barline keeps the earlier pitch; repeating the accidental on it is clearer.
- Count sounding notes after merging ties. `C8-C8` and `C8C8` look alike but the second one re-attacks.

## 3. Accidentals

Pitch is relative to `K:`. An accidental lasts to the end of the bar and is dropped at the barline or a key change.

**Dialect rule: an accidental applies to that letter in every octave** (after `^f`, both `f` and `F` are sharp until the barline).
Standard ABC and abcjs apply it to one octave only. The tool follows the dialect rule when it measures (set
`ABC_ACC=abc` to read the standard way), and `lint`/`verify` list every note where the two readings differ. When the
list is not empty, write the accidental on each affected note explicitly so both readers agree.

## 4. Chord symbols

Harmony lives in quoted symbols inside the `Vocal` voice, even where it is resting: `"Cm7"z16`. Roots and optional slash
basses are note names (`F#m7/C#`). Vocabulary: major (no suffix), `m`, `dim`, `aug`, `7`, `maj7`, `m7`, `dim7`, `m7b5`, `sus4`,
`sus2`, `6`, `m6`, `7sus4`, `m(maj7)`. Nothing else (`C13`, `Cmaj9`, `A7alt`, free text) is native.
A chord change inside a held note is written as a tie: `"C"E16-"Am7"E16`.

`strip-chords` makes a chord-free copy and proves every note, onset, duration and the tempo are unchanged. That copy is
the melody-only seed for a generator that should invent its own harmony.

## 5. What the dialect does not contain

Tuplets, grace notes, stacked notes, repeat signs and alternate endings, slurs, broken rhythm (`>` `<`), decorations,
lyric lines (`w:`), `%%` directives, extra voices, modes in `K:`. Rebuild such material as plain notes and rests.

## 6. Tools

| Need | Command |
|---|---|
| is this file inside the dialect | `abc_tool.py lint file.abc` |
| bar totals | `abc_tool.py check file.abc` |
| chord-free melody seed | `abc_tool.py strip-chords src.abc dst.abc` |
| sections, bars, register, ending degree, chord loops | `abc_tool.py structure file.abc` |
| everything about a source in one call | `abc_tool.py brief score.abc --label Hijaz` |
| whole validation of a song folder | `abc_tool.py verify <song-folder> --maqam Hijaz --tonic D` |

## 7. How this was learned, and what it is not for

The facts above were checked against a real exported score (8 sections, two voices, 113 chord symbols, 4/4 with a few
1/4 and 3/4 bars, 104 bpm). The same session showed that a score's fingerprint (key, tempo, chord loop per section,
structure, signature gesture such as a long held high note) is what lets a person or a model recognise the source song.
This skill does not use that to identify songs. It uses the same fingerprint the other way round: to know exactly
what a variant is allowed to keep and what it must change.
