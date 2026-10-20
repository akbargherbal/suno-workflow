## Decide this first — "regenerate" has two meanings

Your seed is pinned (`2640605763`) and generation is **deterministic** (Pass 1's `ref` arm re-rendered byte-identical). So:

- **Same seed + this recipe ⇒ byte-identical to Q1.** You don't need to regenerate anything — that take is already banked (`…/probe_q/eval/v3q_Q1_ctm_g15.wav`), rated **4 overall / keep = yes**. Zero GPU.
- **A new seed ⇒ a fresh take of the same recipe** — that's the untested Pass 2. It could be better or worse; nothing measured predicts which. This is the *only* reason to spend a GPU track.

So if the goal is "get the best take we know of," the answer is: **use the file you already have.** Regenerating only makes sense when you want a new sample.

## The recipe (Q1 — best measured)

| Item | Value |
|---|---|
| **Style** | the 41-word "CTM" string below, verbatim |
| **Lyrics** | `INFERENCE/probe_q_lyrics.txt` — frozen, byte-verbatim, shared by every Probe Q arm |
| **Sampler** | `guidance_scale=1.5` — **the only change** |
| rep-pen / temp / cot | `1.2` (default) / `1.0` (default) / `off` |
| **Adapters** | v3 final pair, `/content/converter/out/v3_arabmaqamrock_lora_{ar,nar}.safetensors`, scale **1.0 / 1.0** |
| **Seed** | `2640605763` (replay) **or** a fresh value (new take) |
| **Cap** | `7000` (as in Probe Q; an upper cap) |
| Expected shape | ≈224 s, 2 ch / 48 kHz |

**Style, verbatim:**

> `arabmaqamrock dark symphonic rock, slow stately groove, 100 BPM. Maqam Kurd. deep male vocals, breath-supported melismatic runs, melismatic phrasing in Maqam Kurd, unhurried phrase-ending sustains. Distorted electric guitars, orchestral strings, weighted acoustic rock drums, tight rhythm section. Mood: solemn, ominous, grave.`

The lyrics file is Intro → Verse 1 → Chorus ×2 → Outro (lines 1–35); I'm pointing at it rather than pasting 35 lines since it lives in the repo. Co-equal alternative: swap the knob for `semantic_repetition_penalty=1.35` (that's Q3, identical scores). **Don't** combine them (Q4 — the one rejected take) and **don't** use the retarget wording (Q5 — generic).

## The manifest (new file — don't edit the frozen probe manifests)

`INFERENCE/songs.v3_q1_g15.json`:

```json
{ "defaults": { "repeat": 1 },
  "songs": [ { "name": "v3_q1_g15",
    "style": "arabmaqamrock dark symphonic rock, slow stately groove, 100 BPM. Maqam Kurd. deep male vocals, breath-supported melismatic runs, melismatic phrasing in Maqam Kurd, unhurried phrase-ending sustains. Distorted electric guitars, orchestral strings, weighted acoustic rock drums, tight rhythm section. Mood: solemn, ominous, grave.",
    "lyrics_file": "probe_q_lyrics.txt", "seed": 2640605763, "cap": 7000 } ] }
```

Note: `INFERENCE/songs.v3_probe_q.g15.json` already holds this exact entry — but it also carries Q5, so it would render two takes.

## The render command (Colab GPU VM only — `nvidia-smi` first, never overlap)

CPU validation first, no GPU: `EXTRA_REQUEST_OPTS="guidance_scale=1.5" python INFERENCE/generate.py INFERENCE/songs.v3_q1_g15.json --dry-run`

terminal: **detached** — survives Ctrl+C / closing the tab; log `/content/logs/v3_q1_g15.log`; stop `pkill -f songs.v3_q1_g15`; resume: rerun the same line (succeeded takes skip).

```bash
cd /content/maqamrock-yue2-lora-finetuning && git pull
gcloud storage rsync -r "$GCP_BACKUP_BASE/v3_arabmaqamrock_lora/convert" /content/converter/out
export EXTRA_REQUEST_OPTS="guidance_scale=1.5"
setsid nohup python INFERENCE/generate.py INFERENCE/songs.v3_q1_g15.json \
  --lora-ar /content/converter/out/v3_arabmaqamrock_lora_ar.safetensors \
  --lora-nar /content/converter/out/v3_arabmaqamrock_lora_nar.safetensors \
  --out-dir /content/audiocpp_inference/out/v3_q1_g15 --label v3_q1_g15 \
  > /content/logs/v3_q1_g15.log 2>&1 < /dev/null & disown
tail -f /content/logs/v3_q1_g15.log      # ~9 min/track
```

Two honest notes: the pick is **provisional** (n=1, anchor drifted ≈0.9 pt), so "best" means *best measured so far*; and I have **not** created that manifest or touched the repo — this is a proposal. Say the word and I'll write the manifest file (and nothing else), or you can just copy the file you already have.

Recipe + command are on `agent_notes/current.md`.