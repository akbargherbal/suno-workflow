# WORKFLOW.md — Classical Arabic Poems → Suno Fusion Songs

This is an execution playbook, not a discussion document. Follow it as a sequence of steps for turning any classical Arabic poem into a coherent Suno production (single section or multi-section). Every rule below is the current standing rule — apply it directly.

---

> **Precedence rule:** this file documents the standing methodology. If the user's live instructions in the current session conflict with a rule here:
> 1. Name the conflicting rule (its section heading + a one-line summary of what it says).
> 2. Ask: update this file to match the new instruction, or apply it just for this session without editing the file?
> 3. Never silently follow this file over what the user just said — this is especially true for tagging, which is still an active area of experimentation.

---

## Phase 0 — Source the Text

1. Get the full text, **fully diacritized (mushakkal)**, i'rab endings included. Suno's pronunciation accuracy depends on this more than any prompt trick.
2. Cross-check against at least two reputable sources (critical print edition, trusted literary database). Pick one authoritative version and use it for the whole project.
3. Verify verse count and order before splitting into sections — some poems have disputed/additional verses across manuscripts. Decide the version up front.
4. Store the poem as structured data — one (sadr, ajuz) pair per verse, indexed from 1.
5. **Fixed creative target — do not re-derive per project:** Western symphonic rock/orchestral instrumentation carrying a deep, melismatic, classically-articulated Fus'ha vocal. The Arabic identity comes from the voice, not the instrumentation. Specific instrument choices live in the generator script and can change; this pairing does not.

---

## Output Schema — Section JSON

Every project's lyrics deliverable is one JSON file, one object per section:

```json
{
  "sections": [
    {
      "section_id": 1,
      "maqam": "Hijaz",
      "title": "الوداع والخطوات الوادعة",
      "lyrics": "///***///\n[Intro | single clean guitar | close-mic'd, plate reverb, short decay]\n..."
    }
  ]
}
```

- `section_id`: 1-indexed, in poem order.
- `maqam`: one of the fixed set only — Hijaz, Nahawand, Ajam, Kurd.
- `title`: Arabic section title, from the Phase 1 section map.
- `lyrics`: the full lyrics-box content as a single string, per Phase 5.
- **No `mood` field.** Mood is used only as a working label in the Phase 1 section-map table to help pick a maqam (Phase 2) — it is never written to the output JSON.

---

## Phase 1 — Thematic Segmentation

1. Read the whole poem first. Identify its classical movements where present (nasib/atlal, rahil/tardiyya, madih, fakhr, i'tidhar, hija', closing simile) — not every poem has all of these, and order varies.
2. Find the pivot verses (takhallus) — where the poet visibly shifts subject. These are the section boundaries, not arbitrary verse-count cutoffs.
3. Target 8–12 verses per section as a soft guideline (~3–4 min sung). A thematically tight 5–6 verse unit is fine; don't pad a section that doesn't need it. A single continuous narrative can run to 11–13 verses if splitting it would break the story.
4. Write the section map as a table: section name, verse range, verse count, mood tags (English, max 3 words). Keep it at the top of the project notes.
5. Checkpoint before Phase 5: present the section map + maqam assignments as a short brief with 2–3 targeted approval questions before starting lyrics engineering.

### Special case — short, single-section poems

A short poem (e.g. ~15 verses) does not need thematic splitting at all — treat the whole poem as one section (`section_id: 1`), skip the multi-section arc logic in Phase 2 point 3, and go straight to assigning it one maqam.

**The same pacing principle applies to any short section — whether it's a whole short poem or one section inside a longer poem:** a section can meet the 12–14 sung-unit target on paper (Phase 3) and still feel rushed when generated, because verse count is a proxy for duration, not for breathing room. When a section (short poem or short section of a long poem) risks feeling rushed:
- Default fix: use the section's Chorus repeat (Phase 3) as the breathing mechanism — this is the standing, low-risk tool.
- Optional fix, not a standing rule: split verses into smaller `[Verse]` blocks (2–3 bayt each instead of one long block) to slow the delivery pace.
- Optional fix, not a standing rule, use only if the above two aren't enough: an `[Instrumental Interlude]` or `[Instrumental Break]` (Phase 5, tag vocabulary). This is an available option that worked once (see the Ibn Zaydun note in Phase 3) — it is not required by default, and the Chorus repeat remains the preferred/default breathing tool.

