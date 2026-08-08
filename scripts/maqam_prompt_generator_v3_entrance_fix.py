#!/usr/bin/env python3
"""
Maqam Prompt Generator (v3 — "Entrance Fix" edition)
----------------------------------------------------------
Based directly on the v2 "Winning Template" (9.5/10, ~3 months of manual
trial-and-error, Suno v5, cinematic orchestral rock, Arabic male vocal).
Only two fields were touched here — everything else is byte-identical
to v2.

WHAT CHANGED VS v2, AND WHY
----------------------------
Lab 04 (audio_bench analysis, 2026-07-27) compared two same-prompt/
same-seed-lineage takes (A vs B) of one generation. Whole-track averages
actually favored B (brighter, less low-mid energy), yet the human ear
consistently preferred A. Isolating the first ~2 seconds of the vocal's
entrance explained the mismatch: in B, the orchestral swell landed at
the *same instant* as the vocal's first note, nearly doubling both
low-mid ("boxy") energy and stereo width right on top of the voice. In
A, the swell had already resolved before the vocal started. The gap
collapsed within 2-3 seconds in both cases — this is a transient
arrangement-timing event, not a persistent mix problem.

Two small, targeted edits attempt to nudge future generations toward
A's behavior instead of leaving the swell/vocal timing to chance:

1. PRODUCTION — one short *positive* sentence added (state what should
   happen, not what shouldn't): the vocal enters solo/exposed as the
   swell resolves beneath it. (+64 chars)
2. EXCLUDE — one short phrase added, matching the terse style of the
   existing list: "vocal buried under swell". (+26 chars)

Nothing else was touched: GENRE, INSTRUMENTATION, MAQAMS, build_vocals,
the MAX-mode prefix, and all interactive/CLI logic are identical to v2.
This keeps the total prompt well under Suno's ~1000-char field limit
(previous draft of this fix ran ~165 extra chars and risked truncation;
this version adds ~90 chars total across both fields).

This is intentionally a single, isolated variable change so its effect
can be tested cleanly: generate a batch with this script, a batch with
the original v2 script, and compare vocal-entrance low-mid/stereo-width
deltas using audio_bench, the same way Lab 04 did for A vs B.
"""

import os
import sys

if sys.platform == "win32":
    os.system("")


class C:
    _enabled = sys.stdout.isatty()
    RESET = "\033[0m" if _enabled else ""
    BOLD = "\033[1m" if _enabled else ""
    DIM = "\033[2m" if _enabled else ""
    CYAN = "\033[36m" if _enabled else ""
    YELLOW = "\033[33m" if _enabled else ""
    GREEN = "\033[32m" if _enabled else ""
    MAGENTA = "\033[35m" if _enabled else ""


# Menu order matches how the maqams were requested: Hijaz, Nahawand, Ajam, Kurd
MAQAMS = {
    1: "Hijaz",
    2: "Nahawand",
    3: "Ajam",
    4: "Kurd",
}

# grand concert hall or epic stadium acoustics
# Fixed fields — identical across every maqam. Only "vocals" changes.
GENRE = (
    "Symphonic cinematic orchestral ballad, hymn-like grand concert hall acoustics, "
    "heavy rock instrumentation, stately groove, 110 BPM."
)

# CHANGED vs v2: one sentence added at the end (positive framing, +64 chars).
# Everything before it is identical to v2's PRODUCTION field.
PRODUCTION = (
    "Audiophile recording, punchy centered mix, forward vocals pulling "
    "instrumentation down on sustained phrases then band re-enters between "
    "lines, bright presence, clean transients, large dynamic range, natural "
    "breath room between phrases. Vocal enters solo and exposed as the "
    "swell resolves beneath it."
)

INSTRUMENTATION = (
    "Distorted electric guitars, orchestral strings, weighted acoustic rock "
    "drums, tight rhythm section."
)

# CHANGED vs v2: one short phrase appended, matching the existing terse
# style (no "no"/"never" wording, just a two-to-four-word tag like the
# rest of the list). Everything before it is identical to v2's EXCLUDE.
EXCLUDE = (
    "Oud, Qanun, Darbuka, Tabla, Ney, Buzuq, Sitar, Khaliji, female vocals, fast tempo, "
    "upbeat, speed metal, punk, muddy mix, muffled vocals, distant vocals, "
    "washed out, wall of sound, synth pads, extreme "
    "panning, autotune, vocal strain, growling, audience, applause, "
    "vocal buried under swell"
)


def build_prefix(start_phrase: str) -> str:
    """Fixed MAX-mode header + the user-supplied opening phrase/verse."""
    return (
        "[Is_MAX_MODE: MAX](MAX) [QUALITY: MAX](MAX) [REALISM: MAX](MAX)\n"
        "[START_ON: TRUE]\n"
        f'[START_ON: "{start_phrase}"]'
    )


RULE_WIDTH = 64


def rule(char="─", color=C.DIM):
    print(f"{color}{char * RULE_WIDTH}{C.RESET}")


