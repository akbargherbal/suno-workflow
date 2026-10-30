# Writing ABC that plays correctly in abcjs

The user pastes your file into https://www.abcjs.net/abcjs-editor and presses play. Keep the output close to the format his transcriber produces so it behaves the same.

## Contents
1. Header skeleton
2. Bar arithmetic
3. Voices
4. Pitch, accidentals, ties
5. Common pitfalls
6. Minimal example
7. Spelling the maqam with `scale`
8. Audio-seed friendliness

## 1. Header skeleton (copy from the source score, do not invent one)

```
X:1
T:
M:2/4
L:1/16
Q:1/4=89
V: Vocal clef=treble name="Vocal Melody" snm="Vocal"
V: Ins clef=treble name="Ins Melody" snm="Inst."
K:Gm
% intro
V: Vocal
...
V: Ins
...
```

- `M:` meter (bar size), `L:1/16` unit note length, `Q:1/4=89` quarter-notes per minute, `K:` key. Keep `L:1/16`.
- Every voice block is repeated per section, so bars from different voices line up: write the Vocal bars for a section, then the Ins bars for the same section.
- Chord symbols (optional) go in quotes before a note or rest: `"Dm"A4`.

## 2. Bar arithmetic (the most common failure)

With `L:1/16`: a bare note letter lasts 1 unit; a digit multiplies (`A4` = 4 units).
- `M:2/4` bar = **8 units**; `M:4/4` bar = **16 units**; `M:3/4` = 12 units; `M:6/8` = 12 units.
- `z4` = rest of 4 units. `Z` = a full-bar rest; `Z4` = four bars of rest.
- Every bar of every voice must add up to the same total, or abcjs misaligns voices. Run `python scripts/abc_tool.py check file.abc` after writing; fix every `FIX` line.
- A pickup (partial first bar) is fine only at the very start.
- Mid-tune meter change: put `M:1/4` on its own line before the bar and `M:2/4` after it, in *every* voice.

## 3. Voices

- Voice names are `Vocal` and `Ins`; both must be present and end together (use `Z` rests to pad).
- Put the signature fill in `Ins` inside the rests the `Vocal` leaves; pad the other voice with equal rests.
- Do not add more voices unless the user asks.

## 4. Pitch, accidentals, ties

- Uppercase `C D E F G A B` = the octave from middle C; lowercase `c d e f g a b` = one octave up; `c'` two up; `C,` one octave below.
- The `K:` key signature already sharpens/flattens notes (`K:Gm` = Bb and Eb; `K:Dm` = Bb; `K:D#m` = six sharps). Write plain letters for those notes. To override, use `^` sharp, `_` flat, `=` natural; the accidental holds for the rest of that bar.
- Tie with `-` right after the note: `d4-|d4` (same pitch continues across the barline).
- Leave grace notes, tuplets and decorations out unless needed; they make bar sums harder to check.
- Quarter-tone accidentals exist in ABC 2.1 but the preview may play them as ordinary notes; if you use them, tell the user.

## 5. Common pitfalls

- Bars not summing to the meter (the checker catches this).
- Forgetting that `K:` changes what a plain letter means.
- Mixing `z` (one bar part) and `Z` (whole bars) inside a bar.
- Lyrics: do not add `w:` lines for Arabic diacritized text; the renderer handles it badly. Use `% line N` comments instead.
- Very long files: keep sketches to the sections asked for. A full song is about 100-130 lines.

## 6. Minimal example (2/4, a fill answering a sung phrase)

```
X:1
M:2/4
L:1/16
Q:1/4=80
V: Vocal clef=treble name="Vocal Melody" snm="Vocal"
V: Ins clef=treble name="Ins Melody" snm="Inst."
K:Dm
% verse 1, line 1
V: Vocal
A2A2B2A2|G2F2F2E2|D4z4|
V: Ins
Z|Z|z8|
% fill after line 1
V: Vocal
Z|Z|
V: Ins
z4D2F2|A2G2F2E2|
```

Check: every bar is 8 units in both voices (the Vocal rests `Z|Z|` cover the two fill bars). (Lines are illustrative, not a recommendation.)

## 7. Spelling the maqam with `scale`

Because `K:` is a transcriber guess (e.g. `K:D#m` for a song whose home note is C), plain letters often do not
mean what you expect. Never spell by intuition; run

```
python scripts/abc_tool.py scale --maqam Hijaz --tonic D --key-from score.abc
```

It lists each degree with the exact ABC token for that file's `K:` (plain letter = already correct; `^` `_` `=`
= explicit accidental, which lasts until the next barline), plus the octave above and below. Keep the source's
`K:` line so the header stays identical across the variants. Afterwards `abc_tool.py modal` verifies the result
and prints the source line number of every note outside the maqam.

## 8. Audio-seed friendliness

The user will use the variants as seeds for generating new tracks, so what he hears from the abcjs/MIDI
rendering is what matters. Keep `Vocal` a clean, singable single line (no chords or stacked notes in it).
Keep `Q:` explicit. Avoid grace notes, tuplets and microtonal accidentals. Let `Ins` fills sit in the rests of
`Vocal`, not on top of it. Keep pitches inside a comfortable range (about 1.5 octaves for `Vocal`).