Do not carry over a specific target duration (e.g. "aim for X minutes") from one project to another — log the actual result per project instead (see Phase 3 worked examples).

---

## Phase 2 — Assign a Maqam per Section

1. Choose from a fixed set of four maqams only: **Hijaz, Nahawand, Ajam, Kurd**. Match each section's mood (from the Phase 1 table) to whichever fits best.

   | Mood / character | Maqam |
   | --- | --- |
   | Longing, yearning, deep romantic ache | Hijaz |
   | Elegy, deep sorrow, parting | Hijaz |
   | Quiet sadness, gentle nostalgia | Nahawand |
   | Calm narration, description, inner dialogue | Nahawand |
   | Pride, zeal, triumph | Ajam |
   | Praise, celebration, glad tidings | Ajam |
   | Tension, anticipation, warning | Kurd |
   | Mystery, awe, gravity/formality | Kurd |

2. One maqam per section — no mid-section maqam changes. If a section genuinely needs two moods, split it (back to Phase 1).
3. Build a deliberate arc across the whole poem: reuse a maqam for sections that share emotional DNA (e.g. opening lament and closing appeal). Reserve any maqam with a very distinct color (typically Hijaz) for the one moment that's genuinely unique.
4. If a section mixes two moods, assign the maqam by numeric majority of verses (e.g. 4 verses of parting + 9 of pride in comrades → Ajam).

---

## Phase 3 — Buffer Verses & Padding

1. **Buffer verses:** echo the section's own first verse softly at the very start (doubles as the Phase 5 intro technique) and repeat its own last verse softly at the end. This gives literal audio material to crossfade against in Phase 7.
2. **Shared target: 12–14 sung units per section.** This is a counting exercise: sum each section's original verse count; if short of 12–14, repeat exactly as many verses as needed, pulled only from material already in the section — never write new lyrics.
   - Sections at 12–13 original verses usually need no lyrical repeat — buffer-in/out alone lands them at 14–15.
   - Sections clearly under target: repeat the section's single strongest/most iconic couplet as a `[Chorus]` (2x, verbatim) to close the gap.
   - Still short after one chorus repeat: add a short instrumental interlude (a few bars, no new lyrics) before/after the chorus.
3. Do the padding pass only after the section's base pacing/vocal take is confirmed.

**Worked example — Fath Amouriyya (Abu Tammam), 7 sections:** S2 (Nahawand, 12 verses) and S3 (Kurd, 13 verses) served as baseline with no internal repeat (14–15 units from buffering alone). Each shorter section repeated its own thematic-peak couplet as Chorus: S1 (Ajam, 10v) → 14; S4 (Nahawand, 10v) → 14; S5 (Hijaz, 9v) → 13; S6 (Kurd, 8v) → 12; S7 (Ajam, 9v) → 13. All seven sections landed in a near-uniform 12–15 unit band despite original verse counts ranging 8–13.

**Worked example — Ibn Zaydun, single-section poem (15 verses, "إني ذكرتك بالزهراء مشتاقا"):** landed at 17 sung units from buffer-in/out alone — inside the 12–14+ range on paper — but the generated take still felt rushed. Fix applied for this project only: one Chorus repeat (the section's peak couplet) + one `[Instrumental Break]` after it. Result: ~4:50–5:10 min, felt natural. **This duration is not a general target** — log the actual result per project; don't assume it carries over.

---

## Phase 4 — Lock the Voice and Settings

1. From the best early draft (a fast/cheap model tier is fine), create a **Voice** (locks singer identity) rather than only a Style Persona.
2. Lock Style Influence and Weirdness once, and never change them for the rest of the project. Only maqam and lyrics content vary between sections.
   - Log the actual values used **per project** — do not assume a prior project's values (e.g. Nabigha's Weirdness 20% / Style Influence 70%) carried over unless confirmed for the current project.
   - Weirdness = how far Suno explores away from the expected result. Style Influence = how literally Suno treats the style/exclude prompt.
3. When chasing higher fidelity on top of an early draft, prefer direct generation guided by the locked Voice over a Cover/re-render pass — Cover tends to reinterpret and speed up performances.
4. Generate a 30–60s test clip per section before a full render. Check: vocal pacing/stretch, pronunciation of phonetic spellings, whether the target maqam came through.

---

