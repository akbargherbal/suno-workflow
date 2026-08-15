#!/usr/bin/env python3
"""
generate_proofreading_html.py

Reads an AI-song-generation "workspace manifest" JSON file and produces a single,
self-contained HTML "proof-listening notebook" (styled after variation-3-proofreader.html)
so you can proofread lyrics/metadata for every track in a browser.

Usage:
    python generate_proofreading_html.py path/to/workspace_manifest.json
    python generate_proofreading_html.py path/to/workspace_manifest.json -o path/to/output_dir
    python generate_proofreading_html.py path/to/workspace_manifest.json -o path/to/output.html

Notes:
    - Tracks are sorted by `created_at`, oldest first.
    - The manifest path may be Windows- or POSIX-style, and may be wrapped in quotes
      (e.g. pasted via Windows' "Copy as path"). Both are handled automatically.
    - Use -o/--output to choose where the HTML file is saved (a directory or a full
      file path). If omitted, the HTML is written next to the input manifest.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path, PureWindowsPath


# --------------------------------------------------------------------------- #
# Path handling
# --------------------------------------------------------------------------- #

def normalize_user_path(raw: str) -> Path:
    """
    Turn a user-supplied path string into a usable pathlib.Path, regardless of
    whether it was typed/pasted in Windows or POSIX style, and regardless of
    whether it's wrapped in quotes (as with Windows' "Copy as path" feature).
    """
    cleaned = raw.strip()

    # Strip one layer of matching wrapping quotes (straight or "smart" quotes).
    quote_pairs = [('"', '"'), ("'", "'"), ("\u201c", "\u201d"), ("\u2018", "\u2019")]
    for left, right in quote_pairs:
        if len(cleaned) >= 2 and cleaned.startswith(left) and cleaned.endswith(right):
            cleaned = cleaned[1:-1].strip()
            break

    # PureWindowsPath understands both '\' and '/' as separators, and correctly
    # parses drive letters (C:\...), UNC paths, and plain POSIX-style paths alike.
    # This lets us robustly split the string into parts no matter which platform
    # style the user typed it in.
    parsed = PureWindowsPath(cleaned)
    parts = parsed.parts

    if parsed.drive:
        # Windows absolute path, e.g. D:\Music\...
        native = Path(parsed.drive + os.sep, *parts[1:])
    elif parsed.root:
        # POSIX-style absolute path, e.g. /home/user/...
        native = Path(os.sep, *parts[1:])
    else:
        # Relative path (may include a leading "~")
        native = Path(*parts) if parts else Path(cleaned)

    return native.expanduser()


def resolve_output_path(input_path: Path, workspace_name: str, output_arg: str | None) -> Path:
    """
    Decide where to write the generated HTML file.
      - If --output isn't given: save next to the input manifest.
      - If --output points at an existing directory (or clearly looks like one,
        i.e. has no file suffix): save the default filename inside it.
      - Otherwise: treat --output as the exact file path to write.
    """
    default_name = f"{sanitize_filename(workspace_name)} - Proofreading.html"

    if not output_arg:
        return input_path.parent / default_name

    out = normalize_user_path(output_arg)

    if out.exists() and out.is_dir():
        return out / default_name

    if out.suffix.lower() != ".html":
        # Looks like a directory the user wants created, not a file path.
        return out / default_name

    return out


def sanitize_filename(name: str) -> str:
    """Strip characters that are illegal in Windows/POSIX filenames."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
    return cleaned or "workspace"


# --------------------------------------------------------------------------- #
# Manifest loading / sorting
# --------------------------------------------------------------------------- #

def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Manifest file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_created_at(value: str):
    """Parse an ISO-8601 timestamp like '2026-07-25T21:11:12.298Z'."""
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min


def sorted_tracks(tracks: list[dict]) -> list[dict]:
    """Sort tracks by created_at, oldest to newest. Stable for ties."""
    return sorted(tracks, key=lambda t: parse_created_at(t.get("created_at", "")))


# --------------------------------------------------------------------------- #
# HTML building blocks
# --------------------------------------------------------------------------- #

SECTION_LABEL_RE = re.compile(r"^\[.*\]$")


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def build_lyrics_html(lyrics: str) -> str:
    """
    Render the lyrics body as blocks separated by blank lines. A block whose
    first line is a standalone "[...]" section marker gets a highlighted
    section-label; any remaining lines in that block (or all lines, if the
    first line isn't a bracketed marker) become individual lyric-line divs.
    """
    text = (lyrics or "").strip()
    if not text:
        return '<div class="empty">No lyrics / text generated.</div>'

    blocks = re.split(r"\n\s*\n", text)
    out = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue

        inner = ""
        if SECTION_LABEL_RE.match(lines[0]):
            inner += f'<div class="section-label">{esc(lines[0])}</div>'
            lines = lines[1:]

        for ln in lines:
            inner += f'<div class="lyric-line">{esc(ln)}</div>'

        out.append(f'<div class="lyric-block">{inner}</div>')

    return "".join(out)


