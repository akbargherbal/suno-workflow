# Glossary & Terms — Audio Engineering Vocabulary Used in Notebooks 00–06

This glossary collects **every specialized term, abbreviation, tool name, and unusual verb**
used across the seven notebooks (`00` through `06`), explained in plain English. Terms are
grouped by theme rather than alphabetically, because most of them only make sense next to the
related ideas around them. Within each group, terms are ordered the way you'd naturally meet
them (simple idea first, more advanced idea after).

If you ever hit a word in the notebooks or in the project's scripts (`vocal_prominence.py`,
`separation_quality_audit.py`, `reverb_decay_analysis.py`, `stem_analysis.py`, `context.md`,
`AGENTS.md`) that isn't defined here, treat that as a bug in this glossary and flag it.

---

## 1. The absolute basics: what a digital audio file *is*

**Waveform**
The plot of a sound's **amplitude** over time. It is literally a very long list of numbers, one
after another, each one saying "how far the air pressure was pushed at this instant." Nothing
about pitch or tone color is visible in a waveform by itself — only loudness, moment to moment.

**Amplitude**
A single number describing how far the air pressure (or, in a digital file, the stored signal
value) is pushed away from zero at one specific instant. In a normalized digital file this
usually ranges from about −1.0 to +1.0. Zero means silence at that instant; the farther from
zero, the louder that instant is. It is *not* the same thing as loudness over a whole clip (see
**RMS** below) — it's just one snapshot.

**Sample / Sample rate (`sr`)**
A computer cannot store a truly continuous wave, so it takes **samples** — snapshots of the
amplitude — many times per second. The **sample rate** is simply "how many snapshots per
second," measured in Hz (see **Hz** below). 44,100 Hz ("44.1 kHz," CD quality) and 48,000 Hz
("48 kHz," common in video/streaming) are two common rates. Loading two files that have
*different* native sample rates and treating "sample number 1000" as "the same moment in both"
is a classic, silent bug — which is why the scripts in this project always load audio with
`librosa.load(path, sr=None)` (see next entry) instead of trusting a default.

**`sr=None` (in `librosa.load`)**
By default, the `librosa` library quietly **resamples** every file down to 22,050 Hz when you
load it — meaning it throws away some detail and recalculates the file at a lower sample rate,
whether you asked for that or not. Passing `sr=None` tells it "keep the file's own original
rate." This project always uses `sr=None` so that two tracks recorded at genuinely different
native rates never get silently compared as if they were the same.

**Mono**
An audio signal with a single channel — one stream of amplitude numbers, meant to be played
identically through every speaker/ear. There is no left/right distinction in mono audio.

**Stereo**
An audio signal with **two** channels — a **Left (L)** channel and a **Right (R)** channel —
meant to be played through two separate speakers, or into the left and right ears via
headphones. The small differences between L and R at any instant carry all of a mix's stereo
information (see **Mid/Side decomposition** below).

**Clipping**
When a digital signal's amplitude tries to exceed the maximum the format can represent (roughly
±1.0 for a normalized file) and gets abruptly cut off (flattened) instead of continuing to rise.
0 dB is described in the notebooks as "the loudest a digital file can be without clipping."

---

## 2. Turning a wave into a single loudness number

**RMS (Root Mean Square)**
A single number that answers "on average, how much energy did this chunk of audio have?" You
can't just average raw amplitude values directly, because positive and negative values cancel
each other out to roughly zero even in a loud signal. RMS fixes that in three steps:
1. **Square** every amplitude value (this removes the negative signs and weights loud peaks
   more heavily — closer to how physical energy actually behaves).
2. Take the **mean** (average) of those squared values.
3. Take the **square root**, to bring the units back to something comparable to the original
   amplitude scale.

**dB (decibel)**
RMS converted onto a *logarithmic* scale, because human hearing is not linear — it takes a much
bigger jump in raw physical energy before your ear perceives "twice as loud." dB compresses the
numbers so they track what your ear actually experiences. In this project's convention, dB
values from audio are **negative** (0 dB = the loudest a file can be without clipping; more
negative = quieter). A *higher* (less negative) dB number always means *louder*.

