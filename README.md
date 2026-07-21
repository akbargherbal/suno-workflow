# Suno Workflow: Classical Arabic Poetry to AI Audio

A systematized, high-fidelity pipeline for transforming long-form classical Arabic poetry (Qasidas, Mu'allaqas) into coherent, multi-part musical productions using Suno AI.

## The Problem

Standard "prompt-and-hope" AI music generation fails for long-form literary works. Suno's tendency toward "genre drift" (the "Gravitational Well" glitch), mispronunciation of diacritics, and inconsistency in vocal identity makes long-form production impossible without strict, reproducible system constraints.

## The Solution

This repository documents a rigorous engineering approach to AI music production. Rather than treating Suno as a creative tool, this workflow treats it as a **rendering engine** that requires:

1. **Deterministic Locking:** Fixed "Voice" identities, slider values, and acoustic settings.
2. **Thematic Segmentation:** Breaking poems by narrative pivots rather than arbitrary line counts.
3. **Lyrics Engineering:** A standardized tagging schema (the "3-part schema") that removes ambiguity for the model.
4. **Pronunciation Control:** Uthmani-style orthography fixes for specific Arabic phonetic glitches.

## Repository Structure

- `projects/`: Contains project-specific configurations (e.g., `nabigha`).
- `scripts/`: Automation tooling.
  - `maqam_prompt_generator.py`: A prompt-engineering tool that locks in cinematic-orchestral parameters, allowing only the Maqam selection to vary.
- `workflow.md`: The primary English technical documentation and methodology.
- `الدليل.md`: The Arabic translation and reference for the workflow methodology.

## Getting Started

### 1. Tooling

The `maqam_prompt_generator.py` is the engine of this workflow. It enforces the "Winning Template" discovered through 2.5 months of iterative testing.

**Run it to generate your prompt:**

```bash
python scripts/maqam_prompt_generator.py
```

This script eliminates "mood drift" by removing variable mood fields and forcing the model to adhere to a fixed, high-fidelity acoustic profile.

### 2. The Methodology

Before generating, familiarize yourself with the 7-Phase Pipeline:

- **Phase 0:** Text sourcing (full tashkeel mandatory).
- **Phase 1:** Thematic segmentation (pivot-verse identification).
- **Phase 2:** Maqam Assignment (Hijaz, Nahawand, Ajam, Kurd only).
- **Phase 3:** Buffer/Padding management.
- **Phase 4:** Voice & Slider Locking (Weirdness 20%, Style Influence 70%).
- **Phase 5:** Lyrics Box Engineering (The 3-part tag schema).
- **Phase 7:** Audacity Assembly (Crossfading at buffer points).

## Known Glitches & Workarounds

This workflow maintains a living record of Suno's behavior. If you encounter issues, consult the "Workarounds / Known Suno Glitches" section in `workflow.md` for fixes regarding:

- **Gravitational Well:** Drift toward Western pop-rock.
- **Percussive-verb Tags:** Accidental drum summoning.
- **Vocal Tag Escalation:** Why you shouldn't use "still" or "remains" in tags.
- **Lam Assimilation:** The Uthmani orthography fix for definite articles.

## Documentation

- [English Documentation](workflow.md)
- [الدليل العربي](ar_workflow.md)

---

> **Note:** This repository is a record of a live, ongoing experiment. If you find instructions in this file that conflict with direct experimental data, follow the data. The documentation is a map, not the territory.
