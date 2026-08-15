"""
generate_poem_html.py

Generate a styled RTL HTML page for any classical Arabic poem, given as a
list of (first_hemistich, second_hemistich) tuples.

This is a generalized version of a script that was originally hardcoded for
a single poet ("Amro bin Kalthoum"). Everything poem/poet specific is now
passed in as data instead of being baked into the code, so the same script
works for any poem, poet, title, or output path.

See README.md for usage examples and the CLI reference.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

Hemistich = Tuple[str, str]


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

@dataclass
class PoemMeta:
    """All the poem-specific text that used to be hardcoded in the template."""

    poet_name: str
    title: str
    subtitle: str = "✦ من روائع الشعر العربي ✦"
    footer_text: Optional[str] = None
    language: str = "ar"
    direction: str = "rtl"

    def resolved_footer(self) -> str:
        return self.footer_text or f"قال {self.poet_name}"


def slugify(text: str) -> str:
    """Turn a poet/title string into a safe filename fragment."""
    text = text.strip().replace(" ", "_")
    # Keep Arabic letters, ascii letters/digits, and underscores/dashes only.
    return re.sub(r"[^\w\-]", "", text, flags=re.UNICODE) or "poem"


# --------------------------------------------------------------------------- #
# HTML generation
# --------------------------------------------------------------------------- #

def _render_verses(poems: Sequence[Hemistich]) -> str:
    verses_html = ""
    for i, (first_hemistich, second_hemistich) in enumerate(poems, 1):
        verses_html += f"""
        <div class="verse">
            <div class="verse-number">{i}</div>
            <div class="hemistich first">{first_hemistich}</div>
            <div class="hemistich second">{second_hemistich}</div>
        </div>
        """
    return verses_html


def generate_html(
    poems: Sequence[Hemistich],
    meta: PoemMeta,
    output_file: Optional[str] = None,
) -> str:
    """
    Render `poems` into a styled HTML page described by `meta`.

    Parameters
    ----------
    poems: sequence of (first_hemistich, second_hemistich) tuples.
    meta: poet name, title, subtitle, footer, language, and text direction.
    output_file: path to write the HTML to. Defaults to "<slug(poet)>.html".

    Returns
    -------
    The path the HTML file was written to.
    """
    if output_file is None:
        output_file = f"{slugify(meta.poet_name)}.html"

    verses_html = _render_verses(poems)

    html_content = f"""<!DOCTYPE html>
