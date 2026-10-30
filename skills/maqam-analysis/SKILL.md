---
name: maqam-analysis
description: Estimate the tonic, scale and Arabic maqam (مقام) of a song from a transcribed ABC score, or from audio / an f0 pitch table, and say honestly how sure the answer is. Use whenever the user asks which maqam, makam, scale, mode, key, tonic (qarar / قرار) or ghammaz a song or melody uses, uploads a .abc file (or MIDI/MusicXML/audio) and asks about its maqam or key, or wants to compare the maqam of several songs. Also use for AI-generated or Arabic-influenced songs where quarter tones matter. Do not use for chord/harmony analysis or for writing new music.
---

# Maqam analysis

Turn a transcription (usually ABC, produced by an audio-to-score tool) into **evidence** about tonic,
scale shape and maqam, then report it with honestly labelled confidence (the labels are heuristics, see Known limits). You cannot hear audio; you work from
what the files contain, and the files may have lost the very thing that defines a maqam.

## The one thing to remember

ABC and MIDI transcriptions are rounded to 12 semitones. Quarter tones (the 150-cent 2nd of Bayati and Saba,
the 350-cent 3rd of Rast) **cannot appear in them**. So from a 12-TET file:

- natural-minor notes can be Nahawand *or* Bayati; Phrygian notes can be Kurd *or* Bayati; major notes can be Ajam *or* Rast;
- you may say "consistent with Nahawand", "possibly Bayati", never "this is Bayati".

Only audio (via `analyze_f0.py`) or a microtonal transcription (`_/` `^/` `_3/2` accidentals, `K:D exp _/e _/b`, MIDI pitch bend,
MusicXML fractional `<alter>`) can separate them. Check the parser warnings first: a microtonal file whose accidentals were not
recognised would silently be reported as plain 12-TET.

## Workflow

1. **Inventory the input.** `.abc`, `.mid/.midi` and `.xml/.musicxml/.mxl` -> step 2 (same script). Audio or f0 CSV -> step 4.
   MIDI is 12-TET unless it carries pitch bend; the report says which. A file with several tunes (`X:1`, `X:2`) is analysed tune by tune.
2. **Run the analysis** (all files at once is fine):
   ```bash
   python scripts/analyze_abc.py /mnt/user-data/uploads/*.abc          # full report with sections
   python scripts/analyze_abc.py song.abc --brief --no-sections        # one block per file (flags are kept)
   python scripts/analyze_abc.py song.abc --voice Ins                  # the instrument line instead
   python scripts/analyze_abc.py song.mid --voice "Track 1"            # MIDI: pick the melody track yourself
   python scripts/analyze_abc.py song.abc --json                       # for further processing
   ```
   Default voice is the one named like "vocal"; with several voices and no vocal the lines are merged and a warning says so
   (accompaniment can outvote the melody, so pass `--voice`). Chord symbols and `K:` lines are *tool-made* evidence.
   Phrase gaps are 0.6 s converted with the file's `Q:` tempo (override with `--phrase-gap` in quarter notes).
3. **Read the output in this order** (details in `references/maqamat.md`):
   - `parse check` and `parser warnings`: below 95 % bar match means the numbers are untrustworthy; report that and stop.
     "unrecognised characters ignored" means something in the file was not understood: say so.
   - **Tonic** and its confidence, then the **cues** line. If cues disagree, say which cue points where.
   - **Scale shape** and its confidence; mention `12-TET shadow of:` names as possibilities.
     If it says *no single scale identified*, do **not** name a maqam, whatever the "closest partial match" is.
   - **Flags** (printed in `--brief` as well): poor fit, quarter-tone tonic (Sikah/Huzam/Iraq family, not modelled),
     tonic/dominant split, too few pitch classes, same notes fitting other tonics. Pass them on to the user.
   - **Secondary resting note** is a candidate ghammaz, nothing more.
   - Per-section blocks: different sections can have different tonics (verse vs chorus); report differences.
4. **If audio is available**, run `python scripts/analyze_f0.py vocals.wav` (needs `pip install librosa soundfile`;
   isolate the vocal first, because accompaniment is the main failure mode). Report the measured degrees in cents; that table is the
   real evidence for quarter tones. `--csv f0.csv` accepts a pre-computed `time,f0_hz` table. Run `--selftest` once if unsure the
   tracker works here. Exit code 2 / "REFUSED" means the audio cannot support an analysis (too short, one pitch dominating, no peaks):
   tell the user and ask for a vocal stem; do not rerun with other settings until a number appears.
