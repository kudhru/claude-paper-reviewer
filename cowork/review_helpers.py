#!/usr/bin/env python3
"""
review_helpers.py — Deterministic Python helpers for the Cowork paper review workflow.

Claude calls this script via bash for all file operations so that no file I/O
logic is left to Claude's discretion.

Commands
--------
  init_paper     Create the output directory and initial state file.
  save_step      Write a single step response to a numbered .md file.
  compile        Assemble all step .md files into full_review.md.
  convert_pdf    Convert full_review.md to PDF.
  check_state    Print state JSON if in-progress file exists, else NONE.
  save_state     Write/overwrite the in-progress state JSON.
  load_state     Print the current state JSON.
  clear_state    Delete the in-progress state file.
  list_papers    List all PDF files in a directory.
  move_paper     Move source PDF into the output directory.
  build_prompt   Print the fully assembled prompt for a given step.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    result = text.lower()
    for ch in " &/()\\.,:;—–":
        result = result.replace(ch, "_")
    return result.strip("_")


def _state_path(reviews_dir: Path, paper_stem: str) -> Path:
    return reviews_dir / f"{paper_stem}_in_progress.json"


# ---------------------------------------------------------------------------
# PDF CSS + HTML builder
# ---------------------------------------------------------------------------

_PDF_CSS = """
@page { margin: 0.85in 1in 0.85in 1in; }
body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
       font-size: 11pt; line-height: 1.6; color: #24292f; }
h1 { font-size: 1.75em; border-bottom: 2px solid #d0d7de; padding-bottom: 0.3em;
     margin-top: 1.5em; margin-bottom: 0.6em; }
h2 { font-size: 1.35em; border-bottom: 1px solid #d0d7de; padding-bottom: 0.2em;
     margin-top: 1.4em; margin-bottom: 0.5em; }