<html lang="{meta.language}" dir="{meta.direction}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{meta.title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Amiri', 'Traditional Arabic', 'Times New Roman', serif;
            background: linear-gradient(145deg, #1a0a05 0%, #2d1810 50%, #1a0a05 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 30px;
        }}

        .container {{
            background: linear-gradient(180deg, #fdf6e3 0%, #f5e6c8 100%);
            max-width: 900px;
            width: 100%;
            padding: 50px 60px;
            border-radius: 30px;
            box-shadow:
                0 20px 60px rgba(0,0,0,0.8),
                0 0 0 3px #c49a6c,
                0 0 0 8px #8b6b4d,
                0 0 0 12px #5a3d2b;
            position: relative;
        }}

        .container::before {{
            content: "◈";
            position: absolute;
            top: -25px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 40px;
            color: #c49a6c;
            text-shadow: 0 4px 10px rgba(0,0,0,0.5);
        }}

        .title {{
            text-align: center;
            font-size: 32px;
            font-weight: bold;
            color: #4a2a1a;
            padding-bottom: 20px;
            margin-bottom: 30px;
            border-bottom: 3px double #8b6b4d;
            position: relative;
        }}

        .title::after {{
            content: "✧";
            position: absolute;
            bottom: -18px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 24px;
            color: #8b6b4d;
            background: #f5e6c8;
            padding: 0 15px;
        }}

        .subtitle {{
            text-align: center;
            font-size: 18px;
            color: #6b4f3a;
            margin-bottom: 40px;
            font-style: italic;
            letter-spacing: 2px;
        }}

        .verse {{
            display: grid;
            grid-template-columns: 40px 1fr 1fr;
            gap: 15px;
            align-items: center;
            padding: 18px 20px;
            margin-bottom: 12px;
            background: rgba(255, 248, 235, 0.7);
            border-radius: 15px;
            border-right: 4px solid #c49a6c;
            transition: all 0.3s ease;
        }}

        .verse:hover {{
            background: rgba(255, 248, 235, 0.95);
            transform: translateX(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
        }}

        .verse-number {{
            font-size: 20px;
            font-weight: bold;
            color: #8b6b4d;
            text-align: center;
            font-family: 'Times New Roman', serif;
            opacity: 0.6;
        }}

        .hemistich {{
            font-size: 24px;
            line-height: 1.8;
            color: #2d1810;
            padding: 5px 10px;
            text-align: center;
            font-weight: 500;
        }}

        .hemistich.first {{
            border-left: 2px dashed #c49a6c;
            padding-left: 20px;
        }}

        .hemistich.second {{
            padding-right: 20px;
        }}

        .hemistich::before {{
            content: "❝";
            font-size: 14px;
            color: #8b6b4d;
            opacity: 0.4;
            margin-left: 5px;
        }}

        .hemistich::after {{
            content: "❞";
            font-size: 14px;
            color: #8b6b4d;
            opacity: 0.4;
            margin-right: 5px;
        }}

        .footer {{
            text-align: center;
            margin-top: 35px;
            padding-top: 20px;
            border-top: 2px solid #d4b896;
            color: #6b4f3a;
            font-size: 16px;
            letter-spacing: 1px;
        }}

        .footer span {{
            display: inline-block;
            margin: 0 10px;
            color: #8b6b4d;
        }}

        @media (max-width: 700px) {{
            .container {{
                padding: 30px 20px;
            }}

            .verse {{
                grid-template-columns: 1fr;
                gap: 5px;
                text-align: center;
                padding: 15px;
            }}

            .verse-number {{
                font-size: 16px;
                margin-bottom: 5px;
            }}

            .hemistich {{
                font-size: 20px;
                line-height: 1.6;
            }}

            .hemistich.first {{
                border-left: none;
                border-bottom: 1px dashed #c49a6c;
                padding-left: 0;
                padding-bottom: 8px;
            }}

            .hemistich.second {{
                padding-right: 0;
                padding-top: 8px;
            }}

            .title {{
                font-size: 24px;
            }}
        }}

        @media print {{
            body {{
                background: white;
            }}
            .container {{
                box-shadow: none;
                border: 1px solid #ccc;
            }}
            .verse:hover {{
                transform: none;
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="title">{meta.title}</div>
        <div class="subtitle">{meta.subtitle}</div>

        {verses_html}

        <div class="footer">
            <span>◈</span>
            {meta.resolved_footer()}
            <span>◈</span>
        </div>
    </div>
</body>
</html>"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ تم إنشاء الملف: {output_file}")
    print(f"📍 المسار الكامل: {os.path.abspath(output_file)}")
    return output_file


# --------------------------------------------------------------------------- #
# Loading poems from a module (kept for backwards compatibility with the
# original "import poem_list from a sibling module" pattern)
# --------------------------------------------------------------------------- #

def load_poems_from_module(module_ref: str, list_name: str = "poem_list") -> List[Hemistich]:
    """
    Return the `list_name` attribute from `module_ref`, which can be either:

    - a dotted, importable module name, e.g. "amro_bin_kalthoum"
      (must be on sys.path / a proper package), or
    - a filesystem path to a .py file, e.g. "antar/suno_input/antar_poem.py"
      or "antar\\suno_input\\antar_poem.py" on Windows. Path form is used
      automatically whenever `module_ref` contains a path separator or ends
      in ".py" -- no package/__init__.py setup required.
    """
    looks_like_path = (
        module_ref.endswith(".py")
        or os.sep in module_ref
        or "/" in module_ref
        or "\\" in module_ref
    )

    if looks_like_path:
        # Normalize Windows-style backslashes even when running on
        # macOS/Linux, so the same --module value works cross-platform.
        normalized = module_ref.replace("\\", os.sep).replace("/", os.sep)
        path = normalized if normalized.endswith(".py") else normalized + ".py"
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"No such file: {path}")

        module_name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(module_ref)

    poems = getattr(module, list_name, None)
    if poems is None:
        raise AttributeError(
            f"Module '{module_ref}' has no attribute '{list_name}'"
        )
    return poems


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a styled HTML page for an Arabic poem."
    )
    parser.add_argument(
        "--module",
        required=True,
        help="Where the poem list lives: either an importable module name "
        "(e.g. 'amro_bin_kalthoum'), or a path to a .py file "
        "(e.g. 'antar/suno_input/antar_poem.py' or "
        "'antar\\suno_input\\antar_poem.py' on Windows).",
    )
    parser.add_argument(
        "--list-name",
        default="poem_list",
        help="Name of the variable inside --module holding the "
        "list of (first_hemistich, second_hemistich) tuples. Default: poem_list.",
    )
    parser.add_argument("--poet", required=True, help="Poet's name.")
    parser.add_argument(
        "--title", help="Page title. Defaults to 'قصيدة <poet>'."
    )
    parser.add_argument(
        "--subtitle",
        default="✦ من روائع الشعر العربي ✦",
        help="Subtitle shown under the title.",
    )
    parser.add_argument(
        "--footer",
        help="Footer text. Defaults to 'قال <poet>'.",
    )
    parser.add_argument(
        "--output",
        help="Output HTML file path. Defaults to '<slug(poet)>.html'.",
    )
    parser.add_argument(
        "--language", default="ar", help="HTML lang attribute. Default: ar."
    )
    parser.add_argument(
        "--direction",
        default="rtl",
        choices=["rtl", "ltr"],
        help="HTML dir attribute. Default: rtl.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    poems = load_poems_from_module(args.module, args.list_name)

    meta = PoemMeta(
        poet_name=args.poet,
        title=args.title or f"قصيدة {args.poet}",
        subtitle=args.subtitle,
        footer_text=args.footer,
        language=args.language,
        direction=args.direction,
    )

    generate_html(poems, meta, output_file=args.output)


if __name__ == "__main__":
    main()
