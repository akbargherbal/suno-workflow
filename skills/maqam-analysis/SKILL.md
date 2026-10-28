---
name: maqam-analysis
description: Estimate the tonic, scale and Arabic maqam (مقام) of a song from a transcribed ABC score, or from audio / an f0 pitch table, and say honestly how sure the answer is. Use whenever the user asks which maqam, makam, scale, mode, key, tonic (qarar / قرار) or ghammaz a song or melody uses, uploads a .abc file (or MIDI/MusicXML/audio) and asks about its maqam or key, or wants to compare the maqam of several songs. Also use for AI-generated or Arabic-influenced songs where quarter tones matter. Do not use for chord/harmony analysis or for writing new music.
---

# Maqam analysis

Turn a transcription (usually ABC, produced by an audio-to-score tool) into **evidence** about tonic,
scale shape and maqam, then report it with calibrated confidence. You cannot hear audio; you work from
what the files contain, and the files may have lost the very thing that defines a maqam.

## The one thing to remember

ABC and MIDI transcriptions are rounded to 12 semitones. Quarter tones (the 150-cent 2nd of Bayati and Saba,
the 350-cent 3rd of Rast) **cannot appear in them**. So from a 12-TET file:

- natural-minor notes can be Nahawand *or* Bayati; Phrygian notes can be Kurd *or* Bayati; major notes can be Ajam *or* Rast;
- you may say "consistent with Nahawand", "possibly Bayati", never "this is Bayati".

Only audio (via `analyze_f0.py`) or a microtonal transcription (`_/` `^/` accidentals, MIDI pitch bend) can separate them.

## Workflow

1. **Inventory the input.** `.abc` -> step 2. Audio or f0 CSV -> step 4. MIDI/MusicXML -> ask for the ABC or audio, or
   convert with music21 if it is installed; MIDI is 12-TET unless it carries pitch bend, and say so.
2. **Run the ABC analysis** (all files at once is fine):
   ```bash
   python scripts/analyze_abc.py /mnt/user-data/uploads/*.abc          # full report with sections
   python scripts/analyze_abc.py song.abc --brief --no-sections        # one block per file
   python scripts/analyze_abc.py song.abc --voice Ins                  # the instrument line instead
   python scripts/analyze_abc.py song.abc --json                       # for further processing
   ```
   Default voice is the one named like "vocal". Chord symbols and `K:` lines are treated as *tool-made* evidence.
3. **Read the output in this order** (details in `references/maqamat.md`):
   - `parse check`: below 95 % means the numbers are untrustworthy; report that and stop.
   - **Tonic** and its confidence, then the **cues** line. If cues disagree, say which cue points where.
   - **Scale shape** and its confidence; mention `12-TET shadow of:` names as possibilities.
   - Flags: notes outside the scale, almost-never-sung degrees, "No single 12-TET scale explains...".
   - Per-section blocks: different sections can have different tonics (verse vs chorus); report differences.
4. **If audio is available**, run `python scripts/analyze_f0.py vocals.wav` (needs `pip install librosa soundfile`;
   isolate the vocal first if you can). Report the measured degrees in cents; that table is the real evidence for quarter tones.
   `--csv f0.csv` accepts a pre-computed `time,f0_hz` table. Run `--selftest` once if unsure the tracker works here.
5. **Write the answer** (in the user's language) using the template below.

## Answer template

1. **Verdict in one sentence**, with the tonic, the scale shape, and the confidence words as the script gave them.
   Example: "Most likely G with a natural-minor shape (Nahawand-shaped); tonic confidence medium, maqam name only possible."
2. **Evidence**: 2-4 facts (pitch-class shares, where phrases end, which cues agree).
3. **What the file cannot tell**: quarter tones, relative-mode ambiguity (same notes, other tonic), tool-made chords.
4. **What would raise confidence**, ranked: vocal stem or f0 data, known ground truth, the generator prompt, a microtonal transcription.

Keep it short. Do not paste the whole report. Never present the numeric `share` as a probability.

## Rules that prevent wrong answers

- **Never name a maqam from 12-TET input as fact.** Use "consistent with / possibly". Maqam names with quarter-tone
  degrees (Bayati, Rast, Saba, Sikah) are only "possible" unless the input is microtonal.
- **A melody that ends phrases on the 5th or 3rd is normal in pop.** Do not override chord/key evidence with phrase-final notes alone; report the disagreement.
- **Declared `K:` is a guess by the transcription tool**, not ground truth. It counted as one vote together with the chord symbols.
- **Poor fit (< 0.90) means "no single scale"**: describe modulation / chromatic writing / possible rounded quarter tones; do not force a name.
- **Do not claim to have listened.** If the user asks "what does it sound like", say you analysed notes only.
- If the user supplies the true maqam/key for songs, compare your output against it and report agreement honestly,
  including misses; do not tune weights to a handful of songs without saying so.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/abc_parse.py` | Parser (voices, key/meter changes, ties, accidentals incl. `^/ _/`, chords, tuplets). Bar-sum self-check. `python abc_parse.py f.abc` prints a summary. |
| `scripts/maqam_core.py` | Templates in cents, 12-TET shadows, tonic evidence, fit, confidence. `--list` prints the template table. |
| `scripts/analyze_abc.py` | CLI described above. |
| `scripts/analyze_f0.py` | Audio / f0 -> cents peaks -> same scoring. `--selftest` runs synthetic audio checks. |
| `scripts/selftest.py` | 10 synthetic ABC cases with known maqamat. Run after editing any script. |

## Known limits (be upfront about them)

- Scoring weights are heuristics checked on synthetic data and on four real songs without ground truth. Treat tonic confidence as a
  consistency measure between cues, not as accuracy.
- Not modelled: Sikah/Huzam/Iraq (tonic is a quarter tone), jins-level seyir, and transposed-tonic modulation inside a section.
- `analyze_f0.py` is validated on clean synthetic tones only; real recordings with accompaniment will be noisier.
- ABC dialects: grace notes, `&` voice overlays and decorations are ignored with a warning.