## Phase 5 — Lyrics Box Engineering

Applies per section, inside the lyrics box only (style/genre/production prompt is separate and set once, not per section).

1. First line: `///***///`.
2. Anchor Intro tag, immediately followed by the section's first line, no hum/pre-echo:
   `[Intro | single clean instrument | close-mic'd, plate reverb, short decay]`
   - Use the same instrument in this tag across every section — it's a consistent sonic signature.
   - Name the specific technique, not a generic adjective (`plate reverb, short decay` / `close-mic'd`, not "reverb" or "commanding") — generic words pull toward Suno's most common/mainstream association.
   - No vocal-quality word in the Intro tag — Intro is instrument + space only.
3. Tag schema: every `[Verse]`/`[Chorus]`/`[Bridge]`/`[Intro]` header follows `[Section | vocal quality | instrumentation]` — short phrase, 2–5 words per slot, one clause. Never stack a cause/exception/result into one tag.
4. **Vocal-quality descriptor: set once, as an anchor, never repeated or intensified in the same section.** State it at `[Verse 1]`/first `[Chorus]`; leave later headers in the same section bare. A reinforcing restatement (`vocals *still* forward`) is read by Suno as a new, additional push in that direction, not continuity — this compounds into an over-driven vocal by the section's later verses. A genuine mood shift later in the section gets a new plain descriptor (`vocals softening`) — never a continuity word ("still", "remains", "keeps").
5. **Instrument tags: dramatic beats only, 2–3 per section.** Not after every hemistich. Pull only from the instrument palette already in the style prompt; never introduce an instrument in the lyrics box that isn't in the style prompt or is on the Exclude list.
   - Never use percussive-hit verbs (`hit`, `crash`, `slam`, `smash`) in an instrument tag — even without naming drums, these verbs alone can summon a drum hit. Use sustain/build verbs instead: `swell`, `surge`, `build`, `rise`, `resolve`.
   - No intensity/directional adjectives in section headers (`intensifying`, `pulling back`, `slightly`, `commanding`, `softening` applied to instruments). If a section has a genuine instrumental pivot, tag it as a single plain mid-line cue (`[strings swell]`) at the actual beat — not as a header adjective.
   - Name the section's maqam directly inside its single main pivot tag only (the one dramatic-beat tag doing the heaviest lifting), e.g. `[guitars & strings swell — Nahawand]`. Do not scatter the maqam name across minor cues.
6. Tag density: after a full pass, split tags into **functional** (Intro tag, each section's vocal anchor, Outro buffer, any Phase 3 padding mechanism — never touch) and **decorative** (anything restating the header, any adjective on `[Chorus]` beyond the bare label — cut ruthlessly). One instrument tag per genuine dramatic beat; most sections justify one, or none beyond the header.
7. Melismatic stretch: append `...` to the end of every ajuz's rhyme word (and 1–2 extra climactic lines per section).
8. Buffer-in/out: repeat the first couplet across `[Intro]` + `[Verse 1]`; repeat the section's last couplet in `[Outro]`.
9. **Outro tag — standing format:** `[Outro | vocal quality | instrumentation]`, keeping the full 3-part schema (not a bare `[Outro | instrumentation]`). This is the default for all new sections.
10. Insert any Phase 3 chorus/refrain/instrumental padding directly into this same lyrics-box structure.

### Optional tool — Instrumental Interlude / Break (not a standing rule)

Use only if the Chorus repeat (Phase 3) and verse-block splitting (Phase 1, short-section note) aren't enough to prevent a section feeling rushed. Format: `[Instrumental Interlude | instrumentation]` or `[Instrumental Break | instrumentation — maqam]` (no vocal-quality slot; name the maqam here only if this is the section's main pivot tag). Default preference remains the Chorus repeat — treat this as a fallback, not a routine addition.

**Worked example** (Amr ibn Kulthum, Section 4 — Maqam Ajam):