5. **Write the answer** (in the user's language) using the template below.

## Answer template

1. **Verdict in one sentence**, with the tonic, the scale shape, and the confidence words as the script gave them.
   Example: "Most likely G with a natural-minor shape (Nahawand-shaped); tonic confidence medium, maqam name only possible."
2. **Evidence**: 2-4 facts (pitch-class shares, where phrases end, which cues agree).
3. **What the file cannot tell**: quarter tones, relative-mode ambiguity (same notes, other tonic), tool-made chords.
4. **What would raise confidence**, ranked: vocal stem or f0 data, known ground truth, the generator prompt, a microtonal transcription.

**Comparing several songs**: give one table (song | tonic + confidence | scale shape or "no single scale" | main flag), then 2-3 lines on
what differs. Run with `--brief --no-sections`, and compare like with like (same voice, same input type: a MIDI-with-bend result and a
12-TET ABC result do not support the same claims). Do not rank songs by the numeric `share`.

Keep it short. Do not paste the whole report. Never present the numeric `share` as a probability.

## Rules that prevent wrong answers

- **Never name a maqam from 12-TET input as fact.** Use "consistent with / possibly". Maqam names with quarter-tone
  degrees (Bayati, Rast, Saba, Sikah) are only "possible" unless the input is microtonal.
- **A melody that ends phrases on the 5th or 3rd is normal in pop.** Do not override chord/key evidence with phrase-final notes alone; report the disagreement.
- **Declared `K:` is a guess by the transcription tool**, not ground truth. It counted as one vote together with the chord symbols.
- **Poor fit (< 0.90) means "no single scale"**: describe modulation / chromatic writing / possible rounded quarter tones; do not force a name.
  The same applies when the tonic itself is a quarter tone (Sikah-like): say it is outside what the tool models.
- **Tonic/dominant split flag**: say the tonic could be either note; do not pick silently.
- **Ghammaz is descriptive, not a finding**: quote it as "phrases most often rest on X", not as the maqam's ghammaz.
- **Audio of a full mix is unreliable**: the tracker can follow the pad or bass. If the tonic looks like an accompaniment note
  or confidence is low, say so and ask for a vocal stem.
- **Do not claim to have listened.** If the user asks "what does it sound like", say you analysed notes only.
- If the user supplies the true maqam/key for songs, run `scripts/evaluate.py truth.csv` and report agreement honestly,
  including misses and accuracy per confidence label; do not tune weights to a handful of songs without saying so.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/abc_parse.py` | ABC parser (voices, key/meter changes, key-field accidentals, ties, accidentals incl. `^/ _/ _3/2`, chords, tuplets, volta, `P:` parts, multi-tune files, `Q:` tempo). Bar-sum self-check. `python abc_parse.py f.abc` prints a summary. |
| `scripts/import_score.py` | MIDI (with pitch bend and RPN range) and MusicXML/MXL -> the same model. `load_scores(path)` dispatches by extension. |
| `scripts/maqam_core.py` | Templates in cents, 12-TET shadows, tonic cues, fit, confidence, flags, candidate ghammaz. `--list` prints the template table. |
| `scripts/analyze_abc.py` | CLI described above (ABC, MIDI, MusicXML). |
| `scripts/analyze_f0.py` | Audio / f0 -> cents peaks -> same scoring, with refusal guards. `--selftest` runs synthetic audio checks. |
| `scripts/evaluate.py` | Ground-truth check: `truth.csv` of your labelled files, and/or `--synthetic N` perturbed stress test; accuracy per confidence label. |
| `scripts/selftest.py` | Template recovery (10 cases), parser regressions, importer round-trips, guard checks, calibration thresholds. Run after editing any script. |

## Known limits (be upfront about them)

- **Confidence labels are heuristics.** Weights were set by hand. On perturbed synthetic music (`evaluate.py --synthetic 100`) medium
  labels were right 70/70 and low labels 25/30, and failures concentrate in melodies that end phrases on the 5th. That is a stress
  test built from the same scale templates, not accuracy on real songs: real accuracy is unknown until you run `evaluate.py` on
  labelled files. Treat tonic confidence as a consistency measure between cues.
- Melody-only input (no chords, key or second voice) can never score *high* tonic confidence.
- Not modelled: Sikah/Huzam/Iraq (tonic is a quarter tone; now **detected and flagged** for symbolic input, not identified), jins-level
  seyir, and transposed-tonic modulation inside a section. Ghammaz is estimated only as the secondary resting note.
- MIDI vocal-to-MIDI converters that write vibrato as pitch bend add small spurious offsets; check whether `microtonal` was
  triggered by real quarter tones or by bend noise (look at the pitch-class list).
- `analyze_f0.py` is validated on clean synthetic tones and on synthetic tone + pad mixes (where it now refuses or flags); real
  recordings are not validated. Absolute tuning is assumed (A4 = 440), so a quarter-tone tonic cannot be detected from audio.
- Section analysis relies on `% label` comment lines and `P:` fields; `%%` directives are ignored. A file with neither has only a whole-piece result.
- ABC dialects: grace notes, `&` voice overlays and decorations are ignored with a warning; unknown characters are listed in the warnings.
- Phrase gaps use the first `Q:` tempo only.