h3 { font-size: 1.1em; margin-top: 1.1em; margin-bottom: 0.4em; }
p { margin: 0.5em 0; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10.5pt; }
th, td { border: 1px solid #d0d7de; padding: 6px 13px; text-align: left; vertical-align: top; }
th { background-color: #f6f8fa; font-weight: 600; }
tr:nth-child(even) td { background-color: #f6f8fa; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 1.4em 0; }
code { background-color: #f6f8fa; padding: 2px 5px; border-radius: 4px;
       font-size: 0.88em; font-family: "SFMono-Regular", Consolas, monospace; }
pre { background-color: #f6f8fa; border-radius: 6px; padding: 12px 16px; overflow-x: auto; }
pre code { background: none; padding: 0; }
blockquote { border-left: 4px solid #d0d7de; padding: 0 1em; color: #57606a; margin: 0.5em 0; }
ul, ol { padding-left: 2em; margin: 0.4em 0; }
li { margin: 0.2em 0; }
strong { font-weight: 600; }
a { color: #0969da; text-decoration: none; }
"""

_KATEX_VERSION = "0.16.11"


def _build_html(md_path: Path) -> str:
    try:
        import markdown as md_lib
    except ImportError:
        raise RuntimeError("pip install markdown --break-system-packages")
    text = md_path.read_text(encoding="utf-8")
    saved: list = []

    def _save(m):
        saved.append(m.group(0))
        return f"XMATHX{len(saved) - 1}XMATHX"

    text = re.sub(r'\$\$.+?\$\$', _save, text, flags=re.DOTALL)
    text = re.sub(r'(?<!\$)\$(?!\$).+?(?<!\$)\$(?!\$)', _save, text)
    html_body = md_lib.markdown(text, extensions=["tables", "fenced_code", "nl2br", "sane_lists", "attr_list"])
    for i, block in enumerate(saved):
        html_body = html_body.replace(f"XMATHX{i}XMATHX", block)
    cdn = f"https://cdn.jsdelivr.net/npm/katex@{_KATEX_VERSION}/dist"
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<link rel='stylesheet' href='{cdn}/katex.min.css'>"
        f"<script defer src='{cdn}/katex.min.js'></script>"
        f"<script defer src='{cdn}/contrib/auto-render.min.js' "
        f"onload=\"renderMathInElement(document.body,{{delimiters:["
        f"{{left:'$$',right:'$$',display:true}},{{left:'$',right:'$',display:false}}],"
        f"throwOnError:false}});\"></script>"
        f"<style>{_PDF_CSS}</style></head><body>{html_body}</body></html>"
    )


def try_pdf_convert(md_path: Path) -> Optional[Path]:
    pdf_path = md_path.with_suffix(".pdf")
    chrome_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "google-chrome", "chromium",
    ]
    try:
        html = _build_html(md_path)
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
            f.write(html)
            tmp_html = Path(f.name)
        try:
            for chrome in chrome_candidates:
                cmd = [chrome, "--headless=new", f"--print-to-pdf={pdf_path}",
                       "--print-to-pdf-no-header", "--no-sandbox", "--disable-gpu",
                       "--run-all-compositor-stages-before-draw", f"file://{tmp_html}"]
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
        import markdown as md_lib
        from weasyprint import HTML, CSS
        text = md_path.read_text(encoding="utf-8")
        html_body = md_lib.markdown(text, extensions=["tables", "fenced_code", "nl2br", "sane_lists"])
        html = f"<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>{html_body}</body></html>"
        HTML(string=html, base_url=str(md_path.parent)).write_pdf(str(pdf_path), stylesheets=[CSS(string=_PDF_CSS)])
        if pdf_path.exists():
            return pdf_path
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init_paper(args):
    reviews_dir = Path(args.reviews_dir)
    reviews_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    paper_stem = Path(args.abs_pdf).stem
    out_dir = reviews_dir / f"{paper_stem}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "paper_stem": paper_stem,
        "abs_pdf": args.abs_pdf,
        "conference": args.conference,
        "out_dir": str(out_dir),
        "completed_steps": []
    }
    _state_path(reviews_dir, paper_stem).write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(str(out_dir))


def cmd_save_step(args):
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    response = sys.stdin.read() if args.response == "-" else args.response
    fname = f"{int(args.step_id):02d}_{slugify(args.label)}.md"
    (out_dir / fname).write_text(f"# {args.label}\n\n{response}\n", encoding="utf-8")
    if args.state_file:
        state_file = Path(args.state_file)
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding="utf-8"))
            steps = [s for s in state.get("completed_steps", []) if s["id"] != int(args.step_id)]
            steps.append({"id": int(args.step_id), "label": args.label, "file": fname})
            state["completed_steps"] = sorted(steps, key=lambda s: s["id"])
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Saved: {fname}")


def cmd_compile(args):
    out_dir = Path(args.out_dir)
    skip_ids = {0, 1}
    md_files = sorted(out_dir.glob("[0-9][0-9]_*.md"))
    if not md_files:
        print("ERROR: No step .md files found.", file=sys.stderr)
        sys.exit(1)
    paper_title = Path(args.paper_stem).stem.replace("_", " ").replace("-", " ").title()
    sections = [f"# Full Review: {paper_title}\n\n**Conference:** {args.conference}"]
    for md_file in md_files:
        step_id = int(md_file.name[:2])
        if step_id in skip_ids:
            continue
        content = md_file.read_text(encoding="utf-8")
        lines = content.split("\n")
        heading = lines[0].lstrip("# ").strip() if lines else md_file.stem
        body = "\n".join(lines[2:]).strip()
        sections.append(f"---\n\n## {heading}\n\n{body}")
    compiled_md = out_dir / "full_review.md"
    compiled_md.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
    print(str(compiled_md))


def cmd_convert_pdf(args):
    md_path = Path(args.md_path)
    if not md_path.exists():
        print(f"ERROR: {md_path} not found.", file=sys.stderr)
        sys.exit(1)
    result = try_pdf_convert(md_path)
    print(str(result) if result else "FAILED")


def cmd_check_state(args):
    state_file = _state_path(Path(args.reviews_dir), args.paper_stem)
    print(state_file.read_text(encoding="utf-8") if state_file.exists() else "NONE")


def cmd_save_state(args):
    reviews_dir = Path(args.reviews_dir)
    reviews_dir.mkdir(parents=True, exist_ok=True)
    state_file = _state_path(reviews_dir, args.paper_stem)
    state_file.write_text(json.dumps(json.loads(args.state_json), indent=2), encoding="utf-8")
    print(f"State saved: {state_file}")


def cmd_load_state(args):
    state_file = _state_path(Path(args.reviews_dir), args.paper_stem)
    print(state_file.read_text(encoding="utf-8") if state_file.exists() else "NONE")


def cmd_clear_state(args):
    state_file = _state_path(Path(args.reviews_dir), args.paper_stem)
    if state_file.exists():
        state_file.unlink()
        print(f"Cleared: {state_file}")
    else:
        print("No state file found.")


def cmd_list_papers(args):
    papers_dir = Path(args.papers_dir)
    if not papers_dir.is_dir():
        print(f"ERROR: '{papers_dir}' is not a directory.", file=sys.stderr)
        sys.exit(1)
    pdfs = sorted(papers_dir.glob("*.pdf"))
    print("NONE") if not pdfs else [print(str(p.resolve())) for p in pdfs]


def cmd_move_paper(args):
    src = Path(args.src)
    out_dir = Path(args.out_dir)
    if src.exists():
        shutil.move(str(src), out_dir / src.name)
        print(f"Moved: {src.name} -> {out_dir.name}/")
    else:
        print(f"WARNING: source PDF not found at {src}")


def cmd_build_prompt(args):
    data = json.loads(Path(args.prompts_file).read_text(encoding="utf-8"))
    step_id = int(args.step_id)
    step = next((s for s in data["steps"] if s["id"] == step_id), None)
    if step is None:
        print(f"ERROR: step {step_id} not found.", file=sys.stderr)
        sys.exit(1)
    parts = []
    if step.get("prepend_style"):
        parts.append(data["style_instruction"])
    intro_type = step.get("paper_intro_type")
    if intro_type and args.pdf_path:
        parts.append(data["paper_intro"][intro_type].replace("{pdf_path}", args.pdf_path))
    text = step["text"]
    if step_id == 5:
        conference = args.conference or ""
        if args.novelty_file:
            synthesis = Path(args.novelty_file).read_text(encoding="utf-8").strip()
            novelty_block = data["novelty_block_prefix"].replace("{novelty_synthesis}", synthesis)
        else:
            novelty_block = ""
        text = text.replace("{novelty_block}", novelty_block).replace("{conference}", conference)
    parts.append(text)
    print("".join(parts))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Paper review workflow helpers.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init_paper")
    p.add_argument("--reviews-dir", required=True)
    p.add_argument("--abs-pdf", required=True)
    p.add_argument("--conference", required=True)

    p = sub.add_parser("save_step")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--step-id", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--response", required=True)
    p.add_argument("--state-file", default=None)

    p = sub.add_parser("compile")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--paper-stem", required=True)
    p.add_argument("--conference", required=True)

    p = sub.add_parser("convert_pdf")
    p.add_argument("--md-path", required=True)

    p = sub.add_parser("check_state")
    p.add_argument("--reviews-dir", required=True)
    p.add_argument("--paper-stem", required=True)

    p = sub.add_parser("save_state")
    p.add_argument("--reviews-dir", required=True)
    p.add_argument("--paper-stem", required=True)
    p.add_argument("--state-json", required=True)

    p = sub.add_parser("load_state")
    p.add_argument("--reviews-dir", required=True)
    p.add_argument("--paper-stem", required=True)

    p = sub.add_parser("clear_state")
    p.add_argument("--reviews-dir", required=True)
    p.add_argument("--paper-stem", required=True)

    p = sub.add_parser("list_papers")
    p.add_argument("--papers-dir", required=True)

    p = sub.add_parser("move_paper")
    p.add_argument("--src", required=True)
    p.add_argument("--out-dir", required=True)

    p = sub.add_parser("build_prompt")
    p.add_argument("--prompts-file", default="review_prompts.json")
    p.add_argument("--step-id", required=True)
    p.add_argument("--pdf-path", default=None)
    p.add_argument("--conference", default=None)
    p.add_argument("--novelty-file", default=None)

    args = parser.parse_args()
    {
        "init_paper":   cmd_init_paper,
        "save_step":    cmd_save_step,
        "compile":      cmd_compile,
        "convert_pdf":  cmd_convert_pdf,
        "check_state":  cmd_check_state,
        "save_state":   cmd_save_state,
        "load_state":   cmd_load_state,
        "clear_state":  cmd_clear_state,
        "list_papers":  cmd_list_papers,
        "move_paper":   cmd_move_paper,
        "build_prompt": cmd_build_prompt,
    }[args.command](args)


if __name__ == "__main__":
    main()
