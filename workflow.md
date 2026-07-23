# WORKFLOW.md — Long Classical Arabic Poems → Suno Fusion Songs

A general, reusable process for turning any long classical Arabic poem (qasida, mu'allaqa, etc.) into a coherent multi-part Suno production. This consolidates the full method developed across the Nabigha and al-Harith projects — apply it to any new poem from scratch.

---

> **⚠️ Note to the model — this file is background, not a binding text:**
> This file documents the user's *prior* methodology so any new session gets quick context — it is not a fixed, final set of rules. The user has noticed more than once that I stick to this file's content literally even when they give direct instructions in the same conversation that contradict it, and that's wrong.
> **The rule:** if the user's live instructions in the current conversation conflict with a point in this file:
> 1. Flag it explicitly — cite the conflicting section exactly (its number/heading and its wording or an accurate summary).
> 2. Ask: would they rather update the file first so it stays consistent with the new decision, or apply the new instructions this one time without editing the file?
> 3. Don't silently defer to this file's content over the user's live instructions — especially on tagging, which the user has stated is still an active, ongoing experiment.

---

## Phase 0 — Source the Text

Before anything else, get the poem in a form you can trust.

1. **Get the full text, fully diacritized (mushakkal)** — every verse needs complete tashkeel (i'rab endings included), not partial vocalization. Suno's pronunciation depends entirely on this; missing or wrong diacritics is the single biggest cause of mispronunciation, more than any prompt trick can fix.
2. **Cross-check against at least two reputable sources** (e.g. a critical print edition, a trusted literary database) — classical poems often have scribal variants in word choice or even verse order. Pick one authoritative version and stick to it for the whole project.
3. **Verify verse count and order** before splitting into sections — some poems have disputed or additional verses in different manuscripts (mansub/mukhtalaf fih verses). Decide up front which version you're using.
4. **Store the poem as structured data** (like the `poem_list` tuple format used for the Nabigha project) — one (sadr, ajuz) pair per verse, indexed from 1. This makes it trivial to slice into sections later.
5. **The creative target is a fixed pairing, not something to redescribe per project.** A Western musical genre (currently symphonic rock/orchestral) carries a deep, melismatic, classically-articulated Fus'ha vocal — the Arabic identity comes from the voice, not from the instrumentation, and the genre choice itself is deliberately guarded against drifting back toward the Gravitational Well (see Glitches section below). The specifics (which genre, which instruments excluded) live in a generator script and can change; this underlying pairing is the constant to point new sessions to, rather than re-describing the style fresh each time.

---

## Output Schema — Section JSON

Every project's lyrics deliverable is a single JSON file, one object per section, following this shape. Generate against this directly rather than re-deriving it each project — it's the contract Phase 1's section map and Phase 5's lyrics box both feed into.

```json
{
  "sections": [
    {
      "section_id": 1,
      "maqam": "Hijaz",
      "title": "الوداع والخطوات الوادعة",
      "lyrics": "///***///\n[Intro | single clean guitar | close-mic'd, plate reverb, short decay]\n...",
      "mood": "melancholic, longing, nostalgic"
    }
  ]
}
```

- `section_id`: 1-indexed, in poem order.
- `maqam`: from the fixed set only — Hijaz, Nahawand, Ajam, Kurd (Phase 2).
- `title`: Arabic section title, from the Phase 1 section map.
- `lyrics`: the full lyrics-box content as a single string, per the Phase 5 template.
- `mood`: English only, comma-separated, max 3 tags — matches Phase 1 point 4's section-map column.

---

## Phase 1 — Thematic Segmentation

Don't chunk by fixed verse count. Chunk by theme, and let verse count follow.

1. **Identify the poem's classical structure first**: most qasidas move through recognizable movements — nasib/atlal (ruins, longing), rahil/tardiyya (journey, hunt, camel or horse description), madih (praise), fakhr (boasting), i'tidhar (apology), hija' (satire), or a closing simile/summary. Not every poem has all of these, and the order can vary — read the whole poem first before deciding.
2. **Find the pivot verses (takhallus)** — the lines where the poet visibly shifts subject (e.g. "so leave what you see, since there's no going back to it" type transitions). These are your section boundaries, not arbitrary verse-count cutoffs.
3. **Target 8–12 verses per section as a soft guideline** (roughly 3–4 minutes of sung material — verse count is a proxy for that duration, not the goal itself), not a rule. A thematically tight unit that's 5 or 6 verses is fine — better to respect a natural boundary than pad a section that doesn't need it. A single continuous narrative (like a hunt scene) can run to 11–13 if splitting it would break the story.
4. **Write the section map as a table**: section name, verse range, verse count, mood tags (English, max 3 words — this is what lands directly in the output JSON's `mood` field, so write it in its final form here rather than translating/trimming it later). Keep this table at the top of your project notes — it's the reference point for every phase after this.
5. **Checkpoint before lyrics engineering.** Once the section map and maqam assignments (this phase + Phase 2) are drafted, present them back as a short brief with 2–3 targeted approval questions (division count, any section you're unsure about, genre framing) before starting Phase 5. Cheaper to fix a section boundary or maqam call here than after lyrics are written.

---

## Phase 2 — Assign a Maqam per Section

1. **Choose from a fixed set of four maqams only: Hijaz, Nahawand, Ajam, Kurd.** Read each section's mood off your Phase 1 table (mournful, tense, ceremonial, narrative, solemn, triumphant, etc.) and match it to whichever of these four best fits the section's theme and emotional character — don't reach for a maqam outside this set.

   | المزاج / الطابع | المقام المناسب |
   |---|---|
   | حنين، شوق، لوعة عاطفية | الحجاز |
   | رثاء، حزن عميق، فراق | الحجاز |
   | حزن هادئ، أسى، حنين ناعم | نهاوند |
   | سرد هادئ، وصف، حوار داخلي | نهاوند |
   | فخر، حماسة، انتصار | العجم |
   | مديح، احتفال، بشرى | العجم |
   | توتر، ترقب، إنذار | الكرد |
   | غموض، رهبة، جدّية/رسمية | الكرد |
2. **One maqam per section** — don't split a section's maqam mid-way; if a section genuinely needs two moods, that's a sign it should probably be two sections (back to Phase 1).
3. Look for a deliberate **arc across the whole poem** — reusing a maqam for sections that share emotional DNA (e.g. the opening lament and the closing personal appeal) creates a musical rhyme scheme across the whole piece, not just the poetic one. Reserve any maqam with a very distinct color for the one moment that's genuinely unique, so it doesn't lose its impact through repetition.

---

## Phase 3 — Buffer Verses & Padding

1. **Buffer verses**: within each section's own generation, echo its own first verse softly at the very start (this doubles as the vocal-clarity intro technique in Phase 5) and repeat its own last verse softly at the end. This gives you literal audio material to trim and crossfade against in Audacity later, rather than needing a hard cut on unique content.
2. **Balance short sections against your longest section** (don't touch the longest — it's the baseline). For anything noticeably shorter:
   - Turn the section's own strongest or most iconic line into a repeated chorus/refrain (2x) — pull from material already inside the section, don't write new lyrics.
   - Add short instrumental interludes (a few bars, no new lyrics) before/after a chorus repeat.
   - For sections close to the baseline already, a small instrumental tension-build near the climax is enough — no lyrical repeat needed.
3. Do the padding pass only after the base section's pacing and vocal performance are confirmed — pad structure and lyrics, not generation settings.

---

## Phase 4 — Lock the Voice and Settings

1. From your best early draft (a fast/cheap model tier is fine here), create a **Voice** (locks singer identity precisely) rather than only a general Style Persona — you want the same reciter across all sections, not just a similar vibe.
2. **Lock Style Influence and Weirdness (or equivalent sliders) at fixed values once, and never change them for the rest of the project.** Only the maqam selection and lyrics content should vary between sections.

   **Nabigha project — locked values (as of the v4/v5 session):** Weirdness **20%**, Style Influence **70%**. These replace an earlier default (50%/50%) that was never consciously set — the project had drifted along on Suno's defaults rather than a deliberate lock. Weirdness controls how far Suno explores away from the expected/conventional result (higher = more unexpected elements — extra voices, odd instrumentation, surprising transitions); Style Influence controls how literally Suno treats the style/exclude prompt (higher = treats it as a harder constraint rather than a loose suggestion). Do not change either value without a documented reason and a listening-test comparison.
3. If you're chasing higher fidelity from a newer model tier on top of an early draft: try **direct generation guided by the locked Voice** rather than a Cover/re-render pass — Cover tends to "reinterpret" and speed up performances, while a fresh generation guided by a voice reference is more likely to preserve original pacing.
4. Generate a short test clip (30–60 seconds) per section before committing to a full render, checking specifically for: vocal pacing/stretch, correct pronunciation of the phonetic spelling, and whether the target maqam actually came through.

---

## Phase 5 — Lyrics Box Engineering

Applies per section, inside the lyrics box only (style/genre/production prompt stays separate and is a one-time decision, not something you re-derive per section):

1. **Mark the boundary**: put `///***///` as the very first line of the lyrics box, so it's visually clear where the style/genre prompt ends and the lyrics begin.
2. **Open with a mic-placement intro — and use it as the section's anchor tag**: `[Intro | single clean instrument | close-mic'd, plate reverb, short decay]`, followed *directly* by the section's first line — no soft hum, no whispered pre-echo. Use the *same* instrument for this across every section — it becomes a consistent sonic signature tying all sections together regardless of maqam or mood.

   **Why this specific tag matters more than any other tag in the section:** it's the first thing Suno reads in the lyrics box, so it acts as an anchor/pivot that sets the interpretive frame for everything that follows — get this one tag right and the rest of the section tends to follow its lead; get it wrong and no amount of tagging later recovers it.

   **Name the specific technique, not a general adjective.** A generic word like "reverb" or a performance adjective like "commanding" carries whatever association is *most common* for that word in Suno's training data — usually the generic/mainstream one, which is exactly what you're trying to avoid. A precise technical term (`plate reverb, short decay`, `close-mic'd`) narrows the space Suno is drawing from and is far less likely to default toward a cavernous, over-sung, or genre-generic result than a vague descriptor pointing at the same idea. This replaced an earlier version of this rule that used "crystal clarity with subtle hall reflections" — that phrasing worked but was still an adjective-based description; the mic-technique framing is more precise and grounded.

   **Don't put a vocal-quality word in the Intro tag.** It's tempting to add one (`vocals commanding`, etc.) to make the entrance feel stronger, but the Intro tag's job is instrument + space only — a floating vocal descriptor here breaks the section's own `[Section | vocal quality | instrumentation]` schema (see point 3) and, worse, duplicates work the Verse tag right after it is already doing. Let the confidence of the entrance come from *removing the hum*, not from adding an adjective.
3. **Keep every tag inside a single 3-part schema, and keep it to a phrase, not a sentence.** `[Verse]`/`[Chorus]`/`[Bridge]`/`[Intro]` headers all follow `[Section | vocal quality | instrumentation]` — vocal quality goes in slot 2 even for the Intro tag's neighbors, never folded into slot 3 alongside the instruments. And every tag, header or mid-verse, should read like a keyword a model pattern-matches against — 2–5 words, one clause, no reasoning or exceptions embedded in it. If you find yourself stacking a cause, an exception, and a result into one tag (`X, but only if Y, then Z`), that's a sign you're trying to explain your intent rather than just stating it — split it or cut it down to the one word actually doing the work, don't write more.
4. **Set each section's vocal-quality descriptor once, as an anchor, and don't repeat or intensify it later in the same section.** A tag like `forward clear vocals` at `[Verse 1]` establishes the level for the rest of the section — Suno holds it without further prompting. Re-stating it with a reinforcing word (`vocals *still* forward`, `vocals *still* cutting through`) is read as a *new, additional* instruction to push further in that direction, not as "keep doing what you were already doing" — and across several such re-statements in one section, this compounds into an over-driven, shouty mic level by the section's later verses/chorus. If a later part of the section genuinely needs a *different* vocal quality (`vocals softening`, `vocals triumphant`), that's a real mood change and should be tagged — just don't use a continuity word ("still," "remains," "keeps") to describe an unchanged state; leave it untagged and let the anchor hold.
5. **Instrument tags at dramatic beats only, not after every hemistich**: don't insert a tag after each sadr and ajuz by default — that over-constrains Suno and it starts to "fight" the tag placement instead of breathing naturally. Reserve instrument tags (`[strings swell]`, `[guitar chord]`, etc.) for the section's actual pivot points: its climax, a turn in meaning, a build into a chorus/refrain, or a transition into/out of a bridge. As a rough guide, 2–3 tags placed deliberately per section is usually enough — let Suno fill in everything else on its own. Pull only from the instrument palette already defined in your genre/instrumentation prompt; never introduce an instrument in the lyrics box that isn't in your style prompt or that's on your Exclude list, it just confuses the model. Vary the specific tags by section mood (soft/sparse for elegy, sharp/urgent for action, grand for praise, restrained for solemn moments) — but sparingly, at the moments that actually earn it.

   **Never use percussive-hit vocabulary in an instrument tag, even if you never name drums.** Words like `hit`, `crash`, `slam`, `smash` carry a strong drum-kit association in Suno's training data on their own — a tag like `[guitars and strings hit together]` can still summon a drum crash underneath it, purely from the verb, with no percussion instrument named anywhere in the tag. Use sustain/build vocabulary instead: `swell`, `surge`, `build`, `rise`, `resolve`. This is a real, confirmed mechanism, not a precaution — see the Glitches section below.

   **At each section's main pivot tag (the one dramatic-beat tag doing the heaviest lifting), name that section's maqam directly inside the tag** — e.g. `[guitars & strings swell — Nahawand]`. This is a confirmed, tested technique for keeping the vocal performance anchored to the maqam's character at exactly the moment (a big instrumental swell) where Suno is most likely to drift toward a generic Western arrangement — see "Suno Gravitational Well" in the Glitches section below. Reserve this for the one or two tags per section that are genuinely load-bearing; don't scatter the maqam name across every minor instrument cue, that dilutes it back into noise.

   **Vocal tags are the one exception to "sparingly" — keep these dense and non-negotiable, but anchor rather than repeat (see point 4).** Every `[Verse]`/`[Chorus]`/`[Bridge]` header keeps its vocal-quality descriptor, and vocal centrality/clarity phrasing is never thinned out the way instrument tags are. The instrument-tag reduction above applies only to instrumentation cues sitting between hemistichs — not to vocal delivery tags.
6. **Tag density calibration — avoid over-correction.** After a full pass of a poem, a common failure mode is over-tagging: so many instrument/mood cues packed into the lyrics box that the listener feels the arrangement is cluttered or fidgety rather than breathing naturally, even when each individual tag follows every rule above. If this happens, split every tag into one of two buckets and cut hard on the second:
   - **Functional (never touch):** the Intro tag, each section's vocal-quality anchor (point 4), the Outro buffer, and any tag that IS a structural padding mechanism from Phase 3 (e.g. an instrumental interlude, or a refrain's explicit instrumentation drop-out).
   - **Decorative (cut ruthlessly):** any instrument tag mid-verse that just restates in different words what the section header already said, any adjective added to a `[Chorus]` tag beyond the bare label, and — see the "Gravitational Well" glitch note below for the maqam-naming exception — any tag that exists purely to add color rather than to mark an actual pivot.
   - Target **one instrument tag per genuine dramatic beat, not per verse and never per hemistich** — a section with two real turning points (e.g. a mythic-scale entrance, then a resolution before the outro) can justify two tags; most sections justify exactly one, or none beyond the header itself.
7. **Melismatic stretch marks**: append `...` to the end of every ajuz's rhyme word (and 1–2 extra climactic lines per section) to force the AI to hold and stretch the vowel instead of rushing to the next line. This is what preserves the long, breathing vocal delivery.
8. **Buffer-in/buffer-out**: as set up in Phase 3, open with a soft echo of verse 1 and close with a soft, fading repeat of the section's last verse. Note that with the hum removed from the Intro (point 2 above), the buffer-in is now the repeated first couplet across `[Intro]` and `[Verse 1]` rather than a whispered pre-echo — it still gives you two takes of the same line to trim/crossfade against in Phase 7, just delivered at full confidence both times instead of soft-then-strong.
9. Insert any Phase 3 chorus/refrain/instrumental padding directly into this same structure — it's not a separate note, it's part of the lyrics box content itself.

---

## Phase 6 — Generate, Section by Section

1. Same locked Voice + locked sliders every time (Phase 4). Only the maqam and the lyrics content change.
2. Test clip first, full section second, as in Phase 4.
3. Target a solid take (7/10+) before moving to the next section — don't chase a perfect take on every single section on the first pass; you can revisit later.
4. **Log every kept take**: section name, take number, maqam used, and settings — so a later re-take is reproducible instead of guesswork.
5. If a specific passage rushes, drifts, or contains a mispronounced/wrong word despite everything else being right, don't jump straight to regenerating or Cover-ing the whole section — see Phase 6.5 for the ordered set of narrower fixes to try first.

---

## Phase 6.5 — Post-Generation Lyric-Error Fixes

A common failure mode: a section renders beautifully overall, but one word is wrong (e.g. a tanwin case-ending sung with the wrong vowel). The goal here is to fix only the broken word/line while keeping everything else — voice, groove, arrangement — as close as possible to the approved take. Research-sourced options below, ordered from most surgical to most invasive; try them in this order rather than jumping straight to a full regeneration or Cover.

1. **Sample (Beta), if available on your Suno tier** — samples just the problematic phrase and regenerates it with corrected lyrics, without touching the rest of the section. Try this first: it's the narrowest possible intervention.
2. **Replace Section (built-in editor)** — select the offending span in the waveform and rewrite the lyrics for that span only; Suno regenerates just that segment while preserving melody, voice, and arrangement elsewhere. Minimum selectable span is ~10 seconds, so single-word selection isn't possible — select the whole line or hemistich around the error, not just the word.
   - **Don't edit only the broken word in isolation.** Community testing consistently shows this destabilizes the vocal take. Replace the full verse/chorus containing the error instead — this gives the model enough surrounding context to sing the corrected word correctly, at the cost of re-rendering a bit more material than strictly necessary.
   - Keep every tag identical to the original generation (mood, vocal-quality, instrument tags per Phase 5) and reuse the same Voice/Persona (Phase 4) — a mismatch here is the most common cause of the replaced section not matching the rest.
3. **Cover mode + high Audio Influence** (the method already in use) — load the approved take as a Cover source, type the corrected lyrics, and in Advanced settings push **Audio Influence to ~90–100** while keeping **Weirdness low**, so Suno follows the reference audio closely instead of reinterpreting it. This tends to preserve voice character and groove while fixing the mispronunciation, but is a heavier-handed pass than Replace Section since it re-renders the whole take.
4. **Persona-locked regeneration** — if Cover alone drifts the voice too far, first create a **Persona** from the approved take (saves the vocal identity specifically, separate from the general Voice lock in Phase 4), then regenerate with the corrected lyrics **using that same Persona explicitly selected**. Reusing the exact Persona is what keeps the voice identity stable across the fix — skipping this step is a known cause of the corrected take not matching the original vocal character.
5. **Remaster** — this upgrades audio quality/clarity on older-model takes; it is not a lyric-correction tool. Use it only if the actual problem is that the word is *unclear/muddy* rather than *wrong* — those are different failure modes needing different fixes (see the pronunciation-glitch entries above for what counts as "wrong").
6. **Human re-recording (paid third-party service, last resort)** — for a final, publish-critical take where AI regeneration keeps failing, some services re-record just the broken line with a real singer and blend it in with AI voice-matching plus manual audio engineering. Reserve this for a finished project's last mile, not for iteration.

**Verification status: unconfirmed, not yet tested on this project.** All of the above is compiled from current Suno documentation/community sources, not from a listening test on our own poems. Before promoting any of these from "option" to "confirmed step," run a controlled test on one known mispronunciation (e.g. a tanwin case-ending error) using options 1–2 first, and log which one actually fixed it without audibly changing the voice or groove — same discipline as the Glitches section below.

---

## Phase 7 — Assembly (Audacity)

1. Export every section's audio.
2. Import in verse order.
3. Trim into the buffer-verse repeats from Phase 3/5 at each boundary, and crossfade there — the buffers exist specifically to give you clean material to cut into instead of cutting into unique content.
4. Do one full front-to-back listen. Flag any section where the vocal identity or pacing noticeably drifts from its neighbors, and regenerate just that one (same locked Voice/settings) rather than redoing multiple sections.
5. Export the final track.

---

## Workarounds / Known Suno Glitches (temporary fixes)

This section collects known pronunciation or rendering glitches in Suno and the workaround currently in use for each. **These are stopgaps, not permanent orthography rules** — revisit each one periodically and drop it once the underlying model improves.

### Suno "Gravitational Well" — genre/vocal drift toward generic Western pop-rock

**The glitch:** even with a fully-diacritized Arabic text, a correct maqam assignment, and an explicit style prompt, Suno can still drift the vocal performance toward a generic, Western-sounding delivery mid-section — audibly, a listener can tell "this sounds like a Western singer decided to sing in Arabic" even though the pronunciation itself is technically fine. This is a known, documented Suno behavior (sometimes called a "gravity well" in the wider Suno-prompting community): the model's training data is heavily weighted toward mainstream pop/rock, and it exerts a pull back toward that default whenever the prompt doesn't actively resist it — especially at points where the arrangement gets denser or more "produced."

**Confirmed contributing cause — removing drum cue tags without replacing what they were doing.** An earlier pass of this poem's tags removed all drum-named instrument cues (`[drum fill, urgent]`, `[drum roll, resolving]`, `[deep drum hit]`) for an unrelated reason (see below), replacing them with guitar-only call-and-response tags. This made the drift *worse*, not better — the original drum+maqam combination had been an unusual/rare pairing in Suno's training distribution, and that rarity was itself part of what kept the model in unfamiliar (i.e. genuinely Arabic/maqam-flavored) territory. The plain guitar call-and-response phrasing that replaced it is common, idiomatic Western rock vocabulary — a *more* mainstream pairing, not a neutral one — and the drift reappeared.

**The workaround:** name the section's maqam directly inside its main pivot instrument tag, e.g. `[guitars & strings swell — Nahawand]`. Pairing a named maqam with a Western instrument (distorted guitar, etc.) inside the same tag is itself an unusual/rare combination by Suno's standards, which appears to reproduce the same "escape the well" effect the original drum pairing had — but tied to modal identity instead of an instrument we were trying to phase out anyway. **Verification status: confirmed by listening test** (Section 1, tested with and without the maqam-naming fix) — the drift was audibly gone with the fix applied. Applied across all six sections' main pivot tags in v2 of this pass.

**Status update (v3, active experiment):** in the v3 tag-density pass, the maqam name was removed from every mid-lyrics instrument tag project-wide, relying only on the maqam name already present in the `vocals:` field of the style prompt. This was a deliberate trade against tag-clutter (see point 6 in Phase 5), not a reversal of the confirmed test above — the risk is real and not yet re-verified without the fix. Community-documented Suno behavior suggests maqams closer to a Western minor scale (Nahawand, used here in Sections 1 and 5) are inherently more prone to drifting toward generic Western rock than maqams with a more distinct, less Western-adjacent color (Hijaz, Ajam) — so if drift reappears, it's most likely to show up there first. **Watch Sections 1 and 5 specifically on the next listening pass; if drift is audible, restore the maqam name to those two sections' pivot tags only, not project-wide.**

### Percussive-verb instrument tags summon drums even when drums aren't named

**The glitch:** an instrument tag using a percussive-hit verb — `hit`, `crash`, `slam`, `smash` — can cause Suno to bring in a drum hit underneath it, even when the tag names only non-percussion instruments (e.g. `[distorted guitars and strings hit together]`) and drums appear nowhere in the tag. The verb itself carries a strong drum-kit association in the training data, independent of which instruments are actually named.

**The workaround:** never use `hit`/`crash`/`slam`/`smash` in an instrument tag. Use sustain/build vocabulary instead — `swell`, `surge`, `build`, `rise`, `resolve`. This is separate from and in addition to simply not naming drums directly; both the noun (drums) and certain verbs need to be avoided for a tag to reliably stay percussion-free.

**Verification status: partially confirmed.** The connection between "hit"-style verbs and drum bleed-through is inferred from the broader gravity-well pattern and applied preventively across all remaining instrument tags in the project; it has not yet been isolated and confirmed in a dedicated A/B listening test the way the maqam-naming fix was. Spot-check on the next generation pass and downgrade this from "workaround" to "confirmed rule" (or revise it) once verified.

### Repeated/escalating vocal-quality tags read as new commands, not continuity

**The glitch:** re-stating a section's vocal-quality descriptor later in the same section with a reinforcing word — `vocals *still* forward`, `vocals *still* cutting through` — is read by Suno as an *additional, independent* instruction to push further in that direction, not as "maintain the level already established." Across a section with several such re-statements, this compounds into a progressively over-driven, over-loud vocal/mic level by the section's later verses or chorus — audible as the mic feeling "too hot" specifically near the end of a section, without any explicit request for that.

**The workaround:** set each section's vocal-quality descriptor once, at its first appearance (typically `[Verse 1]`), and let it stand as an anchor for the rest of the section — don't repeat it, even in a nominally softer form ("still," "remains," "keeps"). If the section has a genuine mood shift later on, tag that as a distinct new descriptor (`vocals softening`, `vocals triumphant`) rather than a continuity restatement of the first one. Never explicitly ask Suno to "lower" or "reduce" vocal level either — that's itself a new instruction and tends to produce unpredictable results; removing the reinforcing restatement and trusting the original anchor is the safer fix.

**Verification status: confirmed by listening test** (Section 1, Verse 2 → Chorus drift with `vocals still forward` present vs. removed).

### Directional/intensity adjectives in instrument tag headers over-choreograph the result

**The glitch (user observation, v4, not yet confirmed by a dedicated listening test):** the same escalation mechanism documented above for repeated vocal-quality tags appears to also apply to intensity/directional words placed inside a *section header* itself — `[Verse 2 | vocals commanding | instrumentation intensifying]`, `[Bridge | vocals softening | instrumentation pulling back]`, `[Verse 2 | instrumentation swelling slightly]`. Suno appears to read these not as a description of the intended mood but as an active instruction to push in that direction, producing an over-driven vocal and/or a busier, louder instrumental arrangement than intended — the musical equivalent of over-specifying a task (naming the exact route and speed) instead of giving a general instruction and trusting the model to fill in the details ("go to the store and pick up groceries").

**The workaround (v4):** strip intensity/directional adjectives out of section headers entirely.
- **Vocals:** state the vocal-quality descriptor once per section (typically `[Verse 1]`, per the existing anchor rule above). Don't add a new vocal adjective at a later header unless it's a genuinely distinct mood shift, and even then use a single plain word, never a continuity/escalation word ("still", "further", "more").
- **Instrumentation:** remove intensity/direction words from the header (`intensifying`, `pulling back`, `slightly`, `commanding` when applied to instruments) altogether. If the section has a genuine pivot moment, describe it with a single plain instrument tag placed *mid-line, at the actual beat* (`[strings swell]`, `[distorted guitar stab]`) — not as an adjective in the section header. Let the header stay bare (`[Verse 2]`, `[Bridge]`) and let the lyric content and the one mid-line tag carry the mood; trust Suno to "rise to the occasion" rather than choreographing every beat.

**Verification status: unconfirmed, applied preventively project-wide.** This extends the confirmed "escalating vocal tags" mechanism above by analogy; it hasn't been isolated in its own A/B listening test yet. Spot-check on the next generation pass — if sections built this way come back well-paced and not over-driven, promote this from "workaround" to "confirmed rule."

**The glitch:** when a word begins with the root letter ل and takes the definite article (e.g. الليل, اللعن, اللبد), Arabic assimilates the article's lam into the following lam, producing a single geminated/doubled lam sound (shadda). Suno sometimes mispronounces this doubled lam — especially over Western genres/instrumentation — rendering it closer to an American English "L" sound instead of the correct Arabic geminated lam.

**Important — narrow scope:** this workaround applies *only* to the specific case of "ال" (definite article) assimilating into a root-initial ل. It does **not** apply to:
- Other words that merely start with the letter ل without the definite article attached.
- The irregular relative pronouns الذي / التي / الذين, etc. — even though these carry a shadda on the lam by convention, they are a different phonetic case and are not currently known to trigger this specific glitch. Don't apply this fix to them without separately confirming they're affected.

**The workaround:** rewrite the affected word using Quranic (Uthmani-style) orthography instead of standard modern spelling:
- Replace the alef of "ال" with alef wasla (`ٱ`, U+0671).
- Drop the redundant duplicate lam letter — standard spelling writes the article's lam and the root's lam as two separate ل letters plus a shadda; Uthmani style writes only one ل carrying the shadda, since the shadda already encodes the doubling.
- If there's an internal sukun on the syllable between the doubled lam and the final letter (e.g. a long vowel glide), use the small Quranic sukun mark (`ۡ`, U+06E1) instead of the standard sukun (`ْ`, U+0652).
- Keep the word's actual grammatical case ending (i'rab) exactly as it was — don't drop or alter it; this is a pronunciation fix for the lam only, not a resyllabification of the whole word.

Examples: `الليل` → `ٱلَّيۡل`, `اللعن` → `ٱلَّعۡن`.

**Verification step:** before applying, always confirm which specific occurrences actually mispronounce in practice — not every doubled-lam word necessarily glitches, so don't blanket-apply this across a whole poem without spot-checking generated audio first. Log which words were converted and why, per project, so the fix can be reverted easily if Suno's pronunciation improves.

### The waw al-fariqa in "عمرو" is read as a spoken letter instead of a silent orthographic marker

**The glitch:** the word "عمرو" (Amr) carries a silent waw — the "waw al-fariqa" — that exists purely in writing to distinguish it from "عمر" (Umar) in undiacritized text; it carries no sound of its own, and the actual pronunciation depends entirely on the case-ending tanwin (عَمْرٌ / عَمْرٍ). Suno sometimes reads this waw as a spoken letter, producing e.g. "Amro" instead of the correct "Amrin" for a genitive "عَمْرٍ" — treating a purely orthographic mark as phonetic and dropping the tanwin sound in the process.

**The workaround:** since the project's text is already fully diacritized (Phase 0), the waw al-fariqa is redundant for Suno's purposes and can be dropped from the lyrics-box version of the word (not from the authoritative reference text) — write only "عَمْرٍ"/"عَمْرٌ" per the correct i'rab, keeping the tanwin exactly as it should sound.

**Verification status: unconfirmed.** Needs an A/B listening test (with the waw vs. without) before being applied across a whole poem; don't blanket-apply to every occurrence without spot-checking.

### End-of-hemistich wasl (continuation) is read as waqf (stop), swallowing the tanwin

**The glitch:** when a verse's sadr (first hemistich) ends on a word that should phonetically connect into the ajuz (second hemistich) — e.g. "...بعاجل طَعْنَةٍ" continuing into the next hemistich rather than stopping — Suno can instead treat the line break as a pausal position (waqf), dropping the tanwin and rendering the ta marbuta in its pausal form (silent/haa) with an unwanted silence, e.g. "طعنه" with a stop, instead of the connected "طعنتِن" the meaning and meter call for. This doesn't happen every time, which suggests it's tied to how the line is formatted in the lyrics box (e.g. the presence of a newline or line break at a point that isn't actually meant as a stop) rather than the tanwin itself.