**`rms_db()`**
The specific helper function used throughout this project's scripts: it computes RMS and then
converts that RMS value to dB in one step. A tiny constant (`eps`) is added before taking the
logarithm so that a perfectly silent (all-zero) signal doesn't produce an undefined
`log(0) = −infinity` result and crash the code.

**Vocal prominence**
A project-specific term (not a general audio-engineering term) meaning:
`RMS_dB(vocal) − RMS_dB(instrumental)`
— i.e., how many dB louder (or quieter) the vocal is than the instrumental backing, in a given
window of time. A positive number means the vocal sits above the instrumental; a negative
number means the instrumental is louder at that moment.

**Silence gate (as applied to windows of audio, not the tool artifact in §6)**
A simple filtering rule used before computing statistics: windows where the signal is
essentially silent (e.g. `Mid < −40 dB`, or `vocal < −40 dB`) are dropped from the analysis,
because a silent frame carries no meaningful information about balance or content.

---

## 3. Statistics vocabulary used to summarize numbers

**Median**
The middle value of a sorted list of numbers — the "typical" value, less sensitive to extreme
outliers than a plain average.

**Mean**
The ordinary arithmetic average: sum everything, divide by how many values there are.

**Std / Std Dev (Standard deviation)**
A single number describing how spread out a set of values is around its mean/median. A small
std means values cluster tightly together (consistent); a large std means values swing widely
(inconsistent) even if the *typical* value looks fine.

**IQR (Interquartile Range)**
The range covering the middle 50% of a sorted list of values (from the 25th percentile to the
75th percentile). Like std dev, it measures spread, but it's less influenced by a few extreme
outliers.

**Range**
Simply the distance from the smallest value in a data set to the largest.

**Box plot**
A chart that visually summarizes a set of numbers using their median, their IQR (the "box"),
and their overall range (the "whiskers"), letting you compare several tracks' distributions
side by side at a glance.

**Histogram**
A chart that groups numeric values into "bins" (ranges) and shows how many values fall into
each bin, as bars — useful for spotting where large clusters of data pile up (e.g. a pile of
frames all sitting at exactly the same extreme value).

**Correlation**
A number (typically between −1 and 1) describing how closely two signals rise and fall
together over time. A correlation near 1.0 means their *shape* over time matches almost
perfectly, even if their absolute loudness levels differ.

---

## 4. Frequency (pitch), as opposed to loudness

**Frequency**
How *fast* a wave is vibrating/wiggling — this is what we perceive as **pitch**. It is a
completely separate property from loudness (amplitude/RMS/dB): a sound can be quiet and
high-pitched, or loud and low-pitched, independently.

**Hz (Hertz, "cycles per second")**
The unit frequency is measured in. A low bass note might vibrate 60 times a second (60 Hz); a
bright cymbal shimmer might vibrate 8,000 times a second (8 kHz — see **kHz** below). Human
hearing roughly spans 20 Hz to 20,000 Hz, though most musically important content (bass,
vocals, most instruments) sits below 5 kHz.

**kHz (kilohertz)**
A shorthand for "thousands of Hz" — 1 kHz = 1,000 Hz. Used constantly in the notebooks (e.g.
"2–5 kHz," "44.1 kHz").

**Fundamental frequency**
The main, dominant pitch you perceive when a note is sung or played — the "root" tone.

**Harmonics**
Quieter tones stacked on top of the fundamental frequency, at whole-number multiples of it (2x,
3x, etc.). No real musical note is a single pure tone; it's a fundamental plus a stack of
harmonics, and the exact mixture of harmonics is a big part of what makes different instruments
(or voices) sound distinct even when playing the same pitch.

