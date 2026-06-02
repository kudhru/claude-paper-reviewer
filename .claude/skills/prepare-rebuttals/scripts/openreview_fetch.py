#!/usr/bin/env python3
"""
openreview_fetch.py — Fetch submissions and reviews from OpenReview.

Subcommands:
    list-submissions  List all submissions for a venue by author email
    fetch-paper       Download PDF + raw reviews for a single submission
    fetch-all         Download PDFs + raw reviews for all submissions

Credentials are read from a JSON config file:
    { "username": "...", "password": "...", "baseurl": "https://api2.openreview.net" }
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

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


def _venue_slug(venue: str) -> str:
    return _slugify(venue)


def _extract_review_data(note) -> dict:
    content = note.content or {}
    result = {"id": note.id, "forum": note.forum}
    for key, val in content.items():
        if isinstance(val, dict) and "value" in val:
            result[key] = val["value"]
        else:
            result[key] = val
    return result


def cmd_list_submissions(args):
    config = _load_config(args.config)
    client = _get_client(config)

    venue = args.venue
    author = args.author or config["username"]

    submissions = client.get_all_notes(
        content={"authorids": author},
        invitation=f"{venue}/-/Submission",
    )

    if not submissions:
        submissions = client.get_all_notes(
            content={"authorids": author},
            invitation=f"{venue}/-/Blind_Submission",
        )

    results = []
    for sub in submissions:
        title = ""
        if sub.content:
            title_field = sub.content.get("title", {})
            if isinstance(title_field, dict):
                title = title_field.get("value", "")
            else:
                title = str(title_field)
        results.append({"id": sub.id, "number": sub.number, "title": title})

    print(json.dumps(results, indent=2))


def cmd_fetch_paper(args):
    config = _load_config(args.config)
    client = _get_client(config)

    submission_id = args.submission_id
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    note = client.get_note(submission_id)
    title = ""
    if note.content:
        title_field = note.content.get("title", {})
        if isinstance(title_field, dict):
            title = title_field.get("value", "")
        else:
            title = str(title_field)

    pdf_path = out_dir / "paper.pdf"
    try:
        pdf_binary = client.get_pdf(submission_id)
        pdf_path.write_bytes(pdf_binary)
        print(f"Downloaded PDF: {pdf_path}")
    except Exception as e:
        print(f"Warning: could not download PDF: {e}", file=sys.stderr)

    replies = client.get_all_notes(forum=submission_id)
    reviews = []
    for reply in replies:
        invitations = getattr(reply, "invitations", None) or []
        inv_str = " ".join(invitations)
        if "Official_Review" in inv_str and "Meta_Review" not in inv_str and "Ethics_Review" not in inv_str:
            if reply.id != submission_id:
                reviews.append(_extract_review_data(reply))

    raw_reviews_path = out_dir / "raw_reviews.json"
    raw_reviews_path.write_text(
        json.dumps(reviews, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved {len(reviews)} reviews: {raw_reviews_path}")

    for i, rev in enumerate(reviews, 1):
        review_text = _format_review_text(rev, i)
        review_path = out_dir / f"review_{i}.txt"
        review_path.write_text(review_text, encoding="utf-8")
        print(f"  Review {i}: {review_path}")

    meta = {
        "submission_id": submission_id,
        "title": title,
        "num_reviews": len(reviews),
        "paper_pdf": str(pdf_path),
        "reviews_dir": str(out_dir),
    }
    meta_path = out_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Metadata: {meta_path}")


def _format_review_text(rev: dict, index: int) -> str:
    lines = [f"=== Reviewer {index} ===\n"]

    score_keys = ["rating", "soundness", "presentation", "contribution", "confidence", "overall_assessment"]
    for key in score_keys:
        if key in rev:
            label = key.replace("_", " ").title()
            lines.append(f"{label}: {rev[key]}")

    lines.append("")

    text_keys = [
        "summary", "review", "main_review", "strengths_and_weaknesses",
        "strengths", "weaknesses", "questions",
        "limitations", "ethical_concerns", "suggestions",
        "requested_changes", "minor_comments",
    ]
    for key in text_keys:
        if key in rev and rev[key]:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(rev[key]))
            lines.append("")

    known_keys = set(score_keys + text_keys + ["id", "forum"])
    for key, val in rev.items():
        if key not in known_keys and val:
            label = key.replace("_", " ").title()
            lines.append(f"--- {label} ---")
            lines.append(str(val))
            lines.append("")

    return "\n".join(lines)


def cmd_fetch_all(args):
    config = _load_config(args.config)
    client = _get_client(config)

    venue = args.venue
    author = args.author or config["username"]
    rebuttals_root = Path(args.rebuttals_dir).resolve()

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

    venue_dir = rebuttals_root / _venue_slug(venue)
    venue_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for sub in submissions:
        title = ""
        if sub.content:
            title_field = sub.content.get("title", {})
            if isinstance(title_field, dict):
                title = title_field.get("value", "")
            else:
                title = str(title_field)

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
        reviews = []
        for reply in replies:
            invitations = getattr(reply, "invitations", None) or []
            inv_str = " ".join(invitations)
            if "Official_Review" in inv_str and "Meta_Review" not in inv_str and "Ethics_Review" not in inv_str:
                if reply.id != sub.id:
                    reviews.append(_extract_review_data(reply))

        raw_reviews_path = paper_dir / "raw_reviews.json"
        raw_reviews_path.write_text(
            json.dumps(reviews, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        for i, rev in enumerate(reviews, 1):
            review_text = _format_review_text(rev, i)
            review_path = paper_dir / f"review_{i}.txt"
            review_path.write_text(review_text, encoding="utf-8")

        meta = {
            "submission_id": sub.id,
            "title": title,
            "number": sub.number,
            "num_reviews": len(reviews),
            "paper_pdf": str(pdf_path),
            "paper_dir": str(paper_dir),
        }
        meta_path = paper_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        results.append(meta)
        print(f"Fetched: {title} ({len(reviews)} reviews) -> {paper_dir}")

    summary_path = venue_dir / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSummary: {summary_path}")
    print(f"Total: {len(results)} papers")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch submissions and reviews from OpenReview."
    )
    parser.add_argument(
        "--config",
        default=".openreview_config.json",
        help="Path to OpenReview credentials JSON file",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ls = sub.add_parser("list-submissions", help="List submissions for a venue")
    ls.add_argument("--venue", required=True, help="Venue ID (e.g. ICLR.cc/2026/Conference)")
    ls.add_argument("--author", default=None, help="Author email (default: config username)")

    fp = sub.add_parser("fetch-paper", help="Fetch PDF + reviews for one submission")
    fp.add_argument("--submission-id", required=True, help="OpenReview submission note ID")
    fp.add_argument("--out-dir", required=True, help="Output directory")

    fa = sub.add_parser("fetch-all", help="Fetch all submissions + reviews for a venue")
    fa.add_argument("--venue", required=True, help="Venue ID")
    fa.add_argument("--author", default=None, help="Author email (default: config username)")
    fa.add_argument("--rebuttals-dir", default="./rebuttals", help="Root rebuttals directory")

    args = parser.parse_args()

    if args.command == "list-submissions":
        cmd_list_submissions(args)
    elif args.command == "fetch-paper":
        cmd_fetch_paper(args)
    elif args.command == "fetch-all":
        cmd_fetch_all(args)


if __name__ == "__main__":
    main()