def print_menu():
    print()
    rule("═", C.CYAN)
    print(f"{C.BOLD}  MAQAM PROMPT GENERATOR (v3 — entrance fix){C.RESET}")
    rule("═", C.CYAN)
    for num, name in MAQAMS.items():
        print(f"  {C.YELLOW}{num}.{C.RESET} {C.BOLD}Maqam {name}{C.RESET}")
    print()
    rule()


def get_choice():
    while True:
        raw = input(f"\n{C.CYAN}➤ Enter a number (1-{len(MAQAMS)}):{C.RESET} ").strip()
        if raw.isdigit() and int(raw) in MAQAMS:
            return int(raw)
        print(f"{C.MAGENTA}  Invalid choice, please try again.{C.RESET}")


def get_start_phrase():
    while True:
        raw = input(
            f"\n{C.CYAN}➤ Enter the phrase/verse to start on:{C.RESET} "
        ).strip()
        if raw:
            return raw
        print(f"{C.MAGENTA}  Phrase cannot be empty, please try again.{C.RESET}")


def get_mood():
    """Optional — blank/whitespace-only input means "no mood field"."""
    raw = input(
        f"\n{C.CYAN}➤ Enter a mood (optional, press Enter to skip):{C.RESET} "
    ).strip()
    return raw or None


def build_vocals(maqam_name: str) -> str:
    return (
        "Male deep baritone, mixed-voice chest-head resonance blend on "
        "sustained notes, breath-supported melismatic runs, controlled "
        "vibrato, full-voiced commanding presence, precise Arabic "
        f"diction, melismatic phrasing in Maqam {maqam_name} with unhurried "
        "phrase-ending sustains."
    )


def build_prompt(maqam_name: str, start_phrase: str, mood: str | None = None) -> str:
    """Returns the full markdown block: PREFIX + PROMPT (genre -> instrumentation [-> mood]) + EXCLUDE.

    `mood` is optional. If None, empty, or whitespace-only, the mood field
    is omitted entirely from the prompt block rather than emitted empty.
    """
    vocals = build_vocals(maqam_name)

    prompt_block = (
        f'genre: "{GENRE}"\n'
        f'vocals: "{vocals}"\n'
        f'production: "{PRODUCTION}"\n'
        f'instrumentation: "{INSTRUMENTATION}"'
    )

    if mood and mood.strip():
        prompt_block += f'\nmood: "{mood.strip()}"'

    prefix = build_prefix(start_phrase)

    return (
        "PROMPT:\n\n"
        "```\n"
        f"{prefix}\n\n{prompt_block}\n"
        "```\n\n"
        "EXCLUDE:\n\n"
        "```\n"
        f"{EXCLUDE}\n"
        "```"
    )


def generate_prompt(choice, start_phrase: str, mood: str | None = None) -> str:
    """
    Generate a prompt without the interactive menu.

    Parameters
    ----------
    choice : int | str
        Either a menu number (e.g. 2) or a maqam name (e.g. "Nahawand").
    start_phrase : str
        The phrase/verse the vocal should start on, e.g. "آذَنَتْنَا بِبَيْنِهَا".
    mood : str | None, optional
        Optional mood field appended to the end of the positive prompt.
        Omitted entirely if None, empty, or whitespace-only.

    Examples
    --------
    >>> generate_prompt(2, "آذَنَتْنَا بِبَيْنِهَا")
    >>> generate_prompt("Nahawand", "آذَنَتْنَا بِبَيْنِهَا")
    >>> generate_prompt("Nahawand", "آذَنَتْنَا بِبَيْنِهَا", mood="wistful, elegiac")
    """
    if not isinstance(start_phrase, str) or not start_phrase.strip():
        raise ValueError("start_phrase must be a non-empty string.")

    if mood is not None and not isinstance(mood, str):
        raise TypeError("mood must be a string or None.")

    if isinstance(choice, int):
        if choice not in MAQAMS:
            raise ValueError(f"Choice must be between 1 and {len(MAQAMS)}.")
        return build_prompt(MAQAMS[choice], start_phrase, mood)

    if isinstance(choice, str):
        choice_norm = choice.strip().lower()
        for name in MAQAMS.values():
            if name.lower() == choice_norm:
                return build_prompt(name, start_phrase, mood)
        valid = ", ".join(MAQAMS.values())
        raise ValueError(f"Unknown maqam '{choice}'. Valid maqams: {valid}")

    raise TypeError("choice must be an int or a str")


def main():
    print_menu()
    choice = get_choice()
    maqam_name = MAQAMS[choice]
    start_phrase = get_start_phrase()
    mood = get_mood()

    print()
    rule("═", C.GREEN)
    print(f"{C.GREEN}✔ Selected:{C.RESET} {C.BOLD}Maqam {maqam_name}{C.RESET}")
    print(f"{C.GREEN}✔ Start on:{C.RESET} {C.BOLD}{start_phrase}{C.RESET}")
    if mood:
        print(f"{C.GREEN}✔ Mood:{C.RESET}    {C.BOLD}{mood}{C.RESET}")
    rule("═", C.GREEN)
    print()
    print(build_prompt(maqam_name, start_phrase, mood))
    print()


if __name__ == "__main__":
    main()