def build_nav(tracks: list[dict]) -> str:
    items = []
    for i, t in enumerate(tracks, start=1):
        title = esc(t.get("original_title", ""))
        filename = esc(t.get("assigned_filename", ""))
        items.append(
            f'<a href="#track-{i}"><span>{i:02d}</span><b>{title}</b>'
            f'<small>{filename}</small></a>'
        )
    return "<nav>" + "".join(items) + "</nav>"


def build_generation_details(track: dict) -> str:
    styles = esc(track.get("styles", ""))
    block = (
        '<details class="generation">\n'
        '        <summary>Generation / style information</summary>\n'
        f'        <div class="prompt">{styles}</div>\n'
    )
    exclude_styles = (track.get("exclude_styles") or "").strip()
    if exclude_styles:
        block += (
            f"        <div class='subheading'>Excluded styles</div>"
            f"<div class='prompt'>{esc(exclude_styles)}</div>\n"
        )
    else:
        block += "        \n"
    block += "      </details>"
    return block


def build_article(index: int, track: dict) -> str:
    title = esc(track.get("original_title", ""))
    filename = esc(track.get("assigned_filename", ""))
    clip_id = esc(track.get("clip_id", ""))
    created_at = esc(track.get("created_at", ""))
    lyrics_raw = track.get("lyrics", "") or ""

    return f'''    <article id="track-{index}" class="card">
      <div class="cardtop">
        <span>TRACK {index:02d}</span>
      </div>

      <h2>{title}</h2>

      <div class="file-row">
        <code>{filename}</code>
        <button class="copy-btn copy-filename" data-copy="{filename}">Copy filename</button>
      </div>

      <details class="metadata" open>
        <summary>Track metadata</summary>
        <div class="meta-grid">
          <div class="meta-item">
            <label>clip_id</label>
            <div class="copy-field">
              <code>{clip_id}</code>
              <button class="copy-btn" data-copy="{clip_id}">Copy</button>
            </div>
          </div>
          <div class="meta-item">
            <label>original_title</label>
            <div class="copy-field">
              <code>{title}</code>
              <button class="copy-btn" data-copy="{title}">Copy</button>
            </div>
          </div>
          <div class="meta-item">
            <label>assigned_filename</label>
            <div class="copy-field">
              <code>{filename}</code>
              <button class="copy-btn" data-copy="{filename}">Copy</button>
            </div>
          </div>
          <div class="meta-item">
            <label>created_at</label>
            <div class="copy-field">
              <code>{created_at}</code>
              <button class="copy-btn" data-copy="{created_at}">Copy</button>
            </div>
          </div>
        </div>
      </details>

      {build_generation_details(track)}

      <div class="lyrics-head">
        <h3>Lyrics / input text</h3>
        <button class="copy-lyrics" data-lyrics="{esc(lyrics_raw)}">Copy lyrics</button>
      </div>
      <div class="lyrics">{build_lyrics_html(lyrics_raw)}</div>
    </article>'''


# --------------------------------------------------------------------------- #
# Full-page template (styling/script copied from variation-3-proofreader.html)
# --------------------------------------------------------------------------- #