```
///***///
[Intro | single clean guitar | close-mic'd, plate reverb, short decay]
نَعُمُّ أُنَاسَنَا وَنَعِفُّ عَنْهُمْ
وَنَحْمِلُ عَنْهُمُ مَا حَمَّلُونَا...

[Verse 1 | powerful resonant vocals | distorted guitar and steady bass]
نَعُمُّ أُنَاسَنَا وَنَعِفُّ عَنْهُمْ
وَنَحْمِلُ عَنْهُمُ مَا حَمَّلُونَا...
نُطَاعِنُ مَا تَرَاخَى النَّاسُ عَنَّا
وَنَضْرِبُ بِالسُّيُوفِ إِذَا غُشِينَا...

[Chorus | triumphant soaring vocals | full orchestral swell — Ajam]
وَإِنَّ الضِّغْنَ بَعْدَ الضِّغْنِ يَبْدُو
عَلَيْكَ وَيُخْرِجُ الدَّاءَ الدَّفِينَا...

[Verse 2]
نَجُذُّ رُءُوسَهُمْ فِي غَيْرِ بِرٍّ
فَمَا يَدْرُونَ مَاذَا يَتَّقُونَا...

[Outro | deep male vocals | clean electric guitar]
بِفِتْيَانٍ يَرَوْنَ الْقَتْلَ مَجْدَنْ
وَشِيبٍ فِي الْحُرُوبِ مُجَرَّبِينَا...
```

---

## Phase 6 — Generate, Section by Section

1. Same locked Voice + locked sliders every time (Phase 4). Only maqam and lyrics content change.
2. Test clip first, full section second.
3. Target a solid take (7/10+) before moving on — don't chase a perfect take on the first pass.
4. Log every kept take: section name, take number, maqam used, settings.
5. If a passage rushes, drifts, or mispronounces a word, go to Phase 6.5 before regenerating or Cover-ing the whole section.

---

## Phase 6.5 — Post-Generation Lyric-Error Fixes

Fix only the broken word/line, keeping voice/groove/arrangement as close as possible to the approved take. Try in this order, most surgical first:

1. **Sample (Beta)**, if available — resamples just the problem phrase.
2. **Replace Section (built-in editor)** — select the whole affected line/hemistich (minimum span ~10s; single words aren't selectable), not just the broken word. Keep every tag identical to the original generation and reuse the same Voice/Persona.
3. **Cover mode + high Audio Influence** — load the approved take as Cover source, type corrected lyrics, push Audio Influence to ~90–100 while keeping Weirdness low.
4. **Persona-locked regeneration** — if Cover drifts the voice, create a Persona from the approved take first, then regenerate with corrected lyrics using that Persona explicitly.
5. **Remaster** — for unclear/muddy audio only, not for wrong words.
6. **Human re-recording** (paid third-party, last resort) — for a finished project's last mile only.

*Unconfirmed on this project — verify with a controlled test on one known error (options 1–2 first) before treating any of the above as a settled step.*

---

## Phase 7 — Assembly (Audacity)

1. Export every section's audio.
2. Import in verse order.
3. Trim into the buffer-verse repeats at each boundary and crossfade there.
4. Full front-to-back listen. If one section's vocal identity/pacing drifts from its neighbors, regenerate just that section (same locked Voice/settings).
5. Export the final track.

---

## Workarounds / Known Suno Glitches

Stopgaps, not permanent orthography rules — revisit periodically as the model improves. Each entry: the rule to apply, why, and its confidence status.

### Gravitational Well — drift toward generic Western pop-rock

**Rule:** name the section's maqam directly inside its single main pivot instrument tag, e.g. `[guitars & strings swell — Nahawand]`. Reserve this for the one or two genuinely load-bearing tags per section; never inside the Intro tag.
**Why:** pairing a named maqam with a Western instrument inside one tag is an unusual/rare combination in Suno's training data, which keeps the model in maqam-flavored territory instead of drifting to a generic Western default — this effect gets worse, not better, if drum cues are removed without something else taking their place (an unusual drum+maqam pairing was itself doing this job before).
**Status: confirmed** by listening test (with/without the fix, same section).

### Percussive-hit verbs in instrument tags summon drums

**Rule:** never use `hit`, `crash`, `slam`, `smash` in an instrument tag, even naming only non-percussion instruments. Use `swell`, `surge`, `build`, `rise`, `resolve` instead.
**Why:** these verbs carry a strong drum-kit association in the training data independent of which instruments are named.
**Status: partially confirmed** — inferred from the gravity-well pattern, applied preventively; not yet isolated in its own A/B test.

### Repeated/escalating vocal-quality tags read as new commands

**Rule:** set each section's vocal-quality descriptor once, at its first appearance, and don't repeat it — even in a softer form ("still", "remains", "keeps"). A genuine mood shift gets a new, distinct descriptor instead. Never ask Suno to "lower" or "reduce" vocal level — that's itself a new instruction with unpredictable results. This also applies to intensity/directional words in instrument headers (`intensifying`, `pulling back`, `commanding`) — strip these from headers; if a real pivot needs marking, use one plain mid-line instrument cue instead.
**Why:** Suno reads a reinforcing restatement as an additional push in that direction, not "hold the current level" — this compounds into an over-driven vocal or over-busy arrangement by the section's later verses.
**Status:** vocal-tag version **confirmed** by listening test. Header intensity-adjective version **unconfirmed**, applied preventively — spot-check before promoting to confirmed.

### Doubled lam from the definite article mispronounced

**Rule:** when a word begins with root-letter ل and takes the definite article (الليل, اللعن), rewrite it in Uthmani-style orthography in the lyrics box only (not the reference text): alef wasla (`ٱ`) + single ل carrying the shadda + small Quranic sukun (`ۡ`) if there's an internal sukun. Keep the i'rab ending exactly as it was. Example: `الليل` → `ٱلَّيۡل`.
**Scope — does not apply to:** other words merely starting with ل without the definite article, or to الذي/التي/الذين (different phonetic case, not confirmed to trigger this).
**Status: needs per-occurrence spot-check** — not every doubled-lam word necessarily glitches; confirm on generated audio before applying, and log which words were converted so the fix can be reverted later.

### Waw al-fariqa in "عمرو" read as a spoken letter

**Rule:** drop the silent waw from the lyrics-box version of the word (keep it in the reference text) — write only `عَمْرٍ`/`عَمْرٌ` per the correct i'rab.
**Why:** the waw is a purely orthographic marker with no sound of its own; Suno sometimes reads it as spoken (e.g. "Amro" instead of "Amrin"), dropping the tanwin in the process.
**Status: unconfirmed** — needs an A/B test (with/without the waw) before blanket application.

### End-of-hemistich wasl read as waqf, swallowing the tanwin

**Rule:** where the sadr should phonetically connect into the ajuz (wasl), keep them on the same line in the lyrics box (no line break between them); reserve line breaks for genuine stop points. If a formatting split is still needed, avoid pausal punctuation and anything in surrounding tags that implies a stop.
**Why:** Suno can treat a line break as a pausal position, dropping the tanwin and turning the ta marbuta pausal/silent, even where the meaning/meter calls for connection.
**Status: unconfirmed, occurs inconsistently** — needs a controlled test varying only the line-break at the hemistich boundary before promoting either candidate fix.

---

## Quick Checklist (per new poem)

- [ ] Full, verified, fully-diacritized text sourced and stored as structured data
- [ ] Poem length checked: short poem (~15 verses or less) → single section, no thematic split (Phase 1 special case); otherwise → thematic section map built from pivot verses
- [ ] One maqam per section from the fixed set (Hijaz, Nahawand, Ajam, Kurd), with a deliberate arc
- [ ] Shared 12–14 sung-unit target set per section; shortfall padded via the section's own strongest couplet as `[Chorus]`
- [ ] Any section (short poem or short section of a long poem) at risk of feeling rushed: Chorus repeat used as the default breathing tool first; verse-block splitting and Instrumental Interlude/Break kept as optional fallbacks, not routine additions
- [ ] Voice locked from a strong early draft; sliders fixed and never touched again — actual values logged per project, not assumed from a prior project
- [ ] Test clip approved per section before full render
- [ ] Lyrics box: `///***///` → anchor Intro (no vocal-quality word, no hum) → vocal-quality anchored once per section (never repeated/escalated) → sparse instrument tags at real pivots only, sustain/build verbs only → maqam named once, at the main pivot tag only → melismatic `...` → buffer-in/out → Outro keeps the full 3-part schema
- [ ] No `mood` field anywhere in the output JSON
- [ ] Every tag checked against `[Section | vocal quality | instrumentation]`, kept to a short phrase
- [ ] No intensity/directional adjectives in section headers; no `hit`/`crash`/`slam`/`smash` in any instrument tag
- [ ] Take log kept for every approved section, with actual settings and duration (not assumed from another project)
- [ ] Post-generation lyric errors fixed via Phase 6.5's ordered options, not a straight regeneration
- [ ] Full front-to-back listen for drift before final export
