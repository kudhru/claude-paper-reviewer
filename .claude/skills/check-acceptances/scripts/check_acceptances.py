#!/usr/bin/env python3
"""
check_acceptances.py — Find all accepted papers within a date range from OpenReview.

Usage:
    python check_acceptances.py report \
        --start-date 2025-01-01 \
        [--end-date 2026-06-01] \
        [--author EMAIL] \
        [--output-dir ./acceptance-reports] \
        [--config ./.openreview_config.json]
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import openreview


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


def _load_config(config_path: str) -> dict:
    p = Path(config_path).resolve()
    if not p.exists():
        print(f"Error: config file not found: {p}", file=sys.stderr)
        print(
            'Create it with:\n  { "username": "your-email", "password": "your-password", '
            '"baseurl": "https://api2.openreview.net" }',
            file=sys.stderr,
        )
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def _get_client(config: dict) -> openreview.api.OpenReviewClient:
    return openreview.api.OpenReviewClient(
        baseurl=config.get("baseurl", "https://api2.openreview.net"),
        username=config["username"],
        password=config["password"],
    )


def _get_title(note) -> str:
    if note.content:
        title_field = note.content.get("title", {})
        if isinstance(title_field, dict):
            return title_field.get("value", "")
        return str(title_field)
    return ""


def _get_venue_id(note) -> str:
    invitations = getattr(note, "invitations", None) or []
    for inv in invitations:
        if "/-/Submission" in inv or "/-/Blind_Submission" in inv:
            return inv.split("/-/")[0]
    return ""


def _classify_venue(venue_id: str) -> str:
    v = venue_id.lower()
    if "workshop" in v:
        return "workshop"
    if any(x in v for x in ["journal", "transactions", "tmlr", "tacl"]):
        return "journal"
    return "conference"


def _is_decision_note(note) -> bool:
    invitations = getattr(note, "invitations", None) or []
    return any("Decision" in inv for inv in invitations)


def _is_meta_review_note(note) -> bool:
    invitations = getattr(note, "invitations", None) or []
    return any("Meta_Review" in inv for inv in invitations)


def _extract_note_data(note) -> dict:
    content = note.content or {}
    result = {
        "id": note.id,
        "forum": note.forum,
        "cdate": getattr(note, "cdate", 0) or 0,
        "invitations": getattr(note, "invitations", None) or [],
    }
    for key, val in content.items():
        if isinstance(val, dict) and "value" in val:
            result[key] = val["value"]
        else:
            result[key] = val
    return result


_ACCEPT_STRINGS = [
    "accept",
    "main conference",   # ACL/EMNLP main track
    "findings",          # Findings of ACL/EMNLP
    "oral",              # NeurIPS/ICML oral
    "poster",            # NeurIPS/ICML poster
    "spotlight",         # NeurIPS/ICML spotlight
]

def _is_accept_decision(data: dict) -> bool:
    for key in ["decision", "recommendation", "acceptance"]:
        val = data.get(key, "")
        if not isinstance(val, str):
            continue
        v = val.lower()
        # Explicit reject always loses
        if v == "reject":
            continue
        if any(s in v for s in _ACCEPT_STRINGS):
            return True
    return False


def _get_decision_text(data: dict) -> str:
    for key in ["decision", "recommendation", "acceptance"]:
        val = data.get(key, "")
        if val:
            return str(val)
    return ""


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def cmd_report(args):
    config = _load_config(args.config)
    client = _get_client(config)
    author = args.author or config["username"]

    start_dt = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_date_str = args.end_date or datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=timezone.utc
    )
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Searching for all submissions by {author}...", file=sys.stderr)
    submissions = client.get_all_notes(content={"authorids": author})
    print(f"Found {len(submissions)} total submissions. Checking decisions...", file=sys.stderr)

    # paper_key (normalized title) -> paper record
    papers: dict[str, dict] = {}
    # Track (forum, venue_id) pairs already recorded to avoid double-counting
    # venues that post both a Meta_Review and a Decision note.
    recorded: set[tuple[str, str]] = set()

    for i, sub in enumerate(submissions, 1):
        title = _get_title(sub)
        venue_id = _get_venue_id(sub)
        if not venue_id:
            continue

        venue_type = _classify_venue(venue_id)
        paper_key = _normalize_title(title) if title else sub.forum

        print(f"  [{i}/{len(submissions)}] {title or '(no title)'} @ {venue_id}", file=sys.stderr)

        try:
            replies = client.get_all_notes(forum=sub.forum)
        except Exception as e:
            print(f"    Warning: could not fetch replies: {e}", file=sys.stderr)
            continue

        # Separate replies into Decision notes and Meta_Review notes.
        # Decision notes are the authoritative final verdict (set by program chairs).
        # Meta_Review notes are used only when no Decision note exists at all,
        # which is how EMNLP 2025 communicates acceptance. Using Meta_Review as
        # a fallback prevents "Borderline Findings" style intermediate
        # recommendations from being mistaken for acceptances when the final
        # Decision note says "Reject".
        decision_notes = [r for r in replies if r.id != sub.id and _is_decision_note(r)]
        verdict_notes = decision_notes or [r for r in replies if r.id != sub.id and _is_meta_review_note(r)]

        for reply in verdict_notes:
            data = _extract_note_data(reply)
            decision_cdate = data.get("cdate", 0)

            if not (start_ms <= decision_cdate <= end_ms):
                continue

            if not _is_accept_decision(data):
                continue

            decision_text = _get_decision_text(data)
            decision_date = datetime.fromtimestamp(
                decision_cdate / 1000, tz=timezone.utc
            ).strftime("%Y-%m-%d")

            record_key = (sub.forum, venue_id)
            if record_key in recorded:
                continue
            recorded.add(record_key)

            if paper_key not in papers:
                papers[paper_key] = {
                    "title": title,
                    "forum_ids": [],
                    "acceptances": [],
                }

            if sub.forum not in papers[paper_key]["forum_ids"]:
                papers[paper_key]["forum_ids"].append(sub.forum)

            papers[paper_key]["acceptances"].append({
                "venue": venue_id,
                "venue_type": venue_type,
                "decision": decision_text,
                "date": decision_date,
                "decision_note_id": reply.id,
            })
            print(f"    ACCEPTED: {decision_text} ({decision_date})", file=sys.stderr)

    all_papers = list(papers.values())

    workshop_papers = [p for p in all_papers if any(a["venue_type"] == "workshop" for a in p["acceptances"])]
    conference_papers = [p for p in all_papers if any(a["venue_type"] == "conference" for a in p["acceptances"])]
    journal_papers = [p for p in all_papers if any(a["venue_type"] == "journal" for a in p["acceptances"])]

    workshop_venues = sorted(set(
        a["venue"] for p in workshop_papers for a in p["acceptances"] if a["venue_type"] == "workshop"
    ))
    conference_venues = sorted(set(
        a["venue"] for p in conference_papers for a in p["acceptances"] if a["venue_type"] == "conference"
    ))
    journal_venues = sorted(set(
        a["venue"] for p in journal_papers for a in p["acceptances"] if a["venue_type"] == "journal"
    ))

    report = {
        "date_range": {"start": args.start_date, "end": end_date_str},
        "author": author,
        "total_unique_accepted_papers": len(all_papers),
        "by_type": {
            "workshop": {"unique_papers": len(workshop_papers), "venues": workshop_venues},
            "conference": {"unique_papers": len(conference_papers), "venues": conference_venues},
            "journal": {"unique_papers": len(journal_papers), "venues": journal_venues},
        },
        "papers": all_papers,
    }

    json_path = output_dir / "acceptance_report.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        "# Acceptance Report",
        "",
        f"**Author:** {author}",
        f"**Date range:** {args.start_date} to {end_date_str}",
        "",
        "## Summary",
        "",
        f"- **Total unique accepted papers:** {len(all_papers)}",
        f"- **Workshops:** {len(workshop_papers)} paper(s)",
    ]
    for v in workshop_venues:
        md_lines.append(f"  - {v}")
    md_lines += [f"- **Conferences:** {len(conference_papers)} paper(s)"]
    for v in conference_venues:
        md_lines.append(f"  - {v}")
    md_lines += [f"- **Journals:** {len(journal_papers)} paper(s)"]
    for v in journal_venues:
        md_lines.append(f"  - {v}")
    md_lines += ["", "## Paper-Level Detail", ""]

    for paper in sorted(all_papers, key=lambda p: p["title"].lower()):
        md_lines.append(f"### {paper['title'] or '(Untitled)'}")
        for acc in sorted(paper["acceptances"], key=lambda a: a["date"]):
            type_label = acc["venue_type"].upper()
            md_lines.append(f"- [{type_label}] {acc['venue']} — \"{acc['decision']}\" — {acc['date']}")
        md_lines.append("")

    md_path = output_dir / "acceptance_report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    pdf_path = try_pdf_convert(md_path)

    print(f"\nReport written to:")
    print(f"  JSON:     {json_path}")
    print(f"  Markdown: {md_path}")
    if pdf_path:
        print(f"  PDF:      {pdf_path}")
    else:
        print(f"  PDF:      skipped (Chrome and weasyprint both unavailable)")
    print(f"\n{'='*60}")
    print(f"SUMMARY: {args.start_date} to {end_date_str}")
    print(f"{'='*60}")
    print(f"Total unique accepted papers: {len(all_papers)}")
    print(f"Workshops:   {len(workshop_papers)} paper(s)")
    for v in workshop_venues:
        print(f"  - {v}")
    print(f"Conferences: {len(conference_papers)} paper(s)")
    for v in conference_venues:
        print(f"  - {v}")
    print(f"Journals:    {len(journal_papers)} paper(s)")
    for v in journal_venues:
        print(f"  - {v}")
    if not all_papers:
        print("No accepted papers found in this date range.")


def main():
    parser = argparse.ArgumentParser(
        description="Find all accepted papers within a date range from OpenReview."
    )
    parser.add_argument(
        "--config",
        default=".openreview_config.json",
        help="Path to OpenReview credentials JSON file",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    rp = sub.add_parser("report", help="Generate acceptance report for a date range")
    rp.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    rp.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD), defaults to today")
    rp.add_argument("--author", default=None, help="Author email (default: config username)")
    rp.add_argument("--output-dir", default="./acceptance-reports", help="Output directory")

    args = parser.parse_args()

    if args.command == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()
