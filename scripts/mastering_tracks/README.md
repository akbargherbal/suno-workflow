# master_tracks.py

A command-line utility for mastering audio tracks against reference
track(s), built on top of [matchering](https://github.com/sergree/matchering)
(Matchering 2.0).

Give it a **target** (the track you want mastered) and one or more
**references** (a "wet" track you want it to sound like), and it produces
mastered version(s) of the target with matching RMS, frequency response,
peak amplitude, and stereo width.

## Requirements

- Python 3.8+
- `matchering` Python package
- `libsndfile` (Linux only)
- `ffmpeg` (optional, only needed for MP3 support)

## Installation

```bash
# Linux
sudo apt update && sudo apt -y install libsndfile1
python3 -m pip install -U matchering

# macOS / Windows
python -m pip install -U matchering
```

Optional, for MP3 read/write support:

```bash
sudo apt -y install ffmpeg   # Linux
```

Place `master_tracks.py` anywhere on your system, e.g. next to your tracks.

## Usage

The script has three subcommands: `single`, `batch`, and `compare`.

### `single` — one target, one reference

```bash
python3 master_tracks.py single TARGET REFERENCE OUTPUT [-b {16,24}]
```

| Argument         | Description                          |
|------------------|---------------------------------------|
| `TARGET`         | The track you want to master          |
| `REFERENCE`      | The track you want it to sound like   |
| `OUTPUT`         | Path to write the mastered file to    |
| `-b/--bit-depth` | `16` (default) or `24`                |

**Example:**

```bash
python3 master_tracks.py single my_song.wav reference_song.wav my_song_mastered.wav -b 24
```

### `batch` — many targets, one reference

Master every audio file (`.wav`, `.flac`, `.mp3`, `.aiff`, `.aif`) in a
folder against a single reference track — useful for making an entire
album sound consistent.

```bash
python3 master_tracks.py batch TARGET_DIR REFERENCE OUTPUT_DIR [-b {16,24}]
```

**Example:**

```bash
python3 master_tracks.py batch ./album ./reference.wav ./album_mastered -b 16
```

Each file is written to `OUTPUT_DIR/<original_name>_mastered.wav`. If one
track fails to process, batch mode logs the error and continues with the
rest.

### `compare` — one target, many references

Master a **single target against several candidate reference tracks**, so
you can listen back and pick whichever reference gave the best result.
Each output file is named `<reference>__<target>.wav`, prefixed with the
reference track that produced it.

References can be given either individually with `-r` or all at once from
a folder with `-d` (the two can also be combined):

```bash
# individually
python3 master_tracks.py compare TARGET OUTPUT_DIR -r REFERENCE1 -r REFERENCE2 [-r REFERENCE3 ...] [-b {16,24}]

# from a folder
python3 master_tracks.py compare TARGET OUTPUT_DIR -d REFERENCE_DIR [-b {16,24}]
```

At least two reference tracks total are required.

**Example — references listed one by one:**

```bash
python3 master_tracks.py compare my_song.wav ./comparisons \
    -r ref_a.wav \
    -r ref_b.wav \
    -r ref_c.wav \
    -b 24
```

**Example — all references in one folder:**

```bash
python3 master_tracks.py compare my_song.wav ./comparisons -d ./candidate_refs -b 24
```

`-d/--reference-dir` picks up every `.wav`, `.flac`, `.mp3`, `.aiff`, and
`.aif` file directly inside `REFERENCE_DIR` (non-recursive) and uses each
one as a reference. This produces:

```
comparisons/
├── ref_a__my_song.wav
├── ref_b__my_song.wav
└── ref_c__my_song.wav
```

Listen to each one against its reference and keep whichever sounds best.
If a listed reference file can't be found, `compare` logs an error for
that one and continues with the rest.

## Shared options

| Option        | Description                          |
|---------------|----------------------------------------|
| `-b/--bit-depth {16,24}` | Bit depth of mastered output, per subcommand (default: 16) |
| `-q/--quiet`  | Suppress progress logging (global flag, place after the subcommand's required args or before the subcommand) |

## Notes

- Reference tracks should be well-mastered, "wet" versions of the sound
  you're going for — results depend heavily on choosing a good reference.
  `compare` mode exists precisely because reference choice matters a lot,
  and it's often easier to judge by ear than to guess up front.
- All processing happens locally; no audio is uploaded anywhere.
- For advanced options (custom limiter settings, additional output
  formats, etc.), use the `matchering` Python API directly — see the
  [matchering examples directory](https://github.com/sergree/matchering/tree/master/examples).

## Testing

A pytest suite lives in `tests/`. It fakes out the `matchering` package
(no real audio processing, no dependency required) and covers
`build_results`, `master_one`, `master_batch`, `master_compare`, CLI
argument parsing, and `main()` end-to-end for all three subcommands.

```bash
python3 -m pip install pytest
python3 -m pytest -v
```

## License

This script is a thin CLI wrapper; matchering itself is licensed under
the GPLv3 (see the [upstream repository](https://github.com/sergree/matchering)
for details).
