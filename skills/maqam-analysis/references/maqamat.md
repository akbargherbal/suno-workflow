# Maqam reference (for maqam-analysis)

Background the agent needs to interpret `analyze_abc.py` / `analyze_f0.py` output. The scale table
below is generated from `scripts/maqam_core.py --list`, so it cannot drift from the code. If you
change `TEMPLATES` in the code, regenerate it.

## 1. Tonic and mode are different questions

A 7-note pitch-class set has 7 rotations and each is a different mode. The same notes
`D Eb F G A Bb C` are: D Phrygian = **Kurd on D**, G Aeolian = **Nahawand on G**, Bb Ionian =
**Ajam on Bb**, Eb Lydian, F Mixolydian, C Dorian. Naming the scale shape is therefore easy;
naming the **tonic** (qarar, "resting note") is what decides the answer. Never report a scale
without saying which tonic it was read from and how sure that call is.

Typical tonic cues, strongest first: where the whole piece ends; where the main phrases come to rest;
the note the melody starts phrases from; the most sustained note; the bass / chord root
(in transcribed pop, a *tool-made* chord line is a useful but correlated cue).
Pop vocals often end phrases on the 3rd or 5th, so phrase-final notes alone are weak evidence
in pop (observed in all four test songs: the main melody pointed at the 5th or the 3rd while the
tool's chords and key agreed on another note). That is why the report counts independent cues.

## 2. Scale templates (cents above the tonic) and their 12-TET shadows

| id | name | western | degrees (cents) | 12-TET shadows (semitones) |
|---|---|---|---|---|
| rast | Rast | - | [0, 200, 350, 500, 700, 900, 1050] | {0,2,3,5,7,9,10} ; {0,2,3,5,7,9,11} ; {0,2,4,5,7,9,10} ; {0,2,4,5,7,9,11} |
| ajam | Ajam | major / Ionian | [0, 200, 400, 500, 700, 900, 1100] | {0,2,4,5,7,9,11} |
| bayati | Bayati | - | [0, 150, 300, 500, 700, 800, 1000] | {0,1,3,5,7,8,10} ; {0,2,3,5,7,8,10} |
| nahawand | Nahawand | natural minor / Aeolian | [0, 200, 300, 500, 700, 800, 1000] | {0,2,3,5,7,8,10} |
| nahawand_h | Nahawand (raised 7th) | harmonic minor | [0, 200, 300, 500, 700, 800, 1100] | {0,2,3,5,7,8,11} |
| kurd | Kurd | Phrygian | [0, 100, 300, 500, 700, 800, 1000] | {0,1,3,5,7,8,10} |
| hijaz | Hijaz | - | [0, 100, 400, 500, 700, 800, 1000] | {0,1,4,5,7,8,10} |
| hijaz_r | Hijaz (Rast upper) | - | [0, 100, 400, 500, 700, 900, 1000] | {0,1,4,5,7,9,10} |
| hijaz_kar | Hijaz Kar | - | [0, 100, 400, 500, 700, 800, 1100] | {0,1,4,5,7,8,11} |
| saba | Saba | - | [0, 150, 300, 400, 700, 800, 1000] | {0,1,3,4,7,8,10} ; {0,2,3,4,7,8,10} |
| nikriz | Nikriz | - | [0, 200, 300, 600, 700, 900, 1000] | {0,2,3,6,7,9,10} |
| nawa_athar | Nawa Athar | - | [0, 200, 300, 600, 700, 800, 1100] | {0,2,3,6,7,8,11} |
| dorian | (no standard maqam) | Dorian | [0, 200, 300, 500, 700, 900, 1000] | {0,2,3,5,7,9,10} |
| mixolydian | (no standard maqam) | Mixolydian | [0, 200, 400, 500, 700, 900, 1000] | {0,2,4,5,7,9,10} |
| lydian | (no standard maqam) | Lydian | [0, 200, 400, 600, 700, 900, 1100] | {0,2,4,6,7,9,11} |


Reading the table: a maqam with a quarter-tone degree (150, 350, 1050 cents) has several 12-TET
shadows, one per way of rounding it. Whatever is in a 12-TET transcription is one of those shadows,
so these pairs are **indistinguishable in ABC/MIDI**:

| Same 12-TET notes | Possible maqamat | What would settle it |
|---|---|---|
| natural minor `0 2 3 5 7 8 10` | Nahawand (or Bayati with its 2nd rounded up) | measured 2nd degree: 200 c vs ~150 c |
| Phrygian `0 1 3 5 7 8 10` | Kurd (or Bayati with its 2nd rounded down) | 2nd degree: 100 c vs ~150 c |
| major `0 2 4 5 7 9 11` | Ajam (or Rast with both neutral degrees rounded up) | 3rd and 7th: 400/1100 c vs ~350/1050 c |
| Dorian `0 2 3 5 7 9 10` | Rast rounded down, or Western Dorian | 3rd degree ~350 c |
| `0 1 3 4 7 8 10` | Saba (2nd rounded down) | 2nd degree ~150 c |

Maqamat deliberately **not modelled**: Sikah, Huzam, Iraq, Awj-Ara and other maqamat whose tonic is
itself a quarter-tone pitch, plus most modulation-heavy ones (Suznak, Nawa Athar variants, ...).
A real maqam is also a path (*seyir*): where the melody starts, climbs and settles, and which jins
sits on the 4th/5th. The scripts do not model that, so a good match is a hint, not a verdict.

## 3. What the report fields mean

| Field | Meaning |
|---|---|
| parse check | share of bars whose durations sum to the meter. Below 95 % do not trust any number. |
| Pitch classes | share of total sung duration per pitch class (not note counts). |
| tonic share | normalised evidence score, **not a probability**. Compare candidates only with each other. |
| melody-only | the part of the score that comes from the melody itself (duration, phrase-final, phrase-initial, last note), after the 5th-support discount. |
| chord* / declared* | produced by the transcription tool (chord symbols, `K:` line), not by the melody. One vote. |
| other voice | the same melody-only call made on the other voice(s) (e.g. instrument line). |
| tonic confidence | high: >= 75 % of cues agree and margin >= 0.08; medium: >= half agree; low otherwise. |
| fit | share of sung duration that lies on the template, minus small penalties for missing and extra degrees. |
| shape confidence | 12-TET input is capped at *medium* because it cannot show quarter tones; `high` needs microtonal input (audio or `_/` `^/` accidentals) and fit >= 0.95. |
| 12-TET shadow of: X | the notes are consistent with X only if one of its quarter-tone degrees was rounded. Say "possibly X", never "X". |
| Notes outside this scale | pitch classes (>= 1.5 %) not in the best-fit scale: modulation, alteration, or a neutral degree rounded to the wrong side. |
| Scale degrees almost never sung | degrees < 1 % : avoided on purpose, or microtonal and lost in transcription. |
| No single 12-TET scale explains... | best fit < 0.90. Do not name one maqam. Look at sections, or ask for audio. |

## 4. The audio route (analyze_f0.py)

1. Prefer an isolated vocal stem. Guitar/strings break the pitch tracker.
2. `pyin` tracks f0; steady stretches become notes; a circular histogram in cents (10-cent bins,
   15-cent smoothing) gives pitch peaks; peaks are matched to the cents templates within 35 cents.
3. Check the "measured degrees" table: a 2nd degree at 120-180 c is a quarter-tone degree; at ~100 or ~200 it is not.
4. Tuning: assumes A4 = 440 Hz. If every peak sits 20-40 cents off the grid, pass `--tuning-cents`.
5. Sung vibrato/ornaments widen peaks (about +-15 c); real singers also drift, so treat +-25 c as "on" the degree.
6. Not validated on real recordings yet (only on synthetic tones). Say so when reporting.

## 5. What to ask the user for, in order of value

1. Isolated vocal audio (or an f0 CSV) for the song, because it is the only thing that can show quarter tones.
2. Any known ground truth (tonic / maqam / key) to check the call against.
3. The prompt given to the generator, if the song was AI-generated; useful as a weak prior, since generators ignore or blend such instructions.
4. A transcription with microtonal accidentals (`_/` `^/`) or MIDI with pitch bend, if the transcriber can produce one.

## 6. Observed behaviour on real transcriptions (4 commercial songs)

- All four parse cleanly (100 % of bars match the meter), so the parser handles this transcriber's dialect
  (two voices `Vocal` / `Ins`, `L:1/16` or `1/32`, mid-file `M:`/`K:`, `% intro|verse|chorus` comments, ties, `^ _ =`).
- No quarter-tone accidentals occur anywhere: the transcriber outputs 12-TET only, so maqam names can only ever be "possible".
- The tool's `K:` is not always trustworthy: a song declared `Dm` had a vocal centred on F (relative major reading).
- Sections can differ: one song moves between two key signatures; its verse fits no single scale (fit 0.77),
  which is the signature of modulation or of quarter tones rounded both ways.
