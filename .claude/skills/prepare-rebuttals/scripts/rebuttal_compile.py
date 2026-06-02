#!/usr/bin/env python3
"""
rebuttal_compile.py — Compile rebuttal section files into rebuttal.md and convert to PDF.

Reads rebuttal_reviewer_*.md and common_themes.md from OUT_DIR, assembles them into
rebuttal.md with a header and reviewer scores summary, then converts to PDF.

Usage:
    python rebuttal_compile.py --out-dir OUT_DIR --meta-path META_PATH
"""

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


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
.reviewer-header { background-color: #f0f4f8; padding: 8px 12px; border-radius: 6px; margin: 1em 0 0.5em 0; }
"""


def _build_scores_table(raw_reviews: list[dict]) -> str:
    if not raw_reviews:
        return ""

    score_keys = ["rating", "soundness", "presentation", "contribution", "confidence", "overall_assessment"]
    present_keys = []
    for key in score_keys:
        if any(key in rev for rev in raw_reviews):
            present_keys.append(key)

    if not present_keys:
        return ""

    headers = ["Reviewer"] + [k.replace("_", " ").title() for k in present_keys]
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"

    rows = []
    for i, rev in enumerate(raw_reviews, 1):
        vals = [f"R{i}"]
        for key in present_keys:
            val = rev.get(key, "-")
            if isinstance(val, str) and len(val) > 20:
                val = val[:20] + "..."
            vals.append(str(val))
        rows.append("| " + " | ".join(vals) + " |")

    return "\n".join([header_line, sep_line] + rows)


def _build_html(md_path: Path) -> str:
    try:
        import markdown as md_lib
    except ImportError:
        raise RuntimeError("'markdown' Python package not installed. Run: pip install markdown")

    text = md_path.read_text(encoding="utf-8")

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


def try_pdf_convert(md_path: Path) -> Optional[Path]:
    pdf_path = md_path.with_suffix(".pdf")

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


def compile_rebuttal(out_dir: Path, meta: dict) -> Path:
    title = meta.get("title", "Unknown Paper")
    num_reviews = meta.get("num_reviews", 0)

    raw_reviews = []
    raw_reviews_path = out_dir / "raw_reviews.json"
    if raw_reviews_path.exists():
        raw_reviews = json.loads(raw_reviews_path.read_text(encoding="utf-8"))

    sections = []

    sections.append(f"# Rebuttal: {title}\n")

    scores_table = _build_scores_table(raw_reviews)
    if scores_table:
        sections.append("## Reviewer Scores Summary\n")
        sections.append(scores_table)

    rebuttal_files = sorted(out_dir.glob("rebuttal_reviewer_*.md"))
    for rb_file in rebuttal_files:
        content = rb_file.read_text(encoding="utf-8").strip()
        sections.append(f"\n---\n\n{content}")

    common_themes_path = out_dir / "common_themes.md"
    if common_themes_path.exists():
        content = common_themes_path.read_text(encoding="utf-8").strip()
        sections.append(f"\n---\n\n{content}")

    compiled_md = out_dir / "rebuttal.md"
    compiled_md.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    return compiled_md


def main():
    parser = argparse.ArgumentParser(
        description="Compile rebuttal files into rebuttal.md and convert to PDF."
    )
    parser.add_argument("--out-dir", required=True, help="Paper output directory")
    parser.add_argument("--meta-path", default=None, help="Path to meta.json (default: OUT_DIR/meta.json)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    if not out_dir.is_dir():
        raise SystemExit(f"Error: '{out_dir}' is not a directory.")

    meta_path = Path(args.meta_path) if args.meta_path else out_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta = {"title": out_dir.name, "num_reviews": 0}

    print(f"Compiling rebuttal in {out_dir} ...")
    compiled_md = compile_rebuttal(out_dir, meta)
    print(f"  Markdown : {compiled_md.name}")

    pdf = try_pdf_convert(compiled_md)
    if pdf:
        print(f"  PDF      : {pdf.name}")
    else:
        print("  PDF      : skipped (Chrome and weasyprint both unavailable)")


if __name__ == "__main__":
    main()
