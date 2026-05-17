#!/usr/bin/env python3
"""
paper_review_compile.py — Compile step files into full_review.md and convert to PDF.

Reads numbered step files (00_*.md ... 05_*.md) from OUT_DIR, skips steps 0 and 1
(Prompt Injection Check and Paper Explanation), and assembles the rest into full_review.md.
Then attempts PDF conversion via Chrome headless (primary) or weasyprint (fallback).

Usage:
    python paper_review_compile.py --out-dir OUT_DIR --paper-stem STEM --conference "CONF NAME"
"""

import argparse
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Steps to exclude from the compiled review
# ---------------------------------------------------------------------------

SKIP_STEP_NUMS = {0, 1}  # Prompt Injection Check, Paper Explanation


# ---------------------------------------------------------------------------
# PDF CSS and KaTeX version (kept in sync with paper_reviewer_v2.py)
# ---------------------------------------------------------------------------

_KATEX_VERSION = "0.16.11"

_PDF_CSS = """
@page { margin: 0.85in 1in 0.85in 1in; }
body {
    font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #24292f;
}
h1 { font-size: 1.75em; border-bottom: 2px solid #d0d7de; padding-bottom: 0.3em; margin-top: 1.5em; margin-bottom: 0.6em; }
h2 { font-size: 1.35em; border-bottom: 1px solid #d0d7de; padding-bottom: 0.2em; margin-top: 1.4em; margin-bottom: 0.5em; }
h3 { font-size: 1.1em; margin-top: 1.1em; margin-bottom: 0.4em; }
h4 { font-size: 1em; margin-top: 0.9em; margin-bottom: 0.3em; }
p { margin: 0.5em 0; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10.5pt; }
th, td { border: 1px solid #d0d7de; padding: 6px 13px; text-align: left; vertical-align: top; }
th { background-color: #f6f8fa; font-weight: 600; }
tr:nth-child(even) td { background-color: #f6f8fa; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 1.4em 0; }
code {
    background-color: #f6f8fa;
    padding: 2px 5px;
    border-radius: 4px;
    font-size: 0.88em;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
}
pre { background-color: #f6f8fa; border-radius: 6px; padding: 12px 16px; overflow-x: auto; }
pre code { background: none; padding: 0; font-size: 0.88em; }
blockquote { border-left: 4px solid #d0d7de; padding: 0 1em; color: #57606a; margin: 0.5em 0; }
ul, ol { padding-left: 2em; margin: 0.4em 0; }
li { margin: 0.2em 0; }
li > ul, li > ol { margin: 0.1em 0; }
em { color: #57606a; }
strong { font-weight: 600; }
a { color: #0969da; text-decoration: none; }
"""


# ---------------------------------------------------------------------------
# HTML builder (Markdown → HTML with KaTeX math support)
# ---------------------------------------------------------------------------

def _build_html(md_path: Path) -> str:
    try:
        import markdown as md_lib
    except ImportError:
        raise RuntimeError("'markdown' Python package not installed. Run: pip install markdown")

    text = md_path.read_text(encoding="utf-8")

    # Protect math blocks from Markdown's italic/bold processing.
    saved: list[str] = []

    def _save(m: re.Match) -> str:
        saved.append(m.group(0))
        return f"XMATHX{len(saved) - 1}XMATHX"

    text = re.sub(r'\$\$.+?\$\$', _save, text, flags=re.DOTALL)
    text = re.sub(r'(?<!\$)\$(?!\$).+?(?<!\$)\$(?!\$)', _save, text)

    html_body = md_lib.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br", "sane_lists", "attr_list"],
    )

    for i, block in enumerate(saved):
        html_body = html_body.replace(f"XMATHX{i}XMATHX", block)

    cdn = f"https://cdn.jsdelivr.net/npm/katex@{_KATEX_VERSION}/dist"
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="{cdn}/katex.min.css">
<script defer src="{cdn}/katex.min.js"></script>
<script defer src="{cdn}/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body, {{
    delimiters: [
      {{left: '$$', right: '$$', display: true}},
      {{left: '$',  right: '$',  display: false}}
    ],
    throwOnError: false
  }});"></script>
