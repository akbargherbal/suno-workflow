#!/usr/bin/env python3
"""Reformat a raw song batch into the standard batch format.

Input:  a JSON list of objects, each with "name", "style" and "lyrics",
        plus optional per-song keys (currently: "seed").
Output: {"defaults": {"repeat": N, ...}, "songs": [{name, style, lyrics, ...}]}

Optional keys are emitted only when present in the input. With no new
flags the output is identical to earlier versions of this script.

Seeds are per-song only: the downstream generator rejects "seed" inside
"defaults". --seed therefore fills in a seed on each song that lacks one.

Defaults precedence (lowest -> highest):
    built-in (repeat=1)
    < input file's own "defaults"   (only with --keep-input-defaults)
    < --defaults-file
    < --default KEY=VALUE           (repeatable)
    < --repeat
A song's own value always wins over any default.

Usage:
    python format_songs.py batch_01.json
    python format_songs.py batch_01.json -o out.json --repeat 2
    python format_songs.py batch_01.json --seed 42                  # same seed on every song
    python format_songs.py batch_01.json --seed 42 --derive-seeds   # 42, 43, 44, ...
    python format_songs.py batch_01.json --default quantile=0.95 --keep-extra
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

REQUIRED_KEYS = ("name", "style", "lyrics")


def _validate_int(value: Any) -> int:
    # bool is a subclass of int in Python; reject it explicitly.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("must be an integer")
    return value


# Optional per-song keys and how to validate them. To support a new optional
# key, add one line here. Validators run only when the key is present.
FIELD_SPECS: dict[str, Callable[[Any], Any]] = {
    "seed": _validate_int,
}
OPTIONAL_KEYS = tuple(FIELD_SPECS)

# Keys the downstream generator accepts inside "defaults". Anything else is
# rejected here so the error shows up at format time, not generation time.
# "seed" is deliberately absent: seeds are per-song only.
ALLOWED_DEFAULT_KEYS = ("lora", "quantile", "repeat", "style", "style_file")

# Extra validation for allowed default keys (others pass through unchecked).
DEFAULTS_SPECS: dict[str, Callable[[Any], Any]] = {
    "repeat": _validate_int,
}


def validate_defaults(defaults: dict) -> dict:
    """Reject keys the generator doesn't accept; validate known value types."""
    unknown = [k for k in defaults if k not in ALLOWED_DEFAULT_KEYS]
    if unknown:
        hint = " Seeds are per-song only; use --seed." if "seed" in unknown else ""
        raise ValueError(
            f"Unknown default key(s): {', '.join(unknown)} "
            f"(allowed: {', '.join(ALLOWED_DEFAULT_KEYS)}).{hint}"
        )
    for key, value in defaults.items():
        check = DEFAULTS_SPECS.get(key)
        if check is not None:
            try:
                check(value)
            except ValueError as exc:
                raise ValueError(f"Default '{key}' {exc}.") from None
    return defaults


def extract_input_defaults(raw: object) -> dict:
    """Return the 'defaults' block of an already-formatted input, else {}."""
    if isinstance(raw, dict) and "defaults" in raw:
        if not isinstance(raw["defaults"], dict):
            raise ValueError("Input 'defaults' must be an object.")
        return dict(raw["defaults"])
    return {}