**Formant**
A resonance — a frequency range that gets naturally boosted — shaped by the physical cavity a
sound travels through (the mouth/throat/nasal passages for a singing voice; the body of a
guitar or the bore of a trumpet for an instrument). Formants, and the fact that they shift
constantly as a person speaks or sings, are a large part of what makes a human voice sound like
a *voice* rather than an instrument playing an identical note — and part of why voices are
harder for AI separation tools to cleanly isolate than more static instrument tones.

**Spectrum**
A description of "how much of each frequency is present" in a chunk of audio, all added
together, with time collapsed away — i.e., not "how loud, when" (that's a waveform) but "made
of which pitches, how much of each."

**FFT (Fast Fourier Transform)**
The mathematical tool that takes one chunk of waveform and calculates its spectrum — how much
energy is present at each frequency in that chunk.

**STFT (Short-Time Fourier Transform)**
An extension of the FFT that "adds time back in": instead of one static spectrum for an entire
clip, it computes many FFTs on small, overlapping windows in a row and stacks the results
together, producing a **spectrogram** (see next entry). This is the function `librosa.stft`
used throughout the project's separation-quality and reverb scripts.

**Spectrogram**
The picture that comes out of an STFT: time runs along the x-axis, frequency runs along the
y-axis, and color represents how much energy is present at that frequency, at that instant.
Bright horizontal bands are sustained pitches (held vocal notes, sustained instrument tones);
short vertical smears are percussive hits (a drum, a pluck) that briefly excite a wide range of
frequencies at once.

**Frequency bands (named ranges)**
Engineers rarely talk in exact Hz numbers; instead they group frequencies into named bands,
because different instruments and different mixing problems tend to live in different ranges.
The bands used throughout this project (from `stem_analysis.py`):

| Band | Range | Typically home to |
|---|---|---|
| Sub | 20–60 Hz | Felt more than heard; deep bass extension |
| Bass | 60–250 Hz | Bass guitar/synth, kick drum body |
| Low-Mid | 250–500 Hz | Vocal/instrument "body" and warmth |
| Mid | 500–2,000 Hz | Where most instruments and vocal clarity live |
| Presence | 2,000–5,000 Hz | Vocal intelligibility, "forwardness," consonants |
| Treble | 5,000–20,000 Hz | Air, shimmer, cymbals, breathiness |

**"Presence" (as a band name)**
Specifically the 2–5 kHz range — the frequencies that give a vocal its clarity, intelligibility,
and sense of "cutting through" a mix. Not to be confused with the general English word
"presence."

**Spectral flatness**
A number that tells apart plain background *noise* from a *tonal* (musically structured) sound.
It compares the **geometric mean** of a spectrum's energy across frequencies to its
**arithmetic mean**:
- White noise (energy spread evenly across every frequency) → the geometric mean is close to
  the arithmetic mean → **flatness close to 1.0**.
- A pure tone, chord, or hum (energy concentrated in a few frequencies) → a few tall spikes drag
  the arithmetic mean up while the geometric mean stays low → **flatness close to 0**.
In this project, spectral flatness is used to check whether "quiet" parts of a vocal stem are
genuine noise floor (high flatness = good separation) or actually contain leftover instrumental
content (low flatness = **bleed**, see §6).

**Geometric mean / Arithmetic mean**
Two different ways of averaging a list of numbers. The **arithmetic mean** is the everyday
average (sum, divide by count). The **geometric mean** multiplies all the values together and
then takes the appropriate root — it is much more sensitive to small values being present, and
is pulled down hard by even one near-zero value, which is exactly why it's low when energy is
concentrated in only a few frequencies.

---

## 5. The stereo field: panning, Mid/Side, and stereo tools

**Panned / Panning**
"Panning" a sound means positioning it somewhere between the left and right speakers by
adjusting its relative volume in each channel — this is the verb the notebooks use constantly
and is worth spelling out precisely, since it isn't an everyday English word. If a sound is
**panned left**, its Left-channel amplitude is made bigger than its Right-channel amplitude at
that moment (so it feels like it's coming more from the left speaker). A sound panned **dead
center** has (nearly) identical amplitude in L and R — vocals and kick drums are almost always
panned dead center in a typical pop mix. "Panned instruments" means instruments that have been
deliberately placed off-center in the stereo image (e.g., a guitar mixed slightly to the right).

**Mid/Side decomposition**
A standard technique for splitting a stereo signal into "the part both channels agree on" and
"the part they disagree on":

$$\text{Mid} = \frac{L + R}{2} \qquad \text{Side} = \frac{L - R}{2}$$

- **Mid** — content that's identical (or nearly identical) in L and R adds up constructively.
  Centered content (lead vocal, kick, bass, snare) survives strongly in Mid.
- **Side** — if L and R are identical, subtracting them gives zero. Only content that *differs*
  between the channels (panned instruments, stereo reverb, width effects) shows up in Side.

The transform is **reversible**: `L = Mid + Side` and `R = Mid − Side`, exactly, with no loss of
information (a "lossless" transform — see below). This reversibility is why Mid/Side is a real
mixing/mastering tool and not just a measurement trick: engineers can process Mid and Side
independently and then recombine them back into a normal L/R stereo signal.

**Lossless (in the Mid/Side context)**
Describes a transform that can be perfectly undone — encoding to Mid/Side and immediately
decoding back gives you (up to floating-point rounding) the exact original signal, with nothing
lost or altered.

**Width**
A single-number summary of how "wide" (spread out) a stereo signal is, calculated in this
project as `Side_dB − Mid_dB`. A higher (less negative) number means more energy is living in
the Side channel relative to Mid — i.e., a wider-sounding mix. A lower number means the mix is
narrower/more centered.

**Narrow / Wide (as EQ moves or descriptions)**
"Narrow" describes pulling a mix's image toward the center (reducing Side content relative to
Mid) — reverb and pads lose spread while centered elements like the vocal keep their volume.
"Wide" describes the opposite — boosting Side content so the edges of the mix (air, cymbals,
reverb) become more prominent, without touching the centered Mid content (and therefore without
touching the vocal's tone).

**Goniometer (a.k.a. Lissajous scope / vectorscope)**
A visualization tool that plots every sample of the Left channel on the x-axis against the
corresponding sample of the Right channel on the y-axis. A **mono** signal (L = R at every
instant) produces points that all fall exactly on the diagonal line `y = x`. A **wide** stereo
signal (lots of `L ≠ R` content) sprays points out into a cloud around that diagonal — the more
spread in the cloud, the wider the stereo image.

**Mono compatibility / "mono-safe"**
A property of a mix that still sounds correct (nothing missing or hollowed-out) when played
back in mono — i.e., when L and R are summed together. Bass content is traditionally kept
centered (in Mid) specifically because centered content survives summing to mono; content that
lives entirely in Side can partially or fully cancel out when a mix is collapsed to mono. This
is why "keep the bass centered" is a standard mixing rule.

---

## 6. EQ (equalization) and phase concepts

**EQ (Equalizer / Equalization)**
A tool/process that changes the volume of specific frequency ranges independently — boosting
some, cutting others — rather than changing the volume of the whole signal uniformly.

**Boost / Cut**
"Boosting" a frequency range means increasing its volume relative to the rest of the signal.
"Cutting" a frequency range means decreasing its volume relative to the rest.

**High-pass (filter)**
An EQ move that lets high frequencies "pass" through largely unchanged while reducing (cutting)
everything below a chosen frequency. Used, for example, to remove low rumble from a signal.

**High-cut / Low-pass (filter)**
The mirror image of a high-pass: lets low frequencies pass through while reducing everything
above a chosen frequency.

**De-ess / De-essing**
A specific EQ move that reduces harsh "s" and "sh" sibilant sounds in a vocal, typically by
cutting around 5–8 kHz. In this project's Mid/Side context, de-essing is done by cutting that
band in the **Mid** channel only, since sibilance is centered content — leaving any cymbal
brightness living in the Side channel untouched.

**Mid/Side EQ**
Applying *different* EQ curves to the Mid and Side signals (rather than the same curve to both
L and R) — this lets an engineer change "the center" and "the edges" of a mix independently.
Example moves used in the notebooks: high-pass the Side below ~120 Hz for tighter, mono-safe
bass; cut 250–400 Hz in the Side for a cleaner, wider low end; boost 8–16 kHz in the Side for
"air" without brightening the vocal; cut 5–8 kHz in the Mid to de-ess without dulling the
cymbals; cut 200–400 Hz in the Mid for punchier drums without louder vocals.

**Phase**
Describes the timing relationship of a wave — specifically, at what point in its cycle a
frequency component is, relative to some reference. Two signals that are "in phase" line up in
time; signals that are "out of phase" are shifted relative to each other, which can cause
partial or full cancellation when they're combined.

**Group delay**
A side effect of ordinary ("minimum-phase") EQ filters: they don't just change volume per
frequency (the intended effect) — they also delay *different* frequencies by *different*
amounts. This frequency-dependent delay is called group delay. It's usually harmless in a plain
stereo EQ (since L and R get the same delay), but becomes audible in Mid/Side EQ, because
applying *different* filters to Mid and Side bakes *different* delays into each, which shifts
their timing relationship once they're recombined into L/R — causing transients to smear and
the stereo image to feel unstable ("wobble").

**Minimum-phase (EQ)**
The default, conventional type of EQ filter: efficient, but introduces group delay (see above),
which is the mechanism behind the "phase trap" in Mid/Side processing.

**Linear-phase (also called zero-phase) EQ**
An EQ design that delays every frequency by the *same* amount, so the only thing it changes is
volume, not timing. This avoids the group-delay smearing problem described above, which is why
serious Mid/Side mastering tools offer a linear-phase option/toggle.

**Oversampling (HiQ)**
A toggle found in some EQ plugins (e.g. Ableton's EQ Eight) that reduces some phase-related
artifacts but is explicitly *not* the same thing as true linear-phase EQ — the notebooks note
this distinction to avoid readers assuming the two are interchangeable.

**Utility (device)**
An Ableton Live audio utility device used, among other things, to manually build a Mid/Side
encode/decode chain: setting its Width control to 0% passes only the Mid signal, and to 200%
passes only the Side signal (with one channel phase-flipped), which is the manual, mouse-driven
equivalent of the `mid_side()` / `from_mid_side()` functions used in the code.

**EQ Eight**
A specific EQ plugin built into Ableton Live, mentioned because it includes a built-in Mid/Side
mode (each band's channel selector can be set to L/R, Mid-only, or Side-only) that reproduces
the notebook's `process_mid`/`process_side` code with a single click instead of custom code.

---

## 7. Reverb and time-based decay

**Reverb (reverberation)**
The sound of a physical room: after the direct sound of a voice or instrument reaches your ear,
reflections off the walls, floor, and ceiling keep arriving for a short while afterward, each
one quieter than the last, before dying away entirely.

**Decay tail**
The visible/audible fade after a note ends, caused by reverb — instead of energy dropping
instantly to silence, it fades out gradually over some period of milliseconds to seconds.

**Decay slope**
The standard way engineers quantify a decay tail: how many dB the signal loses per second right
after a note ends. A steep, fast slope (e.g. −60 dB/sec) means the sound dies out almost
immediately — little or no reverb. A shallow, slow slope (e.g. −10 dB/sec) means the sound
lingers — a longer, "wetter" tail.

**T60**
A single summary number derived from the decay slope: the time it would take for a sound to
decay by 60 dB at that rate. Used as shorthand for "how long does the room ring."

**"Wet" / "Dry"**
Informal engineering shorthand (used in the notebooks' prose, e.g. "wetter tail") for how much
reverb/effect is present in a sound. "Wet" means more reverb/effect is audible; "dry" means the
sound is closer to its original, untreated, close-mic'd state.

---

## 8. AI vocal/instrumental separation and its artifacts

**Stem**
An individual isolated component of a mix — for example, "the vocal stem" or "the instrumental
stem" — produced either by a human engineer during the original recording/mixing process, or,
in this project's case, by an AI separation model applied after the fact to a finished stereo
mix.

**Separation (AI vocal/instrumental separation)**
The process (performed by a machine-learning model) of taking one finished, mixed stereo track
and splitting it back into an estimated vocal stem and an estimated instrumental stem, without
ever having had access to the original, separately-recorded tracks.

**Proxy**
A stand-in measurement used in place of the "real" thing you actually want to measure, when the
real thing isn't directly available. In this project, Mid/Side (`Mid_dB − Side_dB`) was used
early on as a *proxy* for real vocal-vs-instrumental prominence (`vocal_dB − instrumental_dB`),
because no isolated stems existed yet for some tracks.

**Ground truth**
The real, verified, correct answer that a proxy or estimate is trying to approximate — for
example, real human-separated vocal/instrumental stems (where they exist) serve as ground truth
against which a Mid/Side proxy, or an AI separation tool's output, can be checked.

**Calibration (check)**
The act of comparing a proxy's or a tool's output against ground truth, on the one case where
ground truth happens to be available, in order to estimate how far off the proxy/tool tends to
run in general.

**Reconstruction fidelity**
A label-free way of auditing a separation tool's accuracy: since `vocal + instrumental` should
sum back to (approximately) the original mix if the split was clean and complete, you can add
the two output stems back together and compare that sum to the real original mix — with no
ground-truth stems required. A near-zero gap (in dB) means the tool accounted for almost
everything in the mix; a consistent negative gap means the reconstructed sum is quieter than the
original, i.e., some of the mix's energy didn't end up fully assigned to either stem.

**Bleed (residual bleed / bleed-through)**
Content from one stem leaking into the other — for example, instrumental content that wasn't
fully removed from the vocal stem, so it's still faintly audible ("bleeding through") even in
sections where the vocal stem should be silent. Detected in this project using **spectral
flatness**: a "quiet" vocal-stem frame with low flatness (tonal, structured energy) suggests
bleed rather than genuine noise floor.

**Hard gate**
A discovered behavior of the separation tool (or its export step): whenever the model's
confidence that "a vocal is present" drops low enough, it appears to zero the output completely
(every sample becomes exactly 0.0 — literal digital silence, ~−infinity dB) rather than leaving
a faint, natural-sounding residual. This showed up uniformly across every track tested (21–31%
of all frames), which is why it was identified as an artifact of the *tool/pipeline itself*
rather than a property of any individual song's mix.

**Gate entry / Hard-gate entries**
The moment (timestamp) a vocal stem's signal transitions from real, audible content into the
tool's hard-gated (zeroed) silence — used in this project as a reliable marker for "a phrase
just ended," since it's a clean, unambiguous binary event rather than a subjective judgment
call.

---

## 9. The overall research-method vocabulary

**Hypothesis**
A proposed explanation that hasn't yet been fully verified — something the project sets out to
test, confirm, or rule out using measurements.

**"Confirmed" (as used critically in these notebooks)**
Flags a conclusion the project *believed* was settled at the time, based on one analysis
technique, that later turned out to be incomplete or partly wrong once tested with a more
direct method. The notebooks use quotation marks around "confirmed" deliberately, as a running
theme about not trusting a single measurement too quickly.

**Relative ranking (vs. absolute level/number)**
Two different things a measurement can get right or wrong. "Absolute level" means whether a
specific number is correct in its own right (e.g., "the gap really is 3 dB"). "Relative
ranking" means whether the *order* of several things compared to each other is correct (e.g.,
"Track A really is behind Track B"), even if none of the individual absolute numbers are
exactly right. A proxy can preserve relative ranking while still being wrong in absolute terms
— or, as this project discovered, it can fail at both.

**Loose thread**
An observation noticed in passing during one analysis that isn't fully investigated at the
time, and is explicitly "parked" to be picked up properly once the right tools/vocabulary exist
— used repeatedly across these notebooks to describe questions deliberately deferred rather
than rushed.
