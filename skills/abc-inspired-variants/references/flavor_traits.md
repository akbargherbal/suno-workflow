# Flavor traits: from numbers to plain Arabic to ABC

Use this to build the flavor card for each reference score (SKILL.md step 2) and to realize a trait in a new variant (step 4). The numbers come from `python scripts/abc_tool.py features file.abc`.

## Contents
1. Trait table
2. Picking the distinctive traits
3. Realizing each trait in ABC
4. Making a hook (hypotheses to test, not rules)
5. Translating for the user

## 1. Trait table

| Number from `features` | What it says | Plain-Arabic hint |
|---|---|---|
| `avg_notes_per_phrase`, `avg_phrase_sec` | long phrase = reads like recitation; short phrase = singable | "الجملة طويلة كأنها إلقاء" / "الجملة قصيرة وتُغنّى" |
| `repeated_pitch_pct` | share of notes that stay on the same pitch (recitation feel) | "اللحن يقف على نغمة واحدة كثيرًا" |
| `step_pct` / `leap_pct` | smooth stepwise motion vs jumps | "حركة هادئة متدرجة" / "قفزات" |
| `notes_per_sec_when_sounding`, `median_note_sec` | rhythmic busyness. Comparable across files, unlike raw note units | "إيقاع كثيف" / "نغمات ممتدة" |
| `sounding_pct` (Vocal) | how much silence the singer leaves | "مساحات صمت" |
| `range_semitones` | how high/low the line travels (12 = one octave) | "مدى واسع" |
| `degrees_pct` | which notes of the scale are the home notes; "1" is home, "5" the dominant, "b2" a lowered second (Kurd/Hijaz color), "b6"/"b7" minor color | "النغمة التي يدور حولها اللحن" |
| `similar_phrase_pairs` | how many phrase pairs are 70%+ alike (melodic repetition) | "جمل تتكرر" |
| `most_repeated_5_interval_pattern` | the most repeated 5-move pattern (often five equal notes = recitation) | |
| `short_groups`, `short_group_gap_sec` | short answers (<= 9 notes) after a gap: instrumental fills or sung tags, with their time stamps and spacing | "ردود قصيرة من الغيتار" |
| `longest_evenly_spaced_run_of_fills` | how many fills in a row are spaced almost equally (+-25%). High = mechanical | "تأتي كالساعة" |
| `distinct_short_shapes` | how many different fill shapes exist. 1-3 = a signature; 10+ = many unrelated tags | |
| `length_sec` | song length | |
| Ins `sounding_pct` | how much the accompaniment line speaks at all | |

Caveats: the transcriber guesses tempo and meter each time, so use per-second and per-phrase numbers; the key signature says nothing reliable about the maqam; Ins coverage is partial, so a missing fill may just be a transcription miss.

## 2. Picking the distinctive traits

For each reference, compare its numbers with the other references (and with the base score if there is one). The two or three traits that stand out most are its flavor. Then pair them with what the user said he loves about it: if he says "the little guitar answer", the fill traits win even if phrase length also stands out. If the numbers show nothing special, say so and rely on his words.

## 3. Realizing each trait in ABC

- **Short singable phrases**: break a long hemistich into two sung chunks with a one-beat rest between them (`z4` at `L:1/16` is one quarter-note beat). Keep about 8-12 notes per chunk.
- **Less recitation**: replace runs of equal notes with a small turn (neighbor note up and back) or let the last syllable of the phrase leap a third or a fourth, then fall.
- **Fills in the gaps**: put 5-8 notes in the `Ins` voice during the rest the Vocal leaves after a hemistich. Give the fill one clear shape (e.g. up two steps, down, settle) and let it return later transposed or with a changed ending.
- **Irregular spacing**: do not place a fill after every line. For example after line 1, skip line 2, answer after line 3 and 4, then wait longer before the chorus. Avoid equal gaps for more than two fills in a row.
- **Rhythmic contrast**: mix a few long notes (`4`, `6`) with runs of short ones (`1`, `2`). A phrase made only of equal short notes is flat.
- **Mode color**: to get a darker "minor" feel use the lowered 3rd, 6th, 7th of the key; to get Hijaz-like color write the augmented second (for example in D: Eb then F#) and say it is an approximation because playback is 12-tone. Do not claim it is a faithful maqam.
- **Refrain**: reuse the opening melody for the chorus line so the same couplet is heard repeatedly. Flag it as a structural option (lyrics unchanged).
- **Range and contour**: climb through the verse to a high point in the chorus (e.g. chorus starts a fourth above verse), return low in the outro.
- **Silence**: leave one or two beats before the last word of a line for the instrument to answer.

## 4. Making a hook (hypotheses to test, not rules)

From the project's three tracks (see `project_context.md`, section 4): a short figure of 4-8 notes with a distinctive rhythm; placed in the silence after a sung line; recurring with small variation at less predictable intervals; present early (first minute) so the ear can latch on. Offer these as experiments. If the user reacts against one, drop it.

## 5. Translating for the user

- One sentence per trait, in plain Arabic, with a concrete picture ("الغيتار يرد على الصوت بعد كل بيت").
- Always tie a trait to his own words about the song when he gave any.
- Explain a term once and then reuse it: `phrase` = جملة، `fill` = لزمة قصيرة تملأ الفراغ، `hook` = اللزمة التي تلتصق بالذاكرة، `bar` = مقطع زمني قصير يفصله خط عمودي.
