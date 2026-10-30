---
name: abc-inspired-variants
description: Takes ABC-notation scores (auto-transcribed from AI-generated songs, e.g. REF_ABC_SCORE_MAQAM/<Maqam>_Shortlist/<song>/score.abc) and, for each score, writes three new maqam-correct ABC variants VAR_A_score.abc, VAR_B_score.abc and VAR_C_score.abc plus a short Arabic report,; no questions asked during the run. The reference is a starting point, never a model to copy. Verifies the folder's maqam label (80-90% reliable) and validates every variant against the maqam's rules. For the "arabmaqamrock" project (Arabic maqam symphonic rock, Suno/YuE2 LoRA); the user has no music education and reads Arabic. Use whenever the user shares .abc files, a folder of scores, or pasted ABC text, mentions "score", "سكور", "abcjs", "YuE2", "native ABC", "chords", "كوردات", "نكهة", "استلهام", "variants", "VAR_A", "Shortlist", "مقام", "حجاز", "كرد", "نهاوند", "عجم", "قمر بغداد" or arabmaqamrock, or asks for melodies, hooks, fills or alternatives inspired by existing songs, or gives feedback on earlier variants, even without saying "skill" or "ABC". Not for identifying which song a score comes from.
---

# ABC Inspired Variants (autonomous mode)

For each reference score: **measure -> verify the maqam -> design three different recipes -> write -> validate -> report**.
The user is not in the loop while you work. He will take the variants away, use them as the seed for
generating new tracks, listen, and possibly come back with feedback (see "Feedback sessions").

## Operating rules

1. **Never stop to ask a question.** If something is unclear, choose the most reasonable default, apply it,
   and write the assumption in the song's report (section 5). Finish the whole batch.
2. **Never modify `score.abc`.** Do not overwrite an existing `VAR_*` file unless the user said "regenerate".
   If all five output files already exist for a song, skip it (resume safely after interruptions).
3. **You cannot hear.** Never say a variant "sounds better". Say what changed and what to listen for.
4. **The reference is a starting point, not a model.** Variants must be genuinely new melodies that keep
   only what the recipe says to keep. See "Distance from the source".
5. **Maqam correctness is a hard requirement**, checked by the tool, not by your impression.
6. The user has no music education. Reports are in simple Arabic, English music terms in parentheses with a
   one-sentence everyday explanation (cooking analogies work: the score is the dish, you adjust the seasoning).

7. **Stay inside the native ABC dialect** of the source (`references/native_dialect.md`): two voices `Vocal` and `Ins`,
   the source's `L:` and header, section comments, no tuplets, grace notes, slurs, repeats or `w:` lines. `lint` must be clean.
8. **Do not try to name the song a score comes from.** The fingerprint tools exist to decide what a variant keeps and changes.

Read `references/project_context.md` once at the start of a run (project, what ABC can and cannot do,
what is known) and `references/native_dialect.md` (what the files really contain). If `FEEDBACK_LOG.md` exists in the data root (the folder that contains the `*_Shortlist`
folders), read it too and apply what it says.

## Input and output layout

```
<root>/                      e.g. REF_ABC_SCORE_MAQAM
  Hijaz_Shortlist/<song-folder>/score.abc      <- input; the folder name gives the label
  Hijaz_Shortlist/<song-folder>/VAR_A_score.abc  <- you write these five files
                               /VAR_B_score.abc
                               /VAR_C_score.abc
                               /CONTROL_score.abc   (the source melody, chord-free, notes verified identical)
                               /VAR_REPORT.md       (template: references/report_template.md)
  VARIANTS_INDEX.md            <- you write one per run (batch summary)
  FEEDBACK_LOG.md              <- created/updated only in feedback sessions
```

Labels: `Ajam_Shortlist`, `Hijaz_Shortlist`, `Kurd_Shortlist`, `Nahawand_Shortlist`. They came from an AI
labeller that is about 80-90% right, so **the label is a prior, not a fact** (step 2).
The tool is `scripts/abc_tool.py` (run with `python` or `python3`, whichever exists; paths may contain
Windows backslashes, quote them). `python scripts/abc_tool.py progress <root>` lists songs still lacking outputs.
If given a single score or pasted ABC with no folder, treat it as one song with no label (`maqam` runs without `--label`);
write outputs next to it; if the score only exists as pasted text, create `abc-inspired-variants-out/` in the current working directory and write there.

## Per-song pipeline

### 1. Measure
```
python scripts/abc_tool.py brief <song>/score.abc --label <Label>     # one-shot fingerprint
```
`brief` prints, in one call: header (tempo, meter(s), `L:`, `K:` guess, length, bars), the maqam decision (same as step 2),
a section table (bars, seconds, sung notes, register, ending degree, hook position), the chord loop of each section if the
source has chords, the longest repeating chord loops, the instrumental hook, and the `traits` comparison with sibling songs.
For more detail run `features` and `traits` separately. Inspect the file itself too: voice names, section comments, bar count.
Transcribers re-guess tempo, meter and key for every file, so compare per-second and per-phrase numbers only.
`references/flavor_traits.md` explains the numbers. Write a **flavor card**: 2-3 traits where `traits`
shows |z| >= 1 against its siblings. You have no words from the user about why he likes the song, so
say these come from numbers only.

