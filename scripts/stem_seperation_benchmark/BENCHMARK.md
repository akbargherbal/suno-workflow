# Stem Separation Benchmark: Demucs (baseline) vs. open-source alternatives

Compares several open-source stem separation approaches on Google Colab
(T4 GPU), all reachable from the ideas discussed alongside this repo:

| Label | Tool | Model | Stems | Role |
|---|---|---|---|---|
| `demucs_htdemucs` | [Demucs](https://github.com/facebookresearch/demucs) | `htdemucs` (`--two-stems vocals`) | vocals / instrumental | **Baseline** |
| `demucs_htdemucs_ft` | Demucs | `htdemucs_ft` (fine-tuned) | vocals / instrumental | Slower Demucs variant, supposedly higher quality |
| `demucs_htdemucs_6s` | Demucs | `htdemucs_6s` | vocals, drums, bass, guitar, piano, other | Multi-instrument split (see `separate_stems_multi.py`) |
| `audio_separator_bs_roformer` | [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) | `model_bs_roformer_ep_317_sdr_12.9755.ckpt` | vocals / instrumental | Candidate from `separate_stems.py` |

All four are open-source and pip-installable — nothing closed/cloud-only
(e.g. no MVSep, Lalal.ai, Moises) is included, since those aren't scriptable
locally.

## What it measures

For every audio file, each method separates the same track and the script
records:

- **`elapsed_s`** — wall-clock separation time (model already loaded)
- **`audio_duration_s`** — length of the source track
- **`rtf`** — real-time factor, `audio_duration_s / elapsed_s`. Higher is
  faster (an RTF of 3x means 1 minute of processing per 3 minutes of audio)
- **`peak_gpu_mb`** — peak GPU memory allocated during that file's separation
- Model **load time** (measured once per method, outside the per-file loop,
  so it doesn't skew per-file speed numbers)

Quality (SDR) isn't computed automatically — that needs studio-quality
reference stems to compare against (e.g. MUSDB18), which most personal audio
libraries don't have. The script separates every file with every selected
method so you can **A/B listen** to the outputs under
`benchmark_results/<label>/`. This also lets you judge whether a slower
method's quality actually justifies its extra time — e.g. is
`demucs_htdemucs_ft` (4x slower than `htdemucs`, per the Demucs docs)
audibly better on your tracks, or not worth it?

Note `demucs_htdemucs_6s` isn't directly comparable to the 2-stem methods on
quality (different stems entirely), but its RTF/GPU numbers are still useful
for deciding whether multi-instrument separation is practical on a T4 for
your library size.

## Setup (Colab, T4 runtime)

```python
# Baseline + htdemucs_ft + htdemucs_6s all come from the same package
!pip install -q demucs

# Candidate (CUDA 12-compatible build, per separate_stems.py notes)
!pip install -q "audio-separator[gpu]"
!pip uninstall -y onnxruntime-gpu onnxruntime
!pip install -q "audio-separator" "onnxruntime-gpu<1.27.0"

!pip install -q soundfile pandas
```

Make sure **Runtime → Change runtime type → T4 GPU** is selected before installing.

## Running it

```bash
# Run everything in RUNS (see benchmark_separators.py header)
python benchmark_separators.py ./audio_data -o ./benchmark_results

# Only the baseline and the Roformer candidate
python benchmark_separators.py ./audio_data --runs demucs_htdemucs,audio_separator_bs_roformer

# Everything except one method (e.g. it already finished in a prior run)
python benchmark_separators.py ./audio_data --skip demucs_htdemucs_6s
```

Options:

| Flag | Default | Purpose |
|---|---|---|
| `-o / --output_dir` | `./benchmark_results` | Where separated stems + result files go |
| `--runs` | all labels in `RUNS` | Comma-separated subset of methods to benchmark |
| `--skip` | none | Comma-separated methods to exclude from this run |

To add, remove, or reconfigure a method (different model checkpoint, a
lighter/faster Roformer variant, etc.), edit the `RUNS` list at the top of
`benchmark_separators.py` — each entry is a small dict, no other code changes
needed.

## Output

- `benchmark_per_file.csv` — one row per (method, file)
- `benchmark_summary.csv` — averaged `elapsed_s`, `rtf`, `peak_gpu_mb`, and
  model load time per method, ordered with the baseline first
- `benchmark_raw.json` — same data as JSON
- Separated audio under `<label>/` per method, so all can be listened to
  side by side

## Reading the results

- **Speed**: compare `avg_rtf` against the baseline row — this is the
  "how much faster/slower is this method than plain `htdemucs`" number.
  Roughly matches what was already observed for BS-Roformer
  (~2.97s/it Roformer chunks, ~2 min for a ~4.5 min song → RTF ≈ 2.2–2.5x on
  a T4).
- **Model load overhead**: matters more on short files or many small clips in
  one session. Demucs' load time is dominated by first-time weight download
  (a one-off cost); Roformer's is usually a few seconds.
- **GPU memory**: useful if you plan to batch multiple files concurrently or
  hit T4's 16 GB limit. `htdemucs_6s` will generally use more memory than the
  2-stem runs since it's separating more sources at once.
- **Quality**: not scored automatically — spot-check a few tracks from each
  output folder for bleed-through, artifacts, or muddiness, and decide
  whether the slower method's RTF cost is actually buying you something
  audible.

## Related script: multi-instrument separation

This benchmark includes `demucs_htdemucs_6s` as a *speed* data point, but if
you actually want guitar/piano/etc. stems as a deliverable (not just a
benchmark run), use **`separate_stems_multi.py`** — a standalone script
mirroring `separate_stems.py`'s interface (batch/recursive input, per-song
output folders, MP3/bitrate options) but built around Demucs' `htdemucs_6s`
model instead of BS-Roformer:

```bash
python separate_stems_multi.py song.mp3
python separate_stems_multi.py ./songs_dir -o ./stems -r
```