<style>{_PDF_CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""


# ---------------------------------------------------------------------------
# PDF conversion (Chrome headless primary, weasyprint fallback)
# ---------------------------------------------------------------------------

def try_pdf_convert(md_path: Path) -> Optional[Path]:
    pdf_path = md_path.with_suffix(".pdf")

    # Primary: Chrome headless
    chrome_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "google-chrome",
        "chromium",
    ]
    try:
        html = _build_html(md_path)
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(html)
            tmp_html = Path(f.name)
        try:
            for chrome in chrome_candidates:
                cmd = [
                    chrome,
                    "--headless=new",
                    f"--print-to-pdf={pdf_path}",
                    "--print-to-pdf-no-header",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--run-all-compositor-stages-before-draw",
                    f"file://{tmp_html}",
                ]
                try:
                    r = subprocess.run(cmd, capture_output=True, timeout=60)
                    if r.returncode == 0 and pdf_path.exists():
                        return pdf_path
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
        finally:
            tmp_html.unlink(missing_ok=True)
    except Exception:
        pass

    # Fallback: weasyprint
    try:
        import ctypes
        for _lib in ["/opt/homebrew/lib/libpango-1.0.0.dylib",
                     "/opt/homebrew/lib/libpangocairo-1.0.0.dylib"]:
            try:
                ctypes.CDLL(_lib)
            except OSError:
                pass
        import markdown as md_lib
        from weasyprint import HTML, CSS
        text = md_path.read_text(encoding="utf-8")
        html_body = md_lib.markdown(
            text,
            extensions=["tables", "fenced_code", "nl2br", "sane_lists", "attr_list"],
        )
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
            f"<body>{html_body}</body></html>"
        )
        HTML(string=html, base_url=str(md_path.parent)).write_pdf(
            str(pdf_path), stylesheets=[CSS(string=_PDF_CSS)]
        )
        if pdf_path.exists():
            return pdf_path
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Compile step files into full_review.md
# ---------------------------------------------------------------------------

def compile_review(out_dir: Path, paper_stem: str, conference: str) -> Path:
    step_files = sorted(out_dir.glob("[0-9][0-9]_*.md"))
    paper_title = paper_stem.replace("_", " ").replace("-", " ").title()

    sections = [
        f"# Full Review: {paper_title}\n\n**Conference:** {conference}"
    ]

    for step_file in step_files:
        step_num = int(step_file.name[:2])
        if step_num in SKIP_STEP_NUMS:
            continue

        content = step_file.read_text(encoding="utf-8")

        # Strip the leading "# Label\n\n" header — the compiled doc adds its own ## headers.
        lines = content.split("\n", 2)
        if lines[0].startswith("# ") and len(lines) >= 3:
            label = lines[0][2:]
            response = lines[2].rstrip()
        else:
            label = step_file.stem
            response = content.rstrip()

        sections.append(f"---\n\n## {label}\n\n{response}")

    compiled_md = out_dir / "full_review.md"
    compiled_md.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    return compiled_md


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile paper review step files into full_review.md and convert to PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example:\n"
            "  python paper_review_compile.py \\\n"
            "      --out-dir ./reviews/foo_20260517_143000 \\\n"
            "      --paper-stem foo \\\n"
            "      --conference 'ACL 2026'\n"
        ),
    )
    parser.add_argument("--out-dir", required=True, metavar="DIR",
                        help="Review output directory containing the step .md files")
    parser.add_argument("--paper-stem", required=True, metavar="STEM",
                        help="PDF filename without the .pdf extension")
    parser.add_argument("--conference", required=True, metavar="NAME",
                        help="Conference or venue name (e.g. 'ACL 2026')")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    if not out_dir.is_dir():
        raise SystemExit(f"Error: '{out_dir}' is not a directory.")

    print(f"Compiling review in {out_dir} ...")
    compiled_md = compile_review(out_dir, args.paper_stem, args.conference)
    print(f"  Markdown : {compiled_md.name}")

    pdf = try_pdf_convert(compiled_md)
    if pdf:
        print(f"  PDF      : {pdf.name}")
    else:
        print("  PDF      : skipped (Chrome and weasyprint both unavailable)")


if __name__ == "__main__":
    main()
