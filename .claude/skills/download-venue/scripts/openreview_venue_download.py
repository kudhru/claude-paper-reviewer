#!/usr/bin/env python3
"""
openreview_venue_download.py — Download papers and all associated data from OpenReview.

Subcommands:
    list-venues   Discover all venues where the author has submissions
    download      Download PDFs + all review data for a single venue

Usage:
    python openreview_venue_download.py list-venues [--author EMAIL]
    python openreview_venue_download.py download \
        --venue "ICLR.cc/2025/Conference" \
        --venue-type conference \
        --output-dir ./openreview-data \
        [--author EMAIL]
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import openreview


def _load_config(config_path: str) -> dict:
    p = Path(config_path).resolve()
    if not p.exists():
        print(f"Error: config file not found: {p}", file=sys.stderr)
        print(
            "Create it with:\n"
            '  { "username": "your-email", "password": "your-password", '
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


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    if len(slug) > 80:
        slug = slug[:80].rstrip("_")
    return slug


def _extract_note_data(note) -> dict:
    content = note.content or {}
    result = {"id": note.id, "forum": note.forum}
    invitations = getattr(note, "invitations", None) or []
    result["invitations"] = invitations
    for key, val in content.items():
        if isinstance(val, dict) and "value" in val:
            result[key] = val["value"]
        else:
            result[key] = val
    return result


def _classify_reply(note) -> str:
    invitations = getattr(note, "invitations", None) or []
    inv_str = " ".join(invitations)

    if "Decision" in inv_str:
        return "decision"
    if "Meta_Review" in inv_str:
        return "meta_review"
    if "Ethics_Review" in inv_str:
        return "ethics_review"
    if "Official_Review" in inv_str:
        return "official_review"
    if "Rebuttal" in inv_str:
        return "author_response"
    if "Official_Comment" in inv_str:
        return "comment"
    if "Public_Comment" in inv_str:
        return "public_comment"
    return "other"


def _get_title(note) -> str:
    if note.content:
        title_field = note.content.get("title", {})
        if isinstance(title_field, dict):
            return title_field.get("value", "")
        return str(title_field)
    return ""


def _format_official_review(data: dict, index: int) -> str:
    lines = [f"=== Official Review {index} ===\n"]

    score_keys = [
        "rating", "soundness", "presentation", "contribution",
        "confidence", "overall_assessment",
    ]
    for key in score_keys:
        if key in data:
            label = key.replace("_", " ").title()
            lines.append(f"{label}: {data[key]}")
    lines.append("")

    text_keys = [
        "summary", "review", "main_review", "strengths_and_weaknesses",
        "strengths", "weaknesses", "questions",
        "limitations", "ethical_concerns", "suggestions",
        "requested_changes", "minor_comments",
    ]
    for key in text_keys:
        if key in data and data[key]:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(data[key]))
            lines.append("")

    known_keys = set(score_keys + text_keys + ["id", "forum", "invitations"])
    for key, val in data.items():
        if key not in known_keys and val:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(val))
            lines.append("")

    return "\n".join(lines)


def _format_meta_review(data: dict) -> str:
    lines = ["=== Meta Review ===\n"]

    for key in ["recommendation", "metareview", "meta_review", "summary", "confidence"]:
        if key in data and data[key]:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(data[key]))
            lines.append("")

    known_keys = {
        "recommendation", "metareview", "meta_review", "summary",
        "confidence", "id", "forum", "invitations",
    }
    for key, val in data.items():
        if key not in known_keys and val:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(val))
            lines.append("")

    return "\n".join(lines)


def _format_decision(data: dict) -> str:
    lines = ["=== Decision ===\n"]

    for key in ["decision", "comment", "title"]:
        if key in data and data[key]:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(data[key]))
            lines.append("")

    known_keys = {"decision", "comment", "title", "id", "forum", "invitations"}
    for key, val in data.items():
        if key not in known_keys and val:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(val))
            lines.append("")

    return "\n".join(lines)


def _format_author_response(data: dict, index: int) -> str:
    lines = [f"=== Author Response {index} ===\n"]

    for key in ["rebuttal", "comment", "title"]:
        if key in data and data[key]:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(data[key]))
            lines.append("")

    known_keys = {"rebuttal", "comment", "title", "id", "forum", "invitations"}
    for key, val in data.items():
        if key not in known_keys and val:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(val))
            lines.append("")

    return "\n".join(lines)


def _format_comment(data: dict, index: int) -> str:
    lines = [f"=== Comment {index} ===\n"]

    for key in ["comment", "title"]:
        if key in data and data[key]:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(data[key]))
            lines.append("")

    known_keys = {"comment", "title", "id", "forum", "invitations"}
    for key, val in data.items():
        if key not in known_keys and val:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(val))
            lines.append("")

    return "\n".join(lines)


def _format_generic(data: dict, label: str, index: int) -> str:
    lines = [f"=== {label} {index} ===\n"]

    for key, val in data.items():
        if key not in ("id", "forum", "invitations") and val:
            formatted_label = key.replace("_", " ").title()
            lines.append(f"--- {formatted_label} ---")
            lines.append(str(val))
            lines.append("")

    return "\n".join(lines)


def _write_typed_files(paper_dir: Path, categorized: dict):
    for i, rev in enumerate(categorized["official_review"], 1):
        text = _format_official_review(rev, i)
        (paper_dir / f"review_{i}.txt").write_text(text, encoding="utf-8")

    for i, mr in enumerate(categorized["meta_review"], 1):
        text = _format_meta_review(mr)
        fname = "meta_review.txt" if len(categorized["meta_review"]) == 1 else f"meta_review_{i}.txt"
        (paper_dir / fname).write_text(text, encoding="utf-8")

    for i, dec in enumerate(categorized["decision"], 1):
        text = _format_decision(dec)
        fname = "decision.txt" if len(categorized["decision"]) == 1 else f"decision_{i}.txt"
        (paper_dir / fname).write_text(text, encoding="utf-8")

    for i, er in enumerate(categorized["ethics_review"], 1):
        text = _format_generic(er, "Ethics Review", i)
        fname = "ethics_review.txt" if len(categorized["ethics_review"]) == 1 else f"ethics_review_{i}.txt"
        (paper_dir / fname).write_text(text, encoding="utf-8")

    for i, ar in enumerate(categorized["author_response"], 1):
        text = _format_author_response(ar, i)
        fname = "author_response.txt" if len(categorized["author_response"]) == 1 else f"author_response_{i}.txt"
        (paper_dir / fname).write_text(text, encoding="utf-8")

    for i, comment in enumerate(categorized["comment"], 1):
        text = _format_comment(comment, i)
        (paper_dir / f"comment_{i}.txt").write_text(text, encoding="utf-8")

    for i, pc in enumerate(categorized["public_comment"], 1):
        text = _format_comment(pc, i)
        (paper_dir / f"public_comment_{i}.txt").write_text(text, encoding="utf-8")

    for i, other in enumerate(categorized["other"], 1):
        text = _format_generic(other, "Other", i)
        (paper_dir / f"other_{i}.txt").write_text(text, encoding="utf-8")


def cmd_list_venues(args):
    config = _load_config(args.config)
    client = _get_client(config)
    author = args.author or config["username"]

    print(f"Searching for submissions by {author}...", file=sys.stderr)

    submissions = client.get_all_notes(content={"authorids": author})

    if not submissions:
        print(json.dumps([]))
        return

    venues: dict[str, dict] = {}
    for sub in submissions:
        invitations = getattr(sub, "invitations", None) or []
        venue_id = None
        for inv in invitations:
            if "/-/Submission" in inv or "/-/Blind_Submission" in inv:
                venue_id = inv.split("/-/")[0]
                break

        if not venue_id:
            continue

        if venue_id not in venues:
            venues[venue_id] = {
                "venue": venue_id,
                "venue_type": "workshop" if "workshop" in venue_id.lower() else "conference",
                "num_papers": 0,
                "latest_cdate": 0,
                "papers": [],
            }

        venues[venue_id]["num_papers"] += 1
        venues[venue_id]["papers"].append(_get_title(sub))
        cdate = getattr(sub, "cdate", 0) or 0
        if cdate > venues[venue_id]["latest_cdate"]:
            venues[venue_id]["latest_cdate"] = cdate

    sorted_venues = sorted(
        venues.values(), key=lambda v: v["latest_cdate"], reverse=True
    )

    for v in sorted_venues:
        if v["latest_cdate"]:
            ts = v["latest_cdate"] / 1000
            v["latest_date"] = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        else:
            v["latest_date"] = "unknown"

    print(json.dumps(sorted_venues, indent=2))


def cmd_download(args):
    config = _load_config(args.config)
    client = _get_client(config)

    venue = args.venue
    venue_type = args.venue_type
    author = args.author or config["username"]
    output_root = Path(args.output_dir).resolve()

    submissions = client.get_all_notes(
        content={"authorids": author},
        invitation=f"{venue}/-/Submission",
    )
    if not submissions:
        submissions = client.get_all_notes(
            content={"authorids": author},
            invitation=f"{venue}/-/Blind_Submission",
        )

    if not submissions:
        print("No submissions found.", file=sys.stderr)
        sys.exit(1)

    type_dir = "conferences" if venue_type == "conference" else "workshops"
    venue_dir = output_root / type_dir / _slugify(venue)
    venue_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for sub in submissions:
        title = _get_title(sub)
        paper_slug = _slugify(title) if title else f"paper_{sub.number}"
        paper_dir = venue_dir / paper_slug
        paper_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = paper_dir / "paper.pdf"
        try:
            pdf_binary = client.get_pdf(sub.id)
            pdf_path.write_bytes(pdf_binary)
        except Exception as e:
            print(f"Warning: could not download PDF for '{title}': {e}", file=sys.stderr)

        replies = client.get_all_notes(forum=sub.id)

        categorized = {
            "official_review": [],
            "meta_review": [],
            "ethics_review": [],
            "decision": [],
            "author_response": [],
            "comment": [],
            "public_comment": [],
            "other": [],
        }

        for reply in replies:
            if reply.id == sub.id:
                continue
            category = _classify_reply(reply)
            categorized[category].append(_extract_note_data(reply))

        raw_data_path = paper_dir / "raw_data.json"
        raw_data_path.write_text(
            json.dumps(categorized, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        _write_typed_files(paper_dir, categorized)

        decision_text = ""
        if categorized["decision"]:
            decision_text = categorized["decision"][0].get("decision", "")

        meta = {
            "submission_id": sub.id,
            "title": title,
            "number": sub.number,
            "decision": decision_text,
            "num_official_reviews": len(categorized["official_review"]),
            "num_meta_reviews": len(categorized["meta_review"]),
            "num_author_responses": len(categorized["author_response"]),
            "num_comments": len(categorized["comment"]),
            "num_public_comments": len(categorized["public_comment"]),
            "num_ethics_reviews": len(categorized["ethics_review"]),
            "paper_dir": str(paper_dir),
        }
        (paper_dir / "meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

        results.append(meta)
        total_replies = sum(len(v) for v in categorized.values())
        print(f"Fetched: {title} ({len(categorized['official_review'])} reviews, {total_replies} total replies) -> {paper_dir}")

    summary = {
        "venue": venue,
        "venue_type": venue_type,
        "author": author,
        "num_papers": len(results),
        "papers": results,
    }
    summary_path = venue_dir / "venue_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary: {summary_path}")
    print(f"Total: {len(results)} papers")


def main():
    parser = argparse.ArgumentParser(
        description="Download papers and reviews from OpenReview for a venue."
    )
    parser.add_argument(
        "--config",
        default=".openreview_config.json",
        help="Path to OpenReview credentials JSON file",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    lv = sub.add_parser("list-venues", help="List all venues with author submissions")
    lv.add_argument("--author", default=None, help="Author email (default: config username)")

    dl = sub.add_parser("download", help="Download all author papers and reviews for a venue")
    dl.add_argument("--venue", required=True, help="Venue ID (e.g. ICLR.cc/2025/Conference)")
    dl.add_argument(
        "--venue-type", choices=["conference", "workshop"], default="conference",
        help="Venue type for folder organization (default: conference)",
    )
    dl.add_argument("--author", default=None, help="Author email (default: config username)")
    dl.add_argument("--output-dir", default="./openreview-data", help="Root output directory")

    args = parser.parse_args()

    if args.command == "list-venues":
        cmd_list_venues(args)
    elif args.command == "download":
        cmd_download(args)


if __name__ == "__main__":
    main()