PAGE_TEMPLATE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg:#eee9df;
  --paper:#fffdf8;
  --ink:#292722;
  --muted:#817a6f;
  --rule:#d8d0c3;
  --accent:#9a4f2d;
  --accent-soft:#f0e1d8;
  --button:#f4efe7;
}}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{
  margin:0;
  background:var(--bg);
  color:var(--ink);
  font-family:Georgia,"Times New Roman",serif;
}}
.shell {{
  display:grid;
  grid-template-columns:280px 1fr;
  min-height:100vh;
  transition:grid-template-columns .25s ease;
}}
.shell.collapsed {{
  grid-template-columns:0 1fr;
}}
aside {{
  position:sticky;
  top:0;
  height:100vh;
  padding:38px 24px;
  border-right:1px solid var(--rule);
  overflow:auto;
  transition:padding .2s ease, opacity .2s ease;
}}
.shell.collapsed aside {{
  padding:0;
  opacity:0;
  pointer-events:none;
}}
.sidebar-toggle {{
  position:fixed;
  top:18px;
  left:256px;
  z-index:30;
  width:30px;
  height:30px;
  border-radius:50%;
  border:1px solid var(--rule);
  background:var(--paper);
  color:var(--accent);
  font:700 14px system-ui,sans-serif;
  display:flex;
  align-items:center;
  justify-content:center;
  cursor:pointer;
  box-shadow:0 2px 10px #5d493030;
  transition:left .25s ease;
}}
.sidebar-toggle:hover {{
  background:var(--accent-soft);
}}
.shell.collapsed + .sidebar-toggle {{
  left:14px;
}}
.kicker {{
  font:700 10px system-ui,sans-serif;
  letter-spacing:.16em;
  text-transform:uppercase;
  color:var(--accent);
}}
h1 {{
  font-size:30px;
  line-height:1.05;
  margin:9px 0 12px;
}}
.stats {{
  font:12px/1.7 system-ui,sans-serif;
  color:var(--muted);
  margin-bottom:28px;
}}
nav {{ display:grid; gap:4px; }}
nav a {{
  display:grid;
  grid-template-columns:27px 1fr;
  gap:8px;
  padding:9px 8px;
  color:var(--ink);
  text-decoration:none;
  border-radius:7px;
  font-size:13px;
}}
nav a:hover {{ background:#e2dbcf; }}
nav span {{
  font:700 10px system-ui,sans-serif;
  color:var(--accent);
  padding-top:3px;
}}
nav b {{ font-weight:600; }}
nav small {{
  grid-column:2;
  color:var(--muted);
  font:10px system-ui,sans-serif;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}}
main {{
  max-width:930px;
  width:100%;
  margin:auto;
  padding:56px 34px 100px;
}}
.card {{
  background:var(--paper);
  border:1px solid var(--rule);
  padding:30px 34px 34px;
  margin:0 0 24px;
  box-shadow:0 8px 30px #5d493020;
  scroll-margin-top:24px;
}}
.cardtop {{
  display:flex;
  justify-content:space-between;
  font:700 10px system-ui,sans-serif;
  letter-spacing:.12em;
  color:var(--accent);
}}
h2 {{
  font-size:28px;
  line-height:1.15;
  margin:12px 0 5px;
}}
.file-row {{
  display:flex;
  align-items:center;
  gap:9px;
  margin-bottom:22px;
}}
.file-row code {{
  flex:1;
  font:11px ui-monospace,SFMono-Regular,Menlo,monospace;
  color:var(--muted);
  word-break:break-all;
}}
button {{
  cursor:pointer;
  border:1px solid var(--rule);
  background:var(--button);
  color:#5f584e;
  border-radius:6px;
  padding:6px 9px;
  font:600 10px system-ui,sans-serif;
}}
button:hover {{
  background:var(--accent-soft);
  color:var(--accent);
  border-color:#c8a28e;
}}
button.copied {{
  color:#52714f;
  border-color:#a9bea4;
  background:#edf3eb;
}}
details {{
  border-top:1px solid var(--rule);
  padding:11px 0;
}}
summary {{
  cursor:pointer;
  font:700 11px system-ui,sans-serif;
  color:#6e665b;
  text-transform:uppercase;
  letter-spacing:.08em;
  user-select:none;
}}
.meta-grid {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:10px 14px;
  padding:15px 0 5px;
}}
.meta-item {{
  border:1px solid #e3dbd0;
  background:#fbf7f0;
  border-radius:7px;
  padding:10px;
}}
.meta-item label {{
  display:block;
  font:700 9px system-ui,sans-serif;
  letter-spacing:.08em;
  color:var(--accent);
  margin-bottom:6px;
}}
.copy-field {{
  display:flex;
  gap:7px;
  align-items:center;
}}
.copy-field code {{
  flex:1;
  min-width:0;
  font:11px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;
  overflow-wrap:anywhere;
}}
.generation .prompt {{
  white-space:pre-wrap;
  font:12px/1.65 ui-monospace,SFMono-Regular,Menlo,monospace;
  color:#4c4841;
  padding:12px 0 3px;
}}
.subheading {{
  font:700 9px system-ui,sans-serif;
  color:var(--accent);
  text-transform:uppercase;
  letter-spacing:.08em;
  margin-top:14px;
}}
.lyrics-head {{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:15px;
  margin-top:25px;
  border-bottom:1px solid var(--rule);
  padding-bottom:9px;
}}
.lyrics-head h3 {{
  margin:0;
  font:700 11px system-ui,sans-serif;
  color:#6e665b;
  text-transform:uppercase;
  letter-spacing:.08em;
}}
.lyrics {{
  margin-top:20px;
  direction:rtl;
  text-align:right;
  font-family:"Noto Serif Arabic","Amiri",Georgia,serif;
  font-size:21px;
  line-height:2.1;
}}
.lyric-block {{ margin-bottom:25px; }}
.section-label {{
  font-family:system-ui,sans-serif;
  direction:ltr;
  text-align:left;
  font-size:11px;
  color:var(--accent);
  font-weight:700;
  margin:6px 0;
}}
.lyric-line {{ min-height:1.15em; }}
.empty {{
  font:13px system-ui,sans-serif;
  color:var(--muted);
  direction:ltr;
  text-align:left;
  font-style:italic;
}}
@media(max-width:850px) {{
  .shell {{ display:block; }}
  aside {{
    position:static;
    height:auto;
    border-right:0;
    border-bottom:1px solid var(--rule);
  }}
  .shell.collapsed aside {{
    display:none;
  }}
  .sidebar-toggle {{
    left:14px !important;
    top:14px;
  }}
  main {{ padding:30px 16px 70px; }}
  .card {{ padding:24px 20px; }}
}}
@media(max-width:620px) {{
  .meta-grid {{ grid-template-columns:1fr; }}
  .file-row {{ align-items:flex-start; }}
  .file-row button {{ flex:none; }}
}}
</style>
</head>
<body>
<div class="shell" id="shell">
<aside>
  <div class="kicker">Proof-listening notebook</div>
  <h1>{workspace_name}</h1>
  <div class="stats">
    {total_tracks} tracks<br>
    Generated {generated_on}
  </div>
  {nav}
</aside>

<main>
{articles}
    </main>
</div>
<button id="sidebar-toggle" class="sidebar-toggle" type="button" aria-expanded="true" aria-controls="shell" title="Hide sidebar">&#9776;</button>

<script>
(function () {{
  var shell = document.getElementById("shell");
  var toggle = document.getElementById("sidebar-toggle");
  toggle.addEventListener("click", function () {{
    var collapsed = shell.classList.toggle("collapsed");
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.title = collapsed ? "Show sidebar" : "Hide sidebar";
  }});
}})();
function flash(button) {{
  const old = button.textContent;
  button.textContent = "Copied";
  button.classList.add("copied");
  setTimeout(() => {{
    button.textContent = old;
    button.classList.remove("copied");
  }}, 1100);
}}

async function copyText(text, button) {{
  try {{
    await navigator.clipboard.writeText(text);
    flash(button);
  }} catch (err) {{
    const area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    flash(button);
  }}
}}

document.querySelectorAll("[data-copy]").forEach(button => {{
  button.addEventListener("click", () => copyText(button.dataset.copy, button));
}});

document.querySelectorAll(".copy-lyrics").forEach(button => {{
  button.addEventListener("click", () => copyText(button.dataset.lyrics, button));
}});
</script>
</body>
</html>
'''


def build_html(manifest: dict, tracks: list[dict]) -> str:
    workspace_name = manifest.get("workspace_name", "Workspace")
    generated_on = manifest.get("generated_on", "")

    articles = "\n    \n".join(
        build_article(i, t) for i, t in enumerate(tracks, start=1)
    )

    return PAGE_TEMPLATE.format(
        title=f"{esc(workspace_name)} — Proofreading",
        workspace_name=esc(workspace_name),
        total_tracks=len(tracks),
        generated_on=esc(generated_on),
        nav=build_nav(tracks),
        articles=articles,
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a proof-listening HTML notebook from a workspace_manifest.json file."
    )
    parser.add_argument(
        "manifest_path",
        help="Path to workspace_manifest.json (Windows or POSIX style, quotes okay).",
    )
    parser.add_argument(
        "-o", "--output",
        dest="output",
        default=None,
        help="Where to save the HTML file: a directory, or a full file path. "
             "Defaults to the same folder as the manifest.",
    )
    args = parser.parse_args(argv)

    try:
        manifest_path = normalize_user_path(args.manifest_path)
        manifest = load_manifest(manifest_path)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: could not parse JSON in {manifest_path}: {e}", file=sys.stderr)
        return 1

    tracks = sorted_tracks(manifest.get("tracks", []))
    html_out = build_html(manifest, tracks)

    output_path = resolve_output_path(
        manifest_path, manifest.get("workspace_name", "Workspace"), args.output
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_out, encoding="utf-8")

    print(f"Wrote {len(tracks)} tracks to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