**The workaround (unverified, two candidate fixes to test):**
1. Where wasl is intended, keep the sadr and ajuz on the same line (no newline between them) rather than splitting them visually in the lyrics box; reserve the line break for genuine waqf points.
2. If a visual/formatting split is still needed, avoid any pausal punctuation at that point and make sure nothing in the surrounding tags implies a stop.

**Verification status: unconfirmed, occurs inconsistently.** Needs a controlled test — hold everything else constant and vary only the line-break/formatting at the hemistich boundary — before promoting either candidate fix to a confirmed rule.

---

## Quick Checklist (per new poem)

- [ ] Full, verified, fully-diacritized text sourced and stored as structured data
- [ ] Thematic section map built (pivot verses identified, not arbitrary cuts)
- [ ] One maqam assigned per section (from the fixed set: Hijaz, Nahawand, Ajam, Kurd), with a deliberate arc across the whole poem
- [ ] Baseline (longest) section identified; padding planned for shorter ones using their own material
- [ ] Voice locked from a strong early draft; sliders fixed and never touched again — Nabigha project: Weirdness 20%, Style Influence 70% (see Phase 4, point 2)
- [ ] Test clip approved per section before full render
- [ ] Lyrics box follows the standard template: `///***///` → anchor intro (`[Intro | instrument | close-mic'd, plate reverb, short decay]`, no hum, no vocal-quality word in this tag) → dense vocal-quality tags set **once per mood** on section headers (anchor, don't repeat/intensify) + sparse instrument tags (palette-only, **one per genuine dramatic beat**, at pivot moments only, sustain/build verbs not percussive-hit verbs, no tag that just restates the section header) → maqam name currently omitted from mid-lyrics tags project-wide (v3 active experiment — see Gravitational Well glitch note; watch Nahawand sections first) → melismatic `...` → buffer-in/out → any padding
- [ ] Every tag checked against the 3-part schema (`Section | vocal quality | instrumentation`) and kept to a short phrase, not a sentence — no stacked clauses, no embedded reasoning
- [ ] No intensity/directional adjectives (`intensifying`, `pulling back`, `slightly`, `commanding`, `softening` applied to instruments) sitting in a section header — cues, not choreography (v4, unconfirmed — see Glitches section)
- [ ] No `hit`/`crash`/`slam`/`smash` verbs anywhere in an instrument tag, regardless of which instrument is named
- [ ] Take log kept for every approved section
- [ ] Any post-generation lyric error fixed via Phase 6.5's ordered options (Sample → Replace Section → Cover+Audio Influence → Persona-locked regen), not a straight full regeneration
- [ ] Full front-to-back listen for drift before final export
