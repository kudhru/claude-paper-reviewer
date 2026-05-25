#!/usr/bin/env python3
"""
review_compile.py — Compile all review data for a paper into reviews.md and convert to PDF.

Reads official reviews, meta-reviews, decisions, author responses, and comments
from a paper directory and assembles them into a single compiled document.

Usage:
    python review_compile.py --paper-dir PAPER_DIR
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
"""


def _build_scores_table(reviews: list[dict]) -> str:
    if not reviews:
        return ""

    score_keys = [
        "rating", "soundness", "presentation", "contribution",
        "confidence", "overall_assessment",
    ]
    present_keys = [k for k in score_keys if any(k in rev for rev in reviews)]

    if not present_keys:
        return ""

    headers = ["Reviewer"] + [k.replace("_", " ").title() for k in present_keys]
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"

    rows = []
    for i, rev in enumerate(reviews, 1):
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

    text = re.sub(r"\$\$.+?\$\$", _save, text, flags=re.DOTALL)
    text = re.sub(r"(?<!\$)\$(?!\$).+?(?<!\$)\$(?!\$)", _save, text)

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

        for _lib in [
            "/opt/homebrew/lib/libpango-1.0.0.dylib",
            "/opt/homebrew/lib/libpangocairo-1.0.0.dylib",
        ]:
            try:
                ctypes.CDLL(_lib)
            except OSError:
                pass
        import markdown as md_lib
        from weasyprint import CSS, HTML

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


def compile_reviews(paper_dir: Path, meta: dict) -> Path:
    title = meta.get("title", "Unknown Paper")
    decision = meta.get("decision", "")

    raw_data = {}
    raw_data_path = paper_dir / "raw_data.json"
    if raw_data_path.exists():
        raw_data = json.loads(raw_data_path.read_text(encoding="utf-8"))

    sections = []

    sections.append(f"# Reviews: {title}\n")
    if decision:
        sections.append(f"**Decision:** {decision}\n")

    official_reviews = raw_data.get("official_review", [])
    scores_table = _build_scores_table(official_reviews)
    if scores_table:
        sections.append("## Reviewer Scores Summary\n")
        sections.append(scores_table)

    review_files = sorted(paper_dir.glob("review_*.txt"))
    if review_files:
        sections.append("\n---\n")
        sections.append("## Official Reviews\n")
        for f in review_files:
            content = f.read_text(encoding="utf-8").strip()
            sections.append(content)
            sections.append("")

    meta_review_files = sorted(paper_dir.glob("meta_review*.txt"))
    if meta_review_files:
        sections.append("\n---\n")
        sections.append("## Meta Review\n")
        for f in meta_review_files:
            content = f.read_text(encoding="utf-8").strip()
            sections.append(content)
            sections.append("")

    decision_files = sorted(paper_dir.glob("decision*.txt"))
    if decision_files:
        sections.append("\n---\n")
        sections.append("## Decision\n")
        for f in decision_files:
            content = f.read_text(encoding="utf-8").strip()
            sections.append(content)
            sections.append("")

    ethics_files = sorted(paper_dir.glob("ethics_review*.txt"))
    if ethics_files:
        sections.append("\n---\n")
        sections.append("## Ethics Review\n")
        for f in ethics_files:
            content = f.read_text(encoding="utf-8").strip()
            sections.append(content)
            sections.append("")

    response_files = sorted(paper_dir.glob("author_response*.txt"))
    if response_files:
        sections.append("\n---\n")
        sections.append("## Author Responses\n")
        for f in response_files:
            content = f.read_text(encoding="utf-8").strip()
            sections.append(content)
            sections.append("")

    comment_files = sorted(paper_dir.glob("comment_*.txt"))
    if comment_files:
        sections.append("\n---\n")
        sections.append("## Official Comments\n")
        for f in comment_files:
            content = f.read_text(encoding="utf-8").strip()
            sections.append(content)
            sections.append("")

    public_comment_files = sorted(paper_dir.glob("public_comment_*.txt"))
    if public_comment_files:
        sections.append("\n---\n")
        sections.append("## Public Comments\n")
        for f in public_comment_files:
            content = f.read_text(encoding="utf-8").strip()
            sections.append(content)
            sections.append("")

    compiled_md = paper_dir / "reviews.md"
    compiled_md.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return compiled_md


def main():
    parser = argparse.ArgumentParser(
        description="Compile review data into reviews.md and convert to PDF."
    )
    parser.add_argument("--paper-dir", required=True, help="Paper directory")
    args = parser.parse_args()

    paper_dir = Path(args.paper_dir).resolve()
    if not paper_dir.is_dir():
        raise SystemExit(f"Error: '{paper_dir}' is not a directory.")

    meta_path = paper_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta = {"title": paper_dir.name}

    print(f"Compiling reviews in {paper_dir} ...")
    compiled_md = compile_reviews(paper_dir, meta)
    print(f"  Markdown : {compiled_md.name}")

    pdf = try_pdf_convert(compiled_md)
    if pdf:
        print(f"  PDF      : {pdf.name}")
    else:
        print("  PDF      : skipped (Chrome and weasyprint both unavailable)")


if __name__ == "__main__":
    main()