What to take from the fingerprint (it is also what makes a song recognisable, which is why a variant must change it):
the chord loop per section, the section order and lengths, the register and the note a section ends on, and one
**signature gesture** (a long held high note, a recitation on one repeated pitch, a fill that returns). Name the gesture
in the flavor card and decide per recipe whether it is kept, moved, or replaced.

### 2. Decide the maqam (due diligence)
```
python scripts/abc_tool.py maqam <song>/score.abc --label <Label>
```
The tool scores how well the melody fits each maqam on each possible home note (the file's `K:` is only
a transcriber guess, so do not trust it) and applies the label as a prior. Statuses:

| Status | Meaning | What you do |
|---|---|---|
| CONFIRMED | label fits as well as anything | use the label, with the tool's tonic |
| KEEP_LABEL | something fits a bit better but not convincingly | use the label; say so in the report |
| OVERRIDE | the melody clearly fits another maqam much better | **use the tool's TARGET maqam**; state it prominently |
| LOW_FIT | nothing fits well (noise or modulation) | use the label; stay on core notes only |
| NO_LABEL | no folder label | use the tool's TARGET |

Also read `TONIC UNSURE` and `CLOSE RIVALS` lines (twin modes share notes; see `maqam_rules.md` section 7):
choose by where phrases rest and where the song ends; if still tied, keep the label. Record the final
choice **(maqam, tonic)** and one sentence of evidence. Do not silently change a maqam.

Read `references/maqam_rules.md` for the chosen maqam before composing.

