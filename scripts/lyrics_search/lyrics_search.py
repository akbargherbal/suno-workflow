#!/usr/bin/env python3
"""
Interactive lyrics search & export tool for workspace_manifest.json

Usage:
  python lyrics_search.py --int                    # Interactive mode
  python lyrics_search.py --title "exact title"    # Search by title substring
  python lyrics_search.py --sub "substring"          # Substring search in title + lyrics
  python lyrics_search.py --regex "pattern"          # Regex search in title + lyrics
  python lyrics_search.py --list                     # List all track titles
  python lyrics_search.py --all                      # Export all lyrics
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "download" / "lyrics"


def discover_manifest(cli_path: str | None) -> Path:
    """Locate workspace_manifest.json using a cascading strategy.

    Search order:
      1. Explicit --manifest CLI argument (if provided and exists)
      2. Current working directory
      3. Directory containing this script
      4. Interactive prompt (only when stdin is a terminal)
      5. Raise SystemExit with a helpful message
    """
    candidates: list[Path] = []

    # 1) CLI override
    if cli_path:
        p = Path(cli_path)
        if p.is_file():
            return p.resolve()
        candidates.append(p)  # keep for the error message

    # 2) Current working directory
    cwd_manifest = Path.cwd() / "workspace_manifest.json"
    if cwd_manifest.is_file():
        return cwd_manifest.resolve()
    candidates.append(cwd_manifest)

    # 3) Same directory as this script
    script_manifest = Path(__file__).resolve().parent / "workspace_manifest.json"
    if script_manifest.is_file():
        return script_manifest.resolve()
    candidates.append(script_manifest)

    # 4) Interactive prompt (only if stdin is a real terminal)
    if sys.stdin.isatty():
        print(
            "\n  workspace_manifest.json was not found automatically.\n"
            "  Searched locations:"
        )
        for c in candidates:
            print(f"    - {c}")
        print()

        for attempt in range(3):
            try:
                user_path = input(
                    "  Enter the path to workspace_manifest.json (or 'q' to quit): "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if user_path.lower() in ("q", "quit", "exit"):
                break

            if not user_path:
                continue

            p = Path(user_path).expanduser().resolve()
            if p.is_file():
                print(f"  Found: {p}\n")
                return p
            else:
                print(f"  File not found: {p}")

    # 5) All avenues exhausted
    tried = "\n    ".join(str(c) for c in candidates)
    print(
        f"\n  Error: Could not locate workspace_manifest.json.\n"
        f"  Locations checked:\n    {tried}\n\n"
        f"  Tip: Run this script from the directory that contains workspace_manifest.json,\n"
        f"       or pass the path explicitly:  python lyrics_search.py --manifest /path/to/workspace_manifest.json\n"
    )
    sys.exit(1)


def load_tracks(manifest_path: str) -> list[dict]:
    """Load tracks from the manifest JSON file."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tracks", [])


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safe version of the track title."""
    safe = re.sub(r'[\\/:*?"<>|]', "_", name.strip())
    safe = re.sub(r"_+", "_", safe)
    return safe or "untitled"


def save_lyrics(track: dict, index: int) -> Path:
    """Save a single track's lyrics to a .txt file and return the path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    title = sanitize_filename(track["original_title"])
    filename = f"{index:02d}_{title}.txt"
    out_path = OUTPUT_DIR / filename
    out_path.write_text(track["lyrics"], encoding="utf-8")
    return out_path


def print_track_summary(track: dict, index: int) -> None:
    """Print a one-line summary of a track."""
    print(f"  [{index:02d}] {track['original_title']}")


def search_by_title(tracks: list[dict], query: str) -> list[tuple[int, dict]]:
    """Case-insensitive substring match on title."""
    q = query.strip().lower()
    return [(i, t) for i, t in enumerate(tracks, 1) if q in t["original_title"].lower()]


def search_by_substring(tracks: list[dict], query: str) -> list[tuple[int, dict]]:
    """Substring search across both title and lyrics."""
    q = query.strip()
    return [
        (i, t)
        for i, t in enumerate(tracks, 1)
        if q in t["original_title"] or q in t["lyrics"]
    ]


def search_by_regex(tracks: list[dict], pattern: str) -> list[tuple[int, dict]]:
    """Regex search across both title and lyrics."""
    try:
        compiled = re.compile(pattern, re.DOTALL)
    except re.error as e:
        print(f"  ✗ Invalid regex: {e}")
        return []
    return [
        (i, t)
        for i, t in enumerate(tracks, 1)
        if compiled.search(t["original_title"]) or compiled.search(t["lyrics"])
    ]


def export_results(results: list[tuple[int, dict]]) -> None:
    """Export matched tracks' lyrics to individual files."""
    if not results:
        print("  No matches to export.")
        return
    print(f"\n  Exporting {len(results)} lyric file(s) to: {OUTPUT_DIR}\n")
    for idx, track in results:
        path = save_lyrics(track, idx)
        print(f"    ✔ {path.name}")
    print()


# ── Interactive REPL ──────────────────────────────────────────────────────────

