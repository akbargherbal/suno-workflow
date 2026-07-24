#!/usr/bin/env python3
"""
Maqam Prompt Generator (v2 — "Winning Template" edition)
----------------------------------------------------------
Locks in the exact prompt structure that won after 2.5 months of manual
trial-and-error (Suno v5, cinematic orchestral rock, Arabic male vocal).

Only the Maqam name changes between generations. Every other field stays
fixed on purpose: an LLM (Gemini) was previously asked to vary a `mood`
field per-maqam ("happy" for one, "sad" for another) and introduced
unwanted drift. That field has been removed entirely rather than fixed,
since it was never essential to the winning prompt.

Only the four widely-known maqams with clean genre/mood behavior are
offered: Hijaz, Nahawand, Ajam, Kurd. (Rast, Bayati, Sikah, Saba, etc.
rely on quarter-tone intervals with no faithful Western mapping and were
excluded from the original tool for the same reason.)
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
PRODUCTION = (
    "Audiophile recording, punchy centered mix, forward vocals pulling "
    "instrumentation down on sustained phrases then band re-enters between "
    "lines, bright presence, clean transients, large dynamic range, natural "
    "breath room between phrases."
)
INSTRUMENTATION = (
    "Distorted electric guitars, orchestral strings, weighted acoustic rock "
    "drums, tight rhythm section."
)
EXCLUDE = (
    "Oud, Qanun, Darbuka, Tabla, Ney, Buzuq, Sitar, Khaliji, female vocals, fast tempo, "
    "upbeat, speed metal, punk, muddy mix, muffled vocals, distant vocals, "
    "washed out, wall of sound, synth pads, extreme "
    "panning, autotune, vocal strain, growling, audience, applause"
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
    print(f"{C.BOLD}  MAQAM PROMPT GENERATOR{C.RESET}")
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
