#!/usr/bin/env python3
"""
recompile_reviews.py — Regenerate full_review.md and full_review.pdf for all
existing review folders from the individual step files (02–05 only, no metrics).

Run once; does not re-invoke Claude.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from paper_reviewer import try_pdf_convert

REVIEWS_ROOT = Path(__file__).parent / "reviews"
INCLUDE_PREFIXES = ("02_", "03_", "04_", "05_")


def strip_stats_footer(text: str) -> str:
    """Remove the trailing ---\\n*Time: ...* block written by the reviewer."""
    return re.sub(
        r"\n\n---\n\*Time:[^\n]+\*\s*$",
        "",
        text,
        flags=re.MULTILINE,
    ).rstrip()


def extract_label(text: str) -> str:
    """Return the first # heading as the section label."""
    m = re.match(r"^#\s+(.+)", text.lstrip())
    return m.group(1).strip() if m else "Section"


def strip_top_heading(text: str) -> str:
    """Remove the first # heading line (we use ## label in the compiled doc)."""
    return re.sub(r"^#\s+[^\n]+\n?", "", text.lstrip(), count=1).lstrip()


def recompile_folder(folder: Path) -> bool:
    # Read conference from existing full_review.md if present, else fall back
    # to inferring from the step-5 filename.
    conference = "Unknown"
    existing = folder / "full_review.md"
    if existing.exists():
        m = re.search(r"^\*\*Conference:\*\*\s*(.+)", existing.read_text(encoding="utf-8"), re.MULTILINE)
        if m:
            conference = m.group(1).strip()
    else:
        for f in sorted(folder.glob("05_*.md")):
            # e.g. 05_conference_review___emnlp_2026.md → EMNLP 2026
            slug = f.stem[3:]  # drop "05_"
            slug = re.sub(r"^conference_review___", "", slug)
            conference = slug.replace("_", " ").title()

    # Collect step files 02–05 in order
    step_files = sorted(
        f for f in folder.glob("*.md")
        if any(f.name.startswith(p) for p in INCLUDE_PREFIXES)
    )
    if not step_files:
        return False

    paper_title = folder.name
    # Trim the timestamp suffix (e.g. "_20260509_155924")
    paper_title = re.sub(r"_\d{8}_\d{6}$", "", paper_title)
    paper_title = paper_title.replace("_", " ").replace("-", " ").strip()

    sections = [f"# Full Review: {paper_title}\n\n**Conference:** {conference}"]

    for step_file in step_files:
        raw = step_file.read_text(encoding="utf-8")
        label = extract_label(raw)
        body = strip_top_heading(raw)
        body = strip_stats_footer(body)
        sections.append(f"---\n\n## {label}\n\n{body}")

    md_path = folder / "full_review.md"
    md_path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")

    pdf = try_pdf_convert(md_path)
    return pdf is not None


def main() -> None:
    folders = sorted(d for d in REVIEWS_ROOT.iterdir() if d.is_dir())
    print(f"Found {len(folders)} review folders\n")
    ok = fail = 0
    for folder in folders:
        success = recompile_folder(folder)
        status = "OK  " if success else "FAIL"
        print(f"  {status}  {folder.name}")
        if success:
            ok += 1
        else:
            fail += 1
    print(f"\nDone: {ok} OK, {fail} failed")


if __name__ == "__main__":
    main()
