#!/usr/bin/env python3
"""
master_tracks.py
=================

A small CLI utility built on top of the `matchering` library
(https://github.com/sergree/matchering) for mastering audio tracks
against one or more reference tracks.

Three modes are supported:

1. single   - master one target track against one reference track.
2. batch    - master every audio file in a folder against a single
              reference track (handy for making a whole album sound
              consistent).
3. compare  - master one target track against MULTIPLE reference
              tracks, one output per reference, each file prefixed
              with the name of the reference that produced it. Useful
              for A/B-ing which reference gives the best result.

Install the dependency first:

    python3 -m pip install -U matchering

On Linux you'll also need libsndfile:

    sudo apt update && sudo apt -y install libsndfile1

(Optional) install ffmpeg if you want to load/save mp3:

    sudo apt -y install ffmpeg

See README.md for full usage examples.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

try:
    import matchering as mg
except ImportError:
    sys.exit(
        "The 'matchering' package is not installed.\n"
        "Install it with: python3 -m pip install -U matchering"
    )

AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".aiff", ".aif"}

BIT_DEPTH_SAVERS = {
    16: mg.pcm16,
    24: mg.pcm24,
}


def build_results(output_path: Path, bit_depth: int) -> list:
    """Return the list of matchering result savers for the requested bit depth."""
    saver = BIT_DEPTH_SAVERS.get(bit_depth)
    if saver is None:
        raise ValueError(f"Unsupported bit depth: {bit_depth} (choose 16 or 24)")
    return [saver(str(output_path))]


def master_one(target: Path, reference: Path, output: Path, bit_depth: int) -> None:
    """Master a single target track against a single reference track."""
    output.parent.mkdir(parents=True, exist_ok=True)
    mg.process(
        target=str(target),
        reference=str(reference),
        results=build_results(output, bit_depth),
    )


def master_batch(target_dir: Path, reference: Path, output_dir: Path, bit_depth: int) -> None:
    """Master every audio file found in target_dir against a single reference track."""
    output_dir.mkdir(parents=True, exist_ok=True)
    tracks = sorted(
        p for p in target_dir.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    )

    if not tracks:
        sys.exit(f"No audio files found in {target_dir}")

    for track in tracks:
        out_path = output_dir / f"{track.stem}_mastered.wav"
        logging.info("Mastering %s -> %s", track.name, out_path.name)
        try:
            master_one(track, reference, out_path, bit_depth)
        except Exception as exc:  # keep batch running even if one file fails
            logging.error("Failed to master %s: %s", track.name, exc)


def master_compare(
    target: Path, references: list[Path], output_dir: Path, bit_depth: int
) -> None:
    """
    Master a single target against several reference tracks, producing one
    output file per reference so the user can compare which reference
    yields the best result. Each output is prefixed with the reference's
    filename, e.g.:

        <reference_stem>__<target_stem>.wav
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # de-duplicate while preserving order, in case the same reference was
    # passed in twice by mistake
    seen: set[Path] = set()
    unique_references = []
    for ref in references:
        resolved = ref.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_references.append(ref)

    for reference in unique_references:
        if not reference.is_file():
            logging.error("Reference file not found, skipping: %s", reference)
            continue

        out_path = output_dir / f"{reference.stem}__{target.stem}.wav"
        logging.info("Mastering with reference %s -> %s", reference.name, out_path.name)
        try:
            master_one(target, reference, out_path, bit_depth)
        except Exception as exc:  # keep going even if one reference fails
            logging.error("Failed to master with reference %s: %s", reference.name, exc)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Master audio tracks against reference track(s) using matchering."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    common_bit_depth = dict(
        type=int, choices=[16, 24], default=16,
        help="Bit depth of the mastered result (default: 16)",
    )

    # --- single ---
    p_single = subparsers.add_parser("single", help="Master one target against one reference")
    p_single.add_argument("target", type=Path, help="Track to master")
    p_single.add_argument("reference", type=Path, help="Reference ('wet') track")
    p_single.add_argument("output", type=Path, help="Path to write the mastered file to")
    p_single.add_argument("-b", "--bit-depth", **common_bit_depth)

    # --- batch ---
    p_batch = subparsers.add_parser(
        "batch", help="Master every track in a folder against one reference"
    )
    p_batch.add_argument("target_dir", type=Path, help="Folder of tracks to master")
    p_batch.add_argument("reference", type=Path, help="Reference ('wet') track")
    p_batch.add_argument("output_dir", type=Path, help="Folder to write mastered files to")
    p_batch.add_argument("-b", "--bit-depth", **common_bit_depth)

    # --- compare ---
    p_compare = subparsers.add_parser(
        "compare",
        help="Master one target against MULTIPLE references, for A/B comparison",
    )
    p_compare.add_argument("target", type=Path, help="Track to master")
    p_compare.add_argument("output_dir", type=Path, help="Folder to write mastered files to")
    p_compare.add_argument(
        "-r", "--reference",
        dest="references",
        type=Path,
        action="append",
        default=[],
        help="Reference track to test; repeat -r for each reference, e.g. "
             "-r ref1.wav -r ref2.wav -r ref3.wav",
    )
    p_compare.add_argument(
        "-d", "--reference-dir",
        dest="reference_dir",
        type=Path,
        help="Folder containing reference tracks; every audio file inside "
             "is used as a reference. Can be combined with -r.",
    )
    p_compare.add_argument("-b", "--bit-depth", **common_bit_depth)

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress logging",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(message)s",
    )
    if not args.quiet:
        mg.log(logging.info)

    if args.mode == "single":
        if not args.target.is_file():
            sys.exit(f"Target file not found: {args.target}")
        if not args.reference.is_file():
            sys.exit(f"Reference file not found: {args.reference}")
        logging.info("Mastering %s -> %s", args.target.name, args.output.name)
        master_one(args.target, args.reference, args.output, args.bit_depth)

    elif args.mode == "batch":
        if not args.target_dir.is_dir():
            sys.exit(f"Target folder not found: {args.target_dir}")
        if not args.reference.is_file():
            sys.exit(f"Reference file not found: {args.reference}")
        master_batch(args.target_dir, args.reference, args.output_dir, args.bit_depth)

    elif args.mode == "compare":
        if not args.target.is_file():
            sys.exit(f"Target file not found: {args.target}")

        references = list(args.references)
        if args.reference_dir is not None:
            if not args.reference_dir.is_dir():
                sys.exit(f"Reference folder not found: {args.reference_dir}")
            found = sorted(
                p for p in args.reference_dir.iterdir()
                if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
            )
            if not found:
                sys.exit(f"No audio files found in {args.reference_dir}")
            references.extend(found)

        if len(references) < 2:
            sys.exit(
                "compare mode needs at least two reference tracks "
                "(use -r/--reference repeatedly and/or -d/--reference-dir)"
            )
        master_compare(args.target, references, args.output_dir, args.bit_depth)

    logging.info("Done.")


if __name__ == "__main__":
    main()