### 3. Design three recipes (before writing notes)
Common to all variants: same maqam and tonic, same `M:` and `L:1/16`, voices `Vocal` and `Ins` (use the
source's voice names), same section order and about the same length (+-10% bars), every section ends on a
maqam-appropriate resting note, final Vocal note = tonic. **Sung notes per section stay within about 15% of the
source**: the words were sung over those notes, so the count is the room the lyrics have (assumed, unless the user says the
lyrics will change; `verify` flags it). Change density with note lengths and rests, not by dropping syllables.
**No chord symbols** in the variants by default: the source's chords are Western harmony for its own melody and would
contradict a maqam melody. Note this assumption in the report; add chords only if asked, from the native vocabulary.

| Variant | Idea | Keep from the source | Change |
|---|---|---|---|
| **A Polish** | the source, recomposed as a proper maqam sayr | phrase boundaries and general rhythm skeleton, `Q:` | all pitches; clearer tonic/dominant landings; characteristic move in the first phrases; one signature fill (4-8 notes) in `Ins`, reused with small variation |
| **B Reshape** | a different shape for the same material | section order, `Q:` within +-8% | shorter singable chunks (8-12 notes) cut by beat-long rests, same syllable count; different rhythm density (>= 25% change in notes/sec or median note length); fills irregularly spaced; contour arch, chorus a fourth or fifth higher than verse |
| **C Reimagine** | a wildcard inside the maqam | section order only | a trait neither A nor B uses: e.g. start on the 3rd or 5th instead of the tonic, a sayr that visits the upper jins early, a refrain (opening phrase reused for the chorus, lyrics unchanged), a different register, `Q:` up to +-12%, or a sparser/denser `Ins` role |

Each variant must differ from the other two in **at least three measurable ways** (phrase length,
fill count or spacing, notes/sec, range, Ins activity, tempo, opening degree, contour). Variants that differ by a few
notes defeat the purpose: he wants to hear three different ideas. Borrow a *behavior* (e.g. "answers every
second line with a short rising figure"), not a melody; transform what you borrow.

### 4. Write the ABC
Follow `references/abc_writing.md`. Start every variant from the source's header, keep `K:` as in the source (the
`scale` command prints the correct ABC spelling for that `K:`):
```
python scripts/abc_tool.py scale --maqam <Target> --tonic <Tonic> --key-from <song>/score.abc
```
Top of each file: comment lines `% VARIANT A of <folder> | <Maqam> on <Tonic> | recipe: Polish`. Keep or add
`% intro`, `% verse 1`, `% line N` section comments so notes map to words. Do not add `w:` lines. Do not rely
on quarter-tone playback; the variants must be recognisable in plain 12-tone playback.
Accidentals: the dialect applies one to that letter in every octave until the barline, abcjs only to one octave.
Write the accidental on every affected note so both readings agree (`lint` lists the notes where they differ).

Also write the **control**: the source melody unchanged, so that a listening test has a baseline
(a variant can only be said to help if it beats the control seeded the same way):
```
python scripts/abc_tool.py strip-chords <song>/score.abc <song>/CONTROL_score.abc
```
The command refuses to write if any note, onset, duration or the tempo would change. (If the source has no chords
the control is a plain copy.) Never edit the control by hand.

### 5. Validate and repair (loop up to 4 rounds per variant)
One call does all of it (bars, dialect, maqam, distance from the source, layout parity, differences between variants, cadences):
```
python scripts/abc_tool.py verify <song-folder> --maqam <Target> --tonic <Tonic>
```
Exit code 1 means `FIX` lines remain. The individual commands, for detail:
```
python scripts/abc_tool.py check VAR_A_score.abc VAR_B_score.abc VAR_C_score.abc
python scripts/abc_tool.py modal VAR_A_score.abc VAR_B_score.abc VAR_C_score.abc --maqam <Target> --tonic <Tonic>
python scripts/abc_tool.py compare VAR_A_score.abc score.abc --others VAR_B_score.abc VAR_C_score.abc
python scripts/abc_tool.py features VAR_A_score.abc VAR_B_score.abc VAR_C_score.abc --tonic <Tonic>
```
- `lint` (dialect) and the layout check (section order, bars and sung notes per section against the source) are part of `verify`.
- Fix every `FIX` line in `check` and `modal` (`modal` prints the source line numbers of offending notes).
  `WARN` lines: fix if cheap, otherwise mention in the report.
- **Distance from the source.** `compare` against `score.abc` must show a longest identical run of at most 7
  intervals, and overall similarity at most 0.60 for A and at most 0.50 for B and C (starting values; if a
  limit proves silly in practice, say so in the report). Also compare each variant with the other two.
- Run `features` on the variants and confirm they differ the way the recipes promised; if two look alike, rewrite one.
- If a `FIX` is still unresolved after 4 rounds, keep the file but put `% UNRESOLVED: <what>` as its second line and list it in
  the report and index. A file that fails `check` (broken bars) must never be delivered; simplify until it passes.

### 6. Write `VAR_REPORT.md`
Use `references/report_template.md`. Short, in simple Arabic. Include the maqam decision and its evidence,
flavor card, the recipe table with where to listen (bar or section) and one thing to notice, the quality
checks (bars, dialect, maqam, distance, layout), the assumptions (chord-free, fixed lyrics), and what hypothesis each variant tests, so he can attribute results.

### 7. After the last song: write `VARIANTS_INDEX.md` at the root
One table row per song: folder, label, final maqam and tonic, status, anything unresolved. List first all
OVERRIDE, LOW_FIT, TONIC UNSURE and UNRESOLVED cases. End with `python scripts/abc_tool.py progress <root>`
output. Then give a short chat summary (counts, the exceptional songs, nothing else) and stop. Do not ask questions.

## Feedback sessions (later, when the user returns)

He will name songs/variants and say what he heard, even in a few words. Then:
1. Append to `FEEDBACK_LOG.md` in the root: date, song, variant, recipe, his words, your interpretation
   (labelled hypothesis), decision. Keep it factual and short.
2. **Iterate one change at a time** on the variant he liked: write `VAR_B_score_r2.abc` (never overwrite earlier
   files), mark edits with `% CHANGED`, re-run the validation loop, add a line to the report.
3. Look for patterns across songs (which recipe worked per maqam, what he rejected) and write
   them in the log under "Patterns so far", marked low confidence until repeated. Use them as defaults in the next batch.
4. His explicit corrections about a maqam override `references/maqam_rules.md`; log them and follow them.
5. **After three rounds without a "that's it" moment** on a song, say so and recommend generating several
   seeds and choosing by ear instead of more ABC edits.
6. If he says a variant feels right, give a generation brief: lyrics-tag edits (where a short guitar fill is
   requested, where the opening couplet repeats, section dynamics), style-string edits, a best-of-N seed plan, and a
   rating note including the "shower test" (a day later, which version can he hum?).

## Round trip: scores that come back from generated tracks

When he generates a track from a variant and the pipeline returns that track's own `score.abc`:
1. Treat it as a new source (`brief` it; it may carry chords, and `strip-chords` makes a melody-only copy of it).
2. Run `compare` of the returned score against the variant that seeded it. The numbers say how much of the seed the
   generator kept (identical-run length, melodic and rhythm similarity). This is a measurement of one take, not proof
   that the seed steers the generator; log it as a hypothesis in `FEEDBACK_LOG.md` next to his listening verdict.
3. If the returned score is a good seed itself, it enters the next batch like any other `score.abc`.

## Honesty and scope

- Say "experiment" or "hypothesis", never "this will reach 9/10". If an idea is unlikely to survive into the audio, say so.
- The transcription does not capture guitars, strings, mix or vocal ornaments (melisma), and its pitch accuracy is approximate.
- The detection thresholds in `abc_tool.py` are starting values checked only on synthetic melodies. The
  user can run `python scripts/abc_tool.py survey <root>` on the whole corpus to see how labels and detection agree.
- This is melody and structure sketching, not music-theory teaching unless he asks.
