#!/usr/bin/env python3
"""
separate_stems_multi.py

Multi-instrument stem separation (vocals, drums, bass, guitar, piano, other)
using Demucs (open-source, Meta AI Research) — specifically the `htdemucs_6s`
model, the only widely-used open checkpoint that splits guitar and piano out
as their own stems instead of lumping them into "other".

This is a *separate* script from separate_stems.py on purpose: that script is
tuned for the 2-stem vocals/instrumental case (BS-Roformer via
audio-separator), while this one targets full multi-instrument splits, which
currently only Demucs' 6-stem checkpoint does out of the box among
open-source models.

Usage:
    python separate_stems_multi.py song.mp3
    python separate_stems_multi.py ./songs_dir -o ./stems -r
    python separate_stems_multi.py song.mp3 -m htdemucs_ft   # 4-stem instead of 6
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg",
    ".wma", ".opus", ".aiff", ".aif", ".alac", ".mp4", ".webm", ".caf"
}

# Stems produced per Demucs model. htdemucs_6s is the only open checkpoint
# that separates guitar/piano individually; the others fall back to the
# standard 4-stem split (guitar/piano bleed into "other").
MODEL_STEMS = {
    "htdemucs_6s": ["vocals", "drums", "bass", "guitar", "piano", "other"],
    "htdemucs": ["vocals", "drums", "bass", "other"],
    "htdemucs_ft": ["vocals", "drums", "bass", "other"],
    "mdx_extra": ["vocals", "drums", "bass", "other"],
}

# Nicely-capitalized names for output filenames, e.g. "<song>-Guitar.mp3"
STEM_DISPLAY_NAMES = {
    "vocals": "Vocals",
    "drums": "Drums",
    "bass": "Bass",
    "guitar": "Guitar",
    "piano": "Piano",
    "other": "Other",
}


def process_audio_stems_multi(
    input_path: str,
    output_base_dir: str = ".",
    model_filename: str = "htdemucs_6s",
    output_format: str = "MP3",
    output_bitrate: str = "320k",
    recursive: bool = False,
    device: str = None,
) -> dict:
    """
    Separates audio into multiple instrument stems using Demucs.

    Args:
        input_path: Path to input audio file or directory.
        output_base_dir: Explicit output directory where results will be saved.
        model_filename: Demucs model name (default 'htdemucs_6s' for
            vocals/drums/bass/guitar/piano/other; use 'htdemucs' or
            'htdemucs_ft' for the standard 4-stem split).
        output_format: 'MP3' or 'WAV'. Demucs only offers these two natively.
        output_bitrate: Bitrate for MP3 output (e.g. '320k'). Ignored for WAV.
        recursive: If input_path is a directory, recursively scan subdirectories.
        device: 'cuda' or 'cpu'. If None, Demucs auto-detects (uses GPU if available).

    Returns:
        Dict containing lists of 'successful' and 'failed' file processing records.
    """
    input_p = Path(input_path).expanduser().resolve()

    if not input_p.exists():
        raise FileNotFoundError(f"Error: Path '{input_path}' does not exist.")

    if input_p.is_file():
        if input_p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported audio format: '{input_p.suffix}'. "
                f"Supported formats: {sorted(SUPPORTED_EXTENSIONS)}"
            )
        audio_files = [input_p]
    elif input_p.is_dir():
        glob_pattern = "**/*" if recursive else "*"
        audio_files = sorted(
            [
                f for f in input_p.glob(glob_pattern)
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
            ],
            key=lambda p: p.name.lower()
        )
        if not audio_files:
            print(f"No supported audio files found in directory '{input_p}'.")
            return {"successful": [], "failed": []}
    else:
        raise ValueError(f"Invalid path type: '{input_path}'")

    if model_filename not in MODEL_STEMS:
        print(
            f"Warning: unrecognized model '{model_filename}', assuming it "
            f"produces the standard 4 stems (vocals/drums/bass/other)."
        )
    stems = MODEL_STEMS.get(model_filename, ["vocals", "drums", "bass", "other"])

    print(f"Found {len(audio_files)} audio file(s) to process.")
    print(f"Model: {model_filename}  ->  stems: {', '.join(stems)}")

    base_out_path = Path(output_base_dir).expanduser().resolve()
    base_out_path.mkdir(parents=True, exist_ok=True)
    print(f"Base output directory set to: {base_out_path}")

    # Scratch area for Demucs' own output layout (it insists on
    # <scratch>/<model>/<track_name>/<stem>.<ext>), which we then flatten
    # and rename into <output_base_dir>/<song_name>/<song_name>-<Stem>.<ext>
    scratch_dir = base_out_path / "_demucs_raw"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    fmt = output_format.upper()
    if fmt not in ("MP3", "WAV"):
        raise ValueError("output_format must be 'MP3' or 'WAV' (Demucs' native export options).")

    successful_files = []
    failed_files = []

    for idx, file_path in enumerate(audio_files, start=1):
        song_name = file_path.stem
        song_output_dir = base_out_path / song_name
        song_output_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{idx}/{len(audio_files)}] Processing: {file_path.name}")
        print(f"Destination: {song_output_dir}")

        cmd = [
            sys.executable, "-m", "demucs",
            "-n", model_filename,
            "-o", str(scratch_dir),
        ]
        if fmt == "MP3":
            cmd += ["--mp3", "--mp3-bitrate", output_bitrate.rstrip("k")]
        if device:
            cmd += ["-d", device]
        cmd.append(str(file_path))

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            raw_track_dir = scratch_dir / model_filename / song_name
            if not raw_track_dir.is_dir():
                raise RuntimeError(
                    f"Expected Demucs output at '{raw_track_dir}' but it wasn't created."
                )

            ext = "mp3" if fmt == "MP3" else "wav"
            produced_files = []
            for stem in stems:
                src = raw_track_dir / f"{stem}.{ext}"
                if not src.exists():
                    print(f"  Warning: expected stem file missing: {src}", file=sys.stderr)
                    continue
                display = STEM_DISPLAY_NAMES.get(stem, stem.capitalize())
                dst = song_output_dir / f"{song_name}-{display}.{ext}"
                shutil.move(str(src), str(dst))
                produced_files.append(dst)

            print(f"Completed '{song_name}':")
            for outfile in produced_files:
                print(f"  \u2514\u2500 {outfile}")
            successful_files.append((file_path, produced_files))
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip() if e.stderr else str(e)
            print(f"ERROR processing '{file_path.name}': {err_msg}", file=sys.stderr)
            failed_files.append((file_path, err_msg))
        except Exception as e:
            print(f"ERROR processing '{file_path.name}': {e}", file=sys.stderr)
            failed_files.append((file_path, str(e)))

        print("-" * 50)

    shutil.rmtree(scratch_dir, ignore_errors=True)

    print("\n" + "=" * 50)
    print(f"BATCH PROCESSING SUMMARY: {len(successful_files)} succeeded, {len(failed_files)} failed.")
    if failed_files:
        print("Failed files:")
        for fpath, err in failed_files:
            print(f"  - {fpath.name}: {err}")
    print("=" * 50)

    return {"successful": successful_files, "failed": failed_files}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Separate audio into multiple instrument stems (vocals, drums, bass, guitar, piano, other) using Demucs."
    )
    parser.add_argument("input_path", type=str, help="Path to input audio file or directory.")
    parser.add_argument("-o", "--output_dir", type=str, default=".", help="Explicit destination directory for results (default: current directory).")
    parser.add_argument(
        "-m", "--model", type=str, default="htdemucs_6s",
        help="Demucs model name. 'htdemucs_6s' (default) gives 6 stems including guitar/piano; "
             "'htdemucs' or 'htdemucs_ft' give the standard 4 stems.",
    )
    parser.add_argument("-f", "--format", type=str, default="MP3", choices=["MP3", "WAV", "mp3", "wav"], help="Output format (Demucs supports MP3 or WAV natively).")
    parser.add_argument("-b", "--bitrate", type=str, default="320k", help="MP3 bitrate (e.g. 320k). Ignored for WAV.")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recursively search subdirectories if input_path is a directory.")
    parser.add_argument("-d", "--device", type=str, default=None, choices=[None, "cuda", "cpu"], help="Force 'cuda' or 'cpu'. Default: Demucs auto-detects.")

    args = parser.parse_args()

    process_audio_stems_multi(
        input_path=args.input_path,
        output_base_dir=args.output_dir,
        model_filename=args.model,
        output_format=args.format,
        output_bitrate=args.bitrate,
        recursive=args.recursive,
        device=args.device,
    )
