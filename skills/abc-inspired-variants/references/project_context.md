# Project context: arabmaqamrock

Read this once at the start of a session. It exists so the user never has to re-explain the project.

## Contents
1. The project
2. What the ABC scores are (and are not)
3. How ABC edits reach real audio
4. What is already known (with confidence levels)
5. Reference tracks

## 1. The project

- Goal: improve a LoRA, `akbargherbal/arabmaqamrock-yue2-lora`, trained for the YuE music-generation model. Trigger word: `arabmaqamrock`. Intended sound: a grand, solemn symphonic-rock ballad driven by a commanding, deeply resonant Arabic male vocal delivering ornate, hymn-like melodies over heavy guitars and sweeping orchestral strings.
- Training data: 438 clips generated in Suno from one fixed prompt template (symphonic cinematic orchestral ballad, hymn-like concert-hall acoustics, heavy rock instrumentation, stately groove around 110 BPM, deep male Arabic vocals with melismatic phrasing, audiophile punchy centered mix; distorted electric guitars, orchestral strings, rock drums; an exclude list with oud, qanun, darbuka, female vocals, fast tempo and similar). Only the maqam name varied: Hijaz, Nahawand, Ajam, Kurd. The user rated the clips by ear over about a month: **177 got 5/5**, the rest 4/5.
- Current LoRA output quality: about 7/10 (pleasant, not memorable). Target: 9/10.
- Generation inputs look like: `lyrics` (with section tags such as `[Intro | single clean guitar | close-mic'd, plate reverb, short decay]`, `[Chorus | soaring hopeful vocals | full orchestral build and strings swell]`), `options.style` (e.g. "arabmaqamrock, classical arabic, symphonic metal, ..., Maqam Hijaz, mood: ..."), and a `seed`. The lyrics are classical Arabic poetry with full diacritics; each line is a long hemistich of roughly 14-16 syllables. Lines end with `...`.
- "Maqam" is used loosely: the user asked Suno for Hijaz/Nahawand/Ajam/Kurd but never verified Suno complied. Treat the names as style intentions. Rough Western analogues: Nahawand ~ minor, Ajam ~ major, Kurd ~ minor with a lowered 2nd degree, Hijaz ~ an augmented second between degrees 2 and 3.

## 2. What the ABC scores are (and are not)

- They are **automatic transcriptions** of finished audio: a lossy sketch. Pitches are snapped to 12 notes (quarter-tones and glides vanish), rhythm is quantized, and the program guesses key, meter and tempo. Seen guesses: `K:D#m` 2/4 at 73 bpm; `K:Gm` 2/4 at 89; `K:Dm` 4/4 at 122. Different guesses for the same words are normal.
- The `Vocal` voice is the sung line; the `Ins` voice holds only a little of the accompaniment (around 20-26% of the time has notes). Guitars, strings, drums, timbre, mix and vocal ornaments are not captured. `full_score` files add chord symbols above each bar.
- Timestamps computed from a score can drift a few seconds from the real audio (one fill was at 0:44 by ear and 0:50 in the score).
- The user previews with the abcjs editor (https://www.abcjs.net/abcjs-editor): paste, press play, generic synth sound. Judge notes, rhythm and placement only, not tone.

## 3. How ABC edits reach real audio

They do not, directly. There is no input path from ABC to Suno or YuE. The routes that do reach audio:
- **Lyrics section tags and the style string**: where to ask for a short guitar fill, where the refrain repeats, what each section's dynamics are. Not guaranteed to be obeyed; test, do not promise.
- **Seed**: same lyrics + style with different seeds gives different takes; choosing the best of N by ear is the most reliable improvement lever found so far.
- **Audio reference** (advanced): a rendered sketch could serve as a reference where the generator supports one; treat as inspiration, not a literal instruction.

## 4. What is already known

Confidence is stated per item. These came from comparing three transcribed tracks, with metrics chosen after seeing them, so treat them as hypotheses.

- (Medium) The sung line of all three tracks looks alike statistically: long phrases (about 16-22 notes), around 40% repeated-pitch notes (recitation-like, because classical hemistichs are long), very few repeated melodic phrases. So the sung melody alone did not separate memorable from forgettable.
- (Low-medium) The memorable track ("Baghdad Moon", the happy accident, rated high, about 3:35) had a **few short instrumental fills (5-8 notes) in the gaps after the first hemistich, with one recurring shape, irregularly spaced** (about 14 s apart at the start). A 7.5/10 take of the same words had ~16 fills, one after nearly every line, several spaced almost evenly at about 8 s, with about 12 different shapes, and felt monotonous ("رتيب") to him. A 7/10 Nahawand track ("Munajat") had almost no fills during the sung sections.
- (Low) In "Baghdad Moon" the opening couplet is heard four times (intro, verse 1, two choruses). In "Munajat" the chorus is a different couplet heard twice. Total length also differs (3:35 vs about 4:10 for the 7.5 take).
- (User's own insight, high) Memorability comes from a short, specific figure he can hum afterwards, not from overall polish. He remembers "Baghdad Moon's" fill after dozens of listens and cannot recite its words.
- (Low) A fill after *every* line at a metronomic spacing felt like a formula. One signature figure that returns with small variation at less predictable moments is the candidate principle to test.

## 5. Reference tracks (scores the user has shared)

- "Munajat Diyar al-Uns" (Nahawand): rated about 7/10, "not memorable". Transcribed `K:D#m`, 2/4, 73 bpm, ~3:38.
- "Baghdad Moon" accident (Hijaz): the happy accident. `K:Gm`, 2/4, 89 bpm, ~3:38 by score (3:35 real).
- "Baghdad Moon" second take: rated 7.5-8, monotonous. `K:Dm`, 4/4, 122 bpm, ~4:09.
