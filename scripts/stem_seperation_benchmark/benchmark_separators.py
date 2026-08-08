#!/usr/bin/env python3
"""
Benchmark: Demucs (baseline) vs. other open-source stem separation methods
(BS-Roformer / audio-separator, Demucs htdemucs_ft, Demucs htdemucs_6s).

Designed for Google Colab with a T4 GPU runtime.

Speed (RTF), GPU memory, and model load time are measured automatically.
Quality is *not* scored automatically (no reference stems / SDR) — every
method writes its stems to its own output folder so you can A/B listen and
judge whether the slower methods' quality actually justifies the extra time.

Usage:
    python benchmark_separators.py ./audio_data -o ./benchmark_results
    python benchmark_separators.py ./audio_data --runs demucs_htdemucs,audio_separator_bs_roformer
    python benchmark_separators.py ./audio_data --skip demucs_htdemucs_ft   # re-run all but one
"""

import argparse
import gc
import json
import subprocess
import sys
import time
from pathlib import Path

import torch
import soundfile as sf

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus"}

# --------------------------------------------------------------------------
# Methods to benchmark. Edit this list to add/remove runs.
#
#   label       -- unique name, used for output subfolder + result rows
#   kind        -- "demucs" or "audio_separator"
#   model       -- model name/checkpoint passed to the tool
#   two_stems   -- (demucs only) "vocals" for a 2-stem vocals/no_vocals split,
#                  or None for the model's full/native stem split (used for
#                  htdemucs_6s's 6 stems, so it can be A/B'd against the
#                  multi-instrument workflow, not just vocals/instrumental)
# --------------------------------------------------------------------------
RUNS = [
    {
        "label": "demucs_htdemucs",              # BASELINE
        "kind": "demucs",
        "model": "htdemucs",
        "two_stems": "vocals",
    },
    {
        "label": "demucs_htdemucs_ft",
        "kind": "demucs",
        "model": "htdemucs_ft",
        "two_stems": "vocals",
    },
    {
        "label": "demucs_htdemucs_6s",
        "kind": "demucs",
        "model": "htdemucs_6s",
        "two_stems": None,                       # full 6-stem split, not vocals/instrumental
    },
    {
        "label": "audio_separator_bs_roformer",
        "kind": "audio_separator",
        "model": "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    },
]


def get_audio_duration(path: Path) -> float:
    info = sf.info(str(path))
    return info.frames / info.samplerate


def reset_gpu_stats() -> None:
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()


def gpu_peak_mb() -> float:
    if torch.cuda.is_available():
        return torch.cuda.max_memory_allocated() / (1024 ** 2)
    return 0.0


def bench_demucs(audio_files, output_dir: Path, label: str, model: str, two_stems: str = None):
    """
    Times a Demucs run (any model, any stem mode) per file.
    Uses the `demucs` CLI via subprocess since that's the supported entrypoint.
    """
    results = []
    run_out = output_dir / label
    run_out.mkdir(parents=True, exist_ok=True)

    def build_cmd(out_dir: Path, audio_file: Path):
        cmd = [sys.executable, "-m", "demucs", "-n", model]
        if two_stems:
            cmd += ["--two-stems", two_stems]
        cmd += ["-o", str(out_dir), str(audio_file)]
        return cmd

    # Warm-up run: downloads + loads model weights once so that cost isn't
    # charged to the first timed file. Output is discarded.
    reset_gpu_stats()
    t0 = time.time()
    subprocess.run(build_cmd(run_out / "_warmup", audio_files[0]), check=True, capture_output=True)
    load_time = time.time() - t0
    print(f"[{label}] warmup / model load: {load_time:.1f}s")

    for f in audio_files:
        duration = get_audio_duration(f)
        reset_gpu_stats()
        t0 = time.time()
        subprocess.run(build_cmd(run_out, f), check=True, capture_output=True)
        elapsed = time.time() - t0
        results.append({
            "method": label,
            "file": f.name,
            "audio_duration_s": round(duration, 2),
            "elapsed_s": round(elapsed, 2),
            "rtf": round(duration / elapsed, 3) if elapsed else None,
            "peak_gpu_mb": round(gpu_peak_mb(), 1),
        })
        print(f"[{label}] {f.name}: {elapsed:.1f}s (RTF {duration / elapsed:.2f}x)")

    return results, load_time


def bench_audio_separator(audio_files, output_dir: Path, label: str, model_filename: str):
    """Times an audio-separator run (e.g. BS-Roformer) for vocals/instrumental."""
    from audio_separator.separator import Separator

    run_out = output_dir / label
    run_out.mkdir(parents=True, exist_ok=True)

    separator = Separator(output_format="MP3", output_bitrate="320k", log_level=40)

    reset_gpu_stats()
    t0 = time.time()
    separator.load_model(model_filename=model_filename)
    load_time = time.time() - t0
    print(f"[{label}] model load: {load_time:.1f}s")

    results = []
    for f in audio_files:
        duration = get_audio_duration(f)
        song_dir = run_out / f.stem
        song_dir.mkdir(parents=True, exist_ok=True)

        # audio_separator caches output_dir on the loaded model_instance at
        # load_model() time, so sync it explicitly per file.
        separator.output_dir = str(song_dir)
        if separator.model_instance is not None:
            separator.model_instance.output_dir = str(song_dir)

        reset_gpu_stats()
        t0 = time.time()
        separator.separate(
            audio_file_path=str(f),
            custom_output_names={
                "Vocals": f"{f.stem}-Vocals",
                "Instrumental": f"{f.stem}-Instrumental",
            },
        )
        elapsed = time.time() - t0
        results.append({
            "method": label,
            "file": f.name,
            "audio_duration_s": round(duration, 2),
            "elapsed_s": round(elapsed, 2),
            "rtf": round(duration / elapsed, 3) if elapsed else None,
            "peak_gpu_mb": round(gpu_peak_mb(), 1),
        })
        print(f"[{label}] {f.name}: {elapsed:.1f}s (RTF {duration / elapsed:.2f}x)")

    return results, load_time


def summarize(all_results, load_times):
    import pandas as pd

    df = pd.DataFrame(all_results)

    print("\n" + "=" * 60)
    print("PER-FILE RESULTS")
    print("=" * 60)
    print(df.to_string(index=False))

    summary = df.groupby("method").agg(
        files=("file", "count"),
        avg_elapsed_s=("elapsed_s", "mean"),
        avg_rtf=("rtf", "mean"),
        avg_peak_gpu_mb=("peak_gpu_mb", "mean"),
    ).round(2)
    summary["model_load_s"] = [load_times.get(m, None) for m in summary.index]

    # Order rows to match RUNS definition order rather than alphabetically,
    # so the baseline always appears first.
    order = [r["label"] for r in RUNS if r["label"] in summary.index]
    summary = summary.reindex(order)

    print("\n" + "=" * 60)
    print("SUMMARY BY METHOD (baseline first)")
    print("=" * 60)
    print(summary.to_string())

    return df, summary


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Demucs (baseline) vs. other open-source stem separation methods."
    )
    parser.add_argument("input_dir", type=str, help="Directory of audio files to benchmark.")
    parser.add_argument("-o", "--output_dir", type=str, default="./benchmark_results")
    parser.add_argument(
        "--runs", type=str, default=None,
        help="Comma-separated list of run labels to include (default: all runs in RUNS). "
             f"Available: {', '.join(r['label'] for r in RUNS)}",
    )
    parser.add_argument(
        "--skip", type=str, default=None,
        help="Comma-separated list of run labels to exclude, e.g. to re-run "
             "only the ones that failed or weren't run yet.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_files = sorted(
        [f for f in input_dir.glob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS],
        key=lambda p: p.name.lower(),
    )
    if not audio_files:
        raise SystemExit(f"No supported audio files found in {input_dir}")
    print(f"Benchmarking on {len(audio_files)} file(s) from {input_dir}\n")

    selected_labels = set(args.runs.split(",")) if args.runs else {r["label"] for r in RUNS}
    skip_labels = set(args.skip.split(",")) if args.skip else set()
    active_runs = [r for r in RUNS if r["label"] in selected_labels and r["label"] not in skip_labels]

    if not active_runs:
        raise SystemExit("No runs selected. Check --runs / --skip against the labels in RUNS.")

    print("Runs to benchmark:")
    for r in active_runs:
        print(f"  - {r['label']} ({r['kind']}, model={r['model']})")
    print()

    all_results = []
    load_times = {}

    for run in active_runs:
        if run["kind"] == "demucs":
            results, load_time = bench_demucs(
                audio_files, output_dir, run["label"], run["model"], run.get("two_stems")
            )
        elif run["kind"] == "audio_separator":
            results, load_time = bench_audio_separator(
                audio_files, output_dir, run["label"], run["model"]
            )
        else:
            print(f"Skipping unknown run kind '{run['kind']}' for label '{run['label']}'", file=sys.stderr)
            continue

        all_results += results
        load_times[run["label"]] = round(load_time, 2)

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    df, summary = summarize(all_results, load_times)

    df.to_csv(output_dir / "benchmark_per_file.csv", index=False)
    summary.to_csv(output_dir / "benchmark_summary.csv")
    with open(output_dir / "benchmark_raw.json", "w") as fh:
        json.dump(all_results, fh, indent=2, ensure_ascii=False)

    print(f"\nSaved results to {output_dir}")


if __name__ == "__main__":
    main()
