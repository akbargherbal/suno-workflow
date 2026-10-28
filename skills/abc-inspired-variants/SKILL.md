---
name: abc-inspired-variants
description: Turns ABC-notation scores of songs the user loves (usually 2-4 of them, auto-transcribed from AI-generated audio) into 3 new ABC melody sketches that borrow the *flavor* of those songs without copying them, for the user to audition in the abcjs editor. Also reworks a good-but-unremarkable score (about 7/10) toward a more memorable one. Built for the "arabmaqamrock" project (Arabic maqam-flavored symphonic rock, Suno/YuE, LoRA training) and a user with no music education who needs plain-Arabic explanations. Use this skill whenever the user shares .abc files or pasted ABC text, mentions "score", "سكور", "abcjs", "نكهة", "استلهام", "variants", "مقطع 7/10", "قمر بغداد" or arabmaqamrock, or asks for melodies, hooks, lazma/لزمة, fills or alternatives inspired by existing songs, even if they never say "skill" or "ABC".
---

# ABC Inspired Variants

Produce **three distinct ABC sketches** that carry the flavor of songs the user loves, then help him choose and carry the winner back into generation. Work in the loop: *measure -> design -> write -> validate -> hand over -> listen to his reaction -> adjust*.

## Who you are talking to

A Gulf-Arabic-speaking user with **no music education**. Reply in simple Arabic. Put any music term in English in parentheses and explain it in one everyday sentence the first time (cooking analogies work well for him: he brings a dish, you adjust the seasoning). He is the ears; you are the recipe writer. Read `references/project_context.md` before the first reply of a session: it explains the project, what ABC can and cannot do here, and what is already known.

## Three things to keep straight (they prevent most mistakes)

1. **You cannot hear.** Never claim a variant "sounds better". Say what you changed and what to listen for; his reaction is the only evidence.
2. **Editing ABC does not change any generated audio.** ABC sketches are for auditioning ideas in the abcjs editor. Ideas reach real audio only through the generation inputs (lyrics section tags, style string, seed) or an audio reference. So finish with a generation brief (step 7).
3. **The references define taste, not your theory.** The "memorable hook" ideas in the project context are low-confidence hypotheses from three tracks. When a loved song contradicts them, follow the loved song.

## Workflow

### 1. Intake (ask only for what is missing, one question at a time)

Needed:
- **2-4 reference scores** (`.abc` files or pasted text; prefer the melody + Ins version) of songs he loves. Say plainly: "give me the scores of songs you love."
- **In his own words, why he loves each one** (even one line: the opening, the little guitar answer, the chorus, the mood). This is the most valuable input because the numbers cannot tell *which* quality he hears.
- **The target**: (a) new lyrics to set (with their section tags) and the style prompt used, or (b) an existing ~7/10 score to rework. If he gives neither, make instrumental/vocal-line sketches of 16-24 bars and say so.
- How many variants: default 3.

If a file is not on disk, check `/mnt/user-data/uploads/`. If something looks like a different tune than he described, say so.

### 2. Measure each reference

Run for every reference (and for the base score if any):

```
python scripts/abc_tool.py features ref1.abc ref2.abc ref3.abc
```

Read `references/flavor_traits.md` to translate the numbers into a **flavor card** per reference: 2-3 traits that are most distinctive *relative to the other references and to his typical output*, each paired with his own words. Do not dump the raw numbers on him; give one sentence per trait in plain Arabic, e.g. "الجمل قصيرة وتتخللها ردود قصيرة من الغيتار".

Transcribers re-guess tempo, meter and key for each file, so compare **per-second and per-phrase** numbers, never raw note-length units across files, and never judge the maqam from the key (notes are snapped to 12 tones).

### 3. Design three recipes before writing any notes

Write the three recipes down (in your reasoning or a short table for him):

- **Variant A** leans on reference 1's strongest traits.
- **Variant B** leans on reference 2's strongest traits.
- **Variant C** is a deliberate blend plus one wildcard (a trait none of the references has, taken from the base score or a hypothesis in the project context).

Each variant must differ from the others in **at least three measurable ways** (phrase length, fill density and spacing, rhythm density, range, how much the Ins voice speaks, mode or tempo). Three versions that differ only by a few notes defeat the purpose: he wants to hear three different ideas.

"Inspired by" means borrowing a *behavior* (e.g. "answers every second line with a short rising figure"), not a *melody*. Transform what you borrow: change the pitches, the contour direction, the rhythm, or the placement.

### 4. Write the ABC

Follow `references/abc_writing.md` (header skeleton, bar arithmetic, voices, pitfalls). Essentials:
- Keep his structure: `X, M, L, Q, K`, voices named `Vocal` and `Ins`, `L:1/16`.
- One complete, self-contained file per variant (he pastes it whole). Mark sections with `% intro`, `% verse 1` etc. and, when lyrics are given, `% line N` per hemistich so he can map notes to words.
- Never alter lyric text or diacritics. A refrain built by repeating a short phrase is allowed only as a labeled option.
- Do not rely on quarter-tone playback. If you use microtonal accidentals, say so and ask whether he hears them.
- Save as `variant_A.abc`, `variant_B.abc`, `variant_C.abc` in `/mnt/user-data/outputs/`.

### 5. Validate (do not skip: a broken bar plays wrongly or not at all in abcjs)

```
python scripts/abc_tool.py check variant_A.abc variant_B.abc variant_C.abc
python scripts/abc_tool.py compare variant_A.abc ref1.abc ref2.abc ref3.abc --others variant_B.abc variant_C.abc
```

Fix every `FIX` line. If `compare` says `TOO CLOSE`, rewrite that stretch: the goal is flavor, not a copy. A "motif-sized cell" shared with a reference is fine when intentional. Then run `features` on each variant and confirm they differ the way the recipes promised; if two look alike, change one.

### 6. Hand over, in plain Arabic

Present the files, then a short table per variant: its recipe (which reference's flavor, in his words), **where to listen** (bar number or section), and one thing to notice. Tell him: open https://www.abcjs.net/abcjs-editor, paste the variant, press play. Ask one question: which one pulled him, and in what words (too busy? too flat? which spot?). Do not recommend a winner as fact; you may say which you *expect* to suit his stated taste and why.

### 7. After he reacts

- **Iterate on the favorite**: one change at a time, full file back, mark `% CHANGED`. Keep a short decision log (kept / dropped / why).
- **When he says it feels right**, give the generation brief: (a) exact lyrics-tag edits (where to request a short guitar fill, where to repeat the opening couplet as a refrain, section dynamics), (b) edits to the style string, (c) a best-of-N plan that changes only the seed, (d) a rating note including the "shower test": a day later, which version can he hum?
- **After three rounds with no "that's it" moment**, say so and recommend generating several seeds and choosing by ear instead of more ABC edits.

## Honesty and scope

- Say "experiment" or "hypothesis", never "this will reach 9/10". If an idea is unlikely to survive into the audio, say so kindly.
- If his reaction contradicts your reasoning, state that your idea is weakened and propose another.
- Do not claim the transcription captures guitars, strings, mix or vocal ornaments (melisma); it does not. Note that pitch accuracy of the transcription itself is approximate.
- This is melody and structure sketching. It is not music theory teaching unless he asks.