def format_batch(
    raw: object,
    repeat: int = 1,
    *,
    defaults: dict | None = None,
    seed: int | None = None,
    keep_extra: bool = False,
    derive_seeds: bool = False,
    warn: Callable[[str], None] | None = None,
) -> dict:
    """Convert raw song data into the formatted batch structure.

    repeat        -- value for defaults.repeat (kept for backward compatibility).
    defaults      -- extra/overriding defaults; may include "repeat". Only keys in
                     ALLOWED_DEFAULT_KEYS are accepted.
    seed          -- fill this seed into every song that has none of its own
                     (never written to defaults).
    derive_seeds  -- with `seed`, give song at 0-based position n the seed
                     `seed + n` instead of the same seed for all.
    keep_extra    -- keep unknown per-song keys (after known ones, input order).
                     Otherwise they are dropped, and `warn` is told about them.
    warn          -- callback for non-fatal messages (e.g. dropped keys).
    """
    # Accept an already-formatted file too, so the script is idempotent.
    if isinstance(raw, dict) and "songs" in raw:
        raw = raw["songs"]

    if not isinstance(raw, list):
        raise ValueError("Input must be a JSON list of song objects.")

    final_defaults = validate_defaults({"repeat": repeat, **(defaults or {})})

    if seed is not None:
        try:
            _validate_int(seed)
        except ValueError as exc:
            raise ValueError(f"Seed {exc}.") from None
    if derive_seeds and seed is None:
        raise ValueError("--derive-seeds requires a seed (use --seed).")

    songs = []
    dropped: dict[str, None] = {}  # ordered set of dropped key names
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Song #{i} is not an object.")
        missing = [k for k in REQUIRED_KEYS if k not in item]
        if missing:
            raise ValueError(f"Song #{i} is missing keys: {', '.join(missing)}")

        # Rebuild the dict to enforce key order: required, optional, extras.
        song = {k: item[k] for k in REQUIRED_KEYS}

        # Membership check, not truthiness: seed=0 is valid and must survive.
        for key in OPTIONAL_KEYS:
            if key in item:
                try:
                    song[key] = FIELD_SPECS[key](item[key])
                except ValueError as exc:
                    raise ValueError(f"Song #{i}: '{key}' {exc}.") from None

        # A song's own seed always wins; otherwise fill from --seed.
        if seed is not None and "seed" not in song:
            song["seed"] = seed + (i - 1) if derive_seeds else seed

        extras = [k for k in item if k not in REQUIRED_KEYS and k not in FIELD_SPECS]
        if keep_extra:
            for key in extras:
                song[key] = item[key]
        else:
            dropped.update(dict.fromkeys(extras))

        songs.append(song)

    if dropped and warn is not None:
        warn(
            "ignored unknown song keys: " + ", ".join(dropped)
            + " (use --keep-extra to keep them)"
        )

    return {"defaults": final_defaults, "songs": songs}


def _parse_default(text: str) -> tuple[str, Any]:
    """Parse KEY=VALUE; VALUE is JSON if it parses, else a plain string."""
    key, sep, value = text.partition("=")
    key = key.strip()
    if not sep or not key:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {text!r}")
    try:
        return key, json.loads(value)
    except json.JSONDecodeError:
        return key, value


def _load_defaults_file(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Defaults file {path} must contain a JSON object.")
    return data


def build_defaults(args: argparse.Namespace, raw: object) -> dict:
    """Resolve the defaults layers into one dict (see module docstring)."""
    defaults: dict[str, Any] = {"repeat": 1}  # built-in
    if args.keep_input_defaults:
        defaults.update(extract_input_defaults(raw))
    if args.defaults_file:
        defaults.update(_load_defaults_file(args.defaults_file))
    for key, value in args.default or []:
        defaults[key] = value
    # None means "not provided", so an explicit --repeat 1 still overrides.
    if args.repeat is not None:
        defaults["repeat"] = args.repeat
    return defaults


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="path to the raw JSON file")
    parser.add_argument(
        "-o", "--output", type=Path,
        help="output path (default: <input>_formatted.json)",
    )
    parser.add_argument(
        "-r", "--repeat", type=int, default=None,
        help="value for defaults.repeat (default: 1)",
    )
    parser.add_argument(
        "-s", "--seed", type=int, default=None,
        help="seed written onto every song that has no seed of its own "
             "(per-song only, never in defaults)",
    )
    parser.add_argument(
        "-d", "--default", action="append", type=_parse_default,
        metavar="KEY=VALUE",
        help="set a defaults key (allowed: " + ", ".join(ALLOWED_DEFAULT_KEYS)
             + "); VALUE is parsed as JSON if possible (repeatable)",
    )
    parser.add_argument(
        "--defaults-file", type=Path,
        help="JSON object whose keys are merged into defaults",
    )
    parser.add_argument(
        "--keep-input-defaults", action="store_true",
        help="when the input is an already-formatted file, keep its defaults "
             "instead of resetting them",
    )
    parser.add_argument(
        "--keep-extra", action="store_true",
        help="keep unknown per-song keys instead of dropping them",
    )
    parser.add_argument(
        "--derive-seeds", action="store_true",
        help="with --seed, give song n the seed 'seed + n' (0-based) instead "
             "of the same seed for all",
    )
    args = parser.parse_args()

    output = args.output or args.input.with_name(f"{args.input.stem}_formatted.json")

    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        result = format_batch(
            raw,
            defaults=build_defaults(args, raw),
            seed=args.seed,
            keep_extra=args.keep_extra,
            derive_seeds=args.derive_seeds,
            warn=lambda msg: print(f"Warning: {msg}", file=sys.stderr),
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # ensure_ascii=False keeps Arabic text readable instead of \uXXXX escapes.
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(result['songs'])} songs to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