BANNER = r"""
╔═══════════════════════════════════════════════════════════╗
║           Lyrics Search & Export  —  Interactive Mode     ║
╠═══════════════════════════════════════════════════════════╣
║  Commands:                                                ║
║    title <query>     Search by title (substring)           ║
║    sub <query>       Substring search in title + lyrics    ║
║    regex <pattern>   Regex search in title + lyrics        ║
║    list              List all track titles                 ║
║    export [indices]  Export last results (or specific #s)  ║
║    show <index>      Print lyrics of track #index          ║
║    all               Export all tracks                    ║
║    help              Show this help                        ║
║    quit / exit       Exit                                  ║
╚═══════════════════════════════════════════════════════════╝
"""


def interactive_loop(tracks: list[dict]) -> None:
    """Run the interactive REPL."""
    print(BANNER)
    last_results: list[tuple[int, dict]] = []

    while True:
        try:
            raw = input("\nlyrics> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not raw:
            continue

        parts = raw.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        if cmd == "help":
            print(BANNER)
            continue

        if cmd == "list":
            print(f"\n  {len(tracks)} tracks:\n")
            for i, t in enumerate(tracks, 1):
                print_track_summary(t, i)
            continue

        if cmd == "title" and arg:
            last_results = search_by_title(tracks, arg)
            _print_results(last_results, f"Title matches for '{arg}'")
            continue

        if cmd == "sub" and arg:
            last_results = search_by_substring(tracks, arg)
            _print_results(last_results, f"Substring matches for '{arg}'")
            continue

        if cmd == "regex" and arg:
            last_results = search_by_regex(tracks, arg)
            _print_results(last_results, f"Regex matches for r'{arg}'")
            continue

        if cmd == "export":
            if arg.strip():
                indices = _parse_indices(arg, len(tracks))
                to_export = [(i, tracks[i - 1]) for i in indices]
                export_results(to_export)
            else:
                export_results(last_results)
            continue

        if cmd == "show" and arg:
            try:
                idx = int(arg)
                track = tracks[idx - 1]
                print(f"\n{'─' * 60}")
                print(f"  Track [{idx:02d}]: {track['original_title']}")
                print(f"  File  : {track['assigned_filename']}")
                print(f"{'─' * 60}")
                print(track["lyrics"])
                print(f"{'─' * 60}")
            except (ValueError, IndexError):
                print(f"  ✗ Invalid index. Use 1-{len(tracks)}.")
            continue

        if cmd == "all":
            all_results = [(i, t) for i, t in enumerate(tracks, 1)]
            export_results(all_results)
            continue

        print(f"  ✗ Unknown command: '{cmd}'. Type 'help' for available commands.")


def _print_results(results: list[tuple[int, dict]], header: str) -> None:
    """Display search results and a hint about exporting."""
    if not results:
        print(f"\n  No matches for: {header}")
        return
    print(f"\n  {len(results)} result(s) for {header}:\n")
    for idx, track in results:
        print_track_summary(track, idx)
    print(f"\n  → Type 'export' to save these to files.")


def _parse_indices(arg: str, total: int) -> list[int]:
    """Parse index specs like '1 3 5', '1-5', or '1-3 7 9-11'."""
    indices = set()
    for token in arg.split():
        if "-" in token and not token.startswith("-"):
            try:
                lo, hi = token.split("-", 1)
                lo, hi = int(lo), int(hi)
                indices.update(range(max(lo, 1), min(hi, total) + 1))
            except ValueError:
                print(f"  ✗ Cannot parse range: '{token}'")
        else:
            try:
                val = int(token)
                if 1 <= val <= total:
                    indices.add(val)
                else:
                    print(f"  ✗ Index {val} out of range (1-{total}).")
            except ValueError:
                print(f"  ✗ Cannot parse: '{token}'")
    return sorted(indices)


# ── CLI entry point ────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search and export lyrics from workspace_manifest.json"
    )
    parser.add_argument(
        "--int",
        action="store_true",
        dest="interactive",
        help="Launch interactive mode",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Search tracks by title substring and export matches",
    )
    parser.add_argument(
        "--sub",
        type=str,
        default=None,
        help="Substring search in title + lyrics and export matches",
    )
    parser.add_argument(
        "--regex",
        type=str,
        default=None,
        help="Regex search in title + lyrics and export matches",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_all",
        help="List all track titles and exit",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="export_all",
        help="Export all lyrics and exit",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to workspace_manifest.json (auto-detected if omitted)",
    )

    args = parser.parse_args()

    manifest_path = discover_manifest(args.manifest)
    tracks = load_tracks(str(manifest_path))
    print(f"  Loaded {len(tracks)} tracks from manifest.\n")

    # No search flag → default to interactive
    if (
        not args.title
        and not args.sub
        and not args.regex
        and not args.list_all
        and not args.export_all
        and not args.interactive
    ):
        args.interactive = True

    if args.interactive:
        interactive_loop(tracks)
        return

    if args.list_all:
        for i, t in enumerate(tracks, 1):
            print(f"  [{i:02d}] {t['original_title']}")
        return

    if args.export_all:
        all_results = [(i, t) for i, t in enumerate(tracks, 1)]
        export_results(all_results)
        return

    if args.title:
        results = search_by_title(tracks, args.title)
        _print_results(results, f"title '{args.title}'")
        export_results(results)
        return

    if args.sub:
        results = search_by_substring(tracks, args.sub)
        _print_results(results, f"substring '{args.sub}'")
        export_results(results)
        return

    if args.regex:
        results = search_by_regex(tracks, args.regex)
        _print_results(results, f"regex r'{args.regex}'")
        export_results(results)
        return


if __name__ == "__main__":
    main()
