#!/usr/bin/env python3
"""
openreview_chair_download.py — Program-chair side download of ALL papers of a venue
(not just your own submissions), with their full review data.

Requires that the configured OpenReview account is a Program Chair (or otherwise
has read access) for the venue.

Subcommands:
    stats     Show the decision distribution across all active submissions
    download  Download PDFs + all reviews/decisions/comments for selected papers

Usage:
    python openreview_chair_download.py --config .openreview_config.json stats \
        --venue "CAISc/2026/Conference"

    python openreview_chair_download.py --config .openreview_config.json download \
        --venue "CAISc/2026/Conference" \
        --filter accepted \
        --output-dir ./openreview-chair-data
"""

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import openreview


# --------------------------------------------------------------------------- #
# client / config
# --------------------------------------------------------------------------- #

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


def _val(content: dict, key: str, default=""):
    field = (content or {}).get(key)
    if isinstance(field, dict) and "value" in field:
        return field["value"]
    if field is None:
        return default
    return field


def _get_title(note) -> str:
    return _val(note.content or {}, "title", "")


# --------------------------------------------------------------------------- #
# note extraction (shared shape with download-venue)
# --------------------------------------------------------------------------- #

def _extract_note_data(note) -> dict:
    content = note.content or {}
    result = {"id": note.id, "forum": note.forum}
    result["invitations"] = getattr(note, "invitations", None) or []
    result["signatures"] = getattr(note, "signatures", None) or []
    for key, value in content.items():
        if isinstance(value, dict) and "value" in value:
            result[key] = value["value"]
        else:
            result[key] = value
    return result


def _classify_reply(note) -> str:
    inv_str = " ".join(getattr(note, "invitations", None) or [])

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


_EMPTY_CATEGORIES = (
    "official_review",
    "meta_review",
    "ethics_review",
    "decision",
    "author_response",
    "comment",
    "public_comment",
    "other",
)


def _categorize(submission_id: str, replies: list) -> dict:
    categorized = {key: [] for key in _EMPTY_CATEGORIES}
    for reply in replies:
        if reply.id == submission_id:
            continue
        categorized[_classify_reply(reply)].append(_extract_note_data(reply))
    return categorized


# --------------------------------------------------------------------------- #
# text formatting
# --------------------------------------------------------------------------- #

_SCORE_KEYS = [
    "rating", "soundness", "presentation", "contribution",
    "confidence", "overall_assessment", "novelty", "correctness",
    "technical_quality", "clarity", "significance", "reproducibility",
]

_TEXT_KEYS = [
    "summary", "review", "main_review", "strengths_and_weaknesses",
    "strengths", "weaknesses", "questions", "limitations",
    "ethical_concerns", "suggestions", "requested_changes", "minor_comments",
]

_SKIP_KEYS = {"id", "forum", "invitations", "signatures"}


def _format_official_review(data: dict, index: int) -> str:
    lines = [f"=== Official Review {index} ===\n"]
    for key in _SCORE_KEYS:
        if key in data:
            lines.append(f"{key.replace('_', ' ').title()}: {data[key]}")
    lines.append("")
    for key in _TEXT_KEYS:
        if data.get(key):
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(data[key]))
            lines.append("")
    known = set(_SCORE_KEYS + _TEXT_KEYS) | _SKIP_KEYS
    for key, value in data.items():
        if key not in known and value:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(value))
            lines.append("")
    return "\n".join(lines)


def _format_simple(data: dict, header: str, first_keys: list) -> str:
    lines = [f"=== {header} ===\n"]
    for key in first_keys:
        if data.get(key):
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(data[key]))
            lines.append("")
    known = set(first_keys) | _SKIP_KEYS
    for key, value in data.items():
        if key not in known and value:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(value))
            lines.append("")
    return "\n".join(lines)


def _write_typed_files(paper_dir: Path, categorized: dict):
    for i, rev in enumerate(categorized["official_review"], 1):
        (paper_dir / f"review_{i}.txt").write_text(
            _format_official_review(rev, i), encoding="utf-8")

    for i, item in enumerate(categorized["meta_review"], 1):
        name = "meta_review.txt" if len(categorized["meta_review"]) == 1 else f"meta_review_{i}.txt"
        (paper_dir / name).write_text(
            _format_simple(item, "Meta Review",
                           ["recommendation", "metareview", "meta_review", "summary", "confidence"]),
            encoding="utf-8")

    for i, item in enumerate(categorized["decision"], 1):
        name = "decision.txt" if len(categorized["decision"]) == 1 else f"decision_{i}.txt"
        (paper_dir / name).write_text(
            _format_simple(item, "Decision", ["decision", "comment", "title"]),
            encoding="utf-8")

    for i, item in enumerate(categorized["ethics_review"], 1):
        name = "ethics_review.txt" if len(categorized["ethics_review"]) == 1 else f"ethics_review_{i}.txt"
        (paper_dir / name).write_text(
            _format_simple(item, f"Ethics Review {i}", []), encoding="utf-8")

    for i, item in enumerate(categorized["author_response"], 1):
        name = "author_response.txt" if len(categorized["author_response"]) == 1 else f"author_response_{i}.txt"
        (paper_dir / name).write_text(
            _format_simple(item, f"Author Response {i}", ["rebuttal", "comment", "title"]),
            encoding="utf-8")

    for i, item in enumerate(categorized["comment"], 1):
        (paper_dir / f"comment_{i}.txt").write_text(
            _format_simple(item, f"Comment {i}", ["comment", "title"]), encoding="utf-8")

    for i, item in enumerate(categorized["public_comment"], 1):
        (paper_dir / f"public_comment_{i}.txt").write_text(
            _format_simple(item, f"Public Comment {i}", ["comment", "title"]), encoding="utf-8")

    for i, item in enumerate(categorized["other"], 1):
        (paper_dir / f"other_{i}.txt").write_text(
            _format_simple(item, f"Other {i}", []), encoding="utf-8")


# --------------------------------------------------------------------------- #
# submissions + decisions
# --------------------------------------------------------------------------- #

def _fetch_submissions(client, venue: str) -> list:
    subs = client.get_all_notes(invitation=f"{venue}/-/Submission")
    if not subs:
        subs = client.get_all_notes(invitation=f"{venue}/-/Blind_Submission")
    return subs


def _submission_status(note, venue: str) -> str:
    """active | withdrawn | desk_rejected, based on venueid."""
    venueid = str(_val(note.content or {}, "venueid", ""))
    if "Withdrawn" in venueid:
        return "withdrawn"
    if "Desk_Rejected" in venueid:
        return "desk_rejected"
    return "active"


_REJECT_MARKERS = ("reject", "withdraw", "decline")


def _accept_options(client, venue: str) -> list:
    """Decision strings the venue marked as acceptances, sanity-checked.

    Some venues misconfigure `accept_decision_options` (for example listing
    "Reject" alongside "Accept"). Any option that reads like a rejection is
    dropped, so a bad config cannot silently mark every paper accepted.
    """
    try:
        inv = client.get_invitation(f"{venue}/-/Decision")
    except Exception:
        return []
    content = getattr(inv, "content", None) or {}
    options = _val(content, "accept_decision_options", []) or []
    cleaned = [
        opt for opt in options
        if not any(marker in str(opt).lower() for marker in _REJECT_MARKERS)
    ]
    if len(cleaned) != len(options):
        print(
            "Warning: venue's accept_decision_options included rejection-like "
            f"entries {sorted(set(options) - set(cleaned))}; ignoring those.",
            file=sys.stderr,
        )
    return cleaned


def _is_accept(decision_text: str, accept_options: list) -> bool:
    if not decision_text:
        return False
    if accept_options:
        return decision_text.strip() in {str(opt).strip() for opt in accept_options}
    lowered = decision_text.lower()
    return "accept" in lowered and not any(m in lowered for m in _REJECT_MARKERS)


def _fetch_forum(client, submission) -> tuple:
    try:
        replies = client.get_all_notes(forum=submission.id)
    except Exception as exc:
        print(f"Warning: could not fetch replies for #{submission.number}: {exc}",
              file=sys.stderr)
        replies = []
    return submission, _categorize(submission.id, replies)


def _gather(client, venue: str, workers: int) -> tuple:
    subs = _fetch_submissions(client, venue)
    if not subs:
        print(f"No submissions found for {venue}. "
              f"Check the venue id and that your account has chair access.",
              file=sys.stderr)
        sys.exit(1)

    active = [s for s in subs if _submission_status(s, venue) == "active"]
    print(f"{venue}: {len(subs)} submissions total, {len(active)} active "
          f"(withdrawn/desk-rejected excluded). Fetching reviews...", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda s: _fetch_forum(client, s), active))

    return subs, results


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #

def cmd_stats(args):
    client = _get_client(_load_config(args.config))
    accept_options = _accept_options(client, args.venue)
    subs, results = _gather(client, args.venue, args.workers)

    rows = []
    for sub, cat in results:
        decisions = cat["decision"]
        decision_text = decisions[0].get("decision", "") if decisions else ""
        rows.append({
            "number": sub.number,
            "id": sub.id,
            "title": _get_title(sub),
            "decision": decision_text,
            "accepted": _is_accept(decision_text, accept_options),
            "num_reviews": len(cat["official_review"]),
            "ratings": [r.get("rating") for r in cat["official_review"]],
        })

    counts = {}
    for row in rows:
        counts[row["decision"] or "(no decision)"] = counts.get(row["decision"] or "(no decision)", 0) + 1

    out = {
        "venue": args.venue,
        "total_submissions": len(subs),
        "active_submissions": len(rows),
        "accept_decision_options": accept_options,
        "decision_counts": counts,
        "num_accepted": sum(1 for row in rows if row["accepted"]),
        "papers": sorted(rows, key=lambda r: r["number"]),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_download(args):
    client = _get_client(_load_config(args.config))
    accept_options = _accept_options(client, args.venue)
    _subs, results = _gather(client, args.venue, args.workers)

    venue_dir = Path(args.output_dir).resolve() / _slugify(args.venue)
    venue_dir.mkdir(parents=True, exist_ok=True)

    selected = []
    for sub, cat in results:
        decisions = cat["decision"]
        decision_text = decisions[0].get("decision", "") if decisions else ""
        accepted = _is_accept(decision_text, accept_options)
        if args.filter == "accepted" and not accepted:
            continue
        selected.append((sub, cat, decision_text, accepted))

    print(f"Selected {len(selected)} papers (filter={args.filter}). Downloading...",
          file=sys.stderr)

    metas = []
    for sub, cat, decision_text, accepted in sorted(selected, key=lambda t: t[0].number):
        title = _get_title(sub)
        slug = _slugify(title) if title else "untitled"
        paper_dir = venue_dir / f"{sub.number:04d}_{slug}"
        paper_dir.mkdir(parents=True, exist_ok=True)

        pdf_ok = False
        pdf_path = paper_dir / "paper.pdf"
        if not (args.skip_existing_pdf and pdf_path.exists() and pdf_path.stat().st_size > 0):
            try:
                pdf_path.write_bytes(client.get_pdf(sub.id))
                pdf_ok = True
            except Exception as exc:
                print(f"Warning: PDF failed for #{sub.number} '{title}': {exc}",
                      file=sys.stderr)
        else:
            pdf_ok = True

        (paper_dir / "raw_data.json").write_text(
            json.dumps(cat, indent=2, ensure_ascii=False), encoding="utf-8")
        _write_typed_files(paper_dir, cat)

        content = sub.content or {}
        ratings = [r.get("rating") for r in cat["official_review"]]
        meta = {
            "submission_id": sub.id,
            "number": sub.number,
            "title": title,
            "authors": _val(content, "authors", []),
            "authorids": _val(content, "authorids", []),
            "keywords": _val(content, "keywords", []),
            "abstract": _val(content, "abstract", ""),
            "submission_track": _val(content, "submission_track", ""),
            "submission_type": _val(content, "submission_type", ""),
            "decision": decision_text,
            "accepted": accepted,
            "ratings": ratings,
            "num_official_reviews": len(cat["official_review"]),
            "num_meta_reviews": len(cat["meta_review"]),
            "num_author_responses": len(cat["author_response"]),
            "num_comments": len(cat["comment"]),
            "num_public_comments": len(cat["public_comment"]),
            "num_ethics_reviews": len(cat["ethics_review"]),
            "forum_url": f"https://openreview.net/forum?id={sub.id}",
            "pdf_downloaded": pdf_ok,
            "paper_dir": str(paper_dir),
        }
        (paper_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        metas.append(meta)
        print(f"#{sub.number:>4}  {len(cat['official_review'])} reviews  "
              f"{decision_text or '(no decision)'}  -> {paper_dir.name}")

    summary = {
        "venue": args.venue,
        "filter": args.filter,
        "accept_decision_options": accept_options,
        "num_papers": len(metas),
        "papers": metas,
    }
    summary_path = venue_dir / "venue_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    print(f"\nSummary: {summary_path}")
    print(f"Total downloaded: {len(metas)} papers -> {venue_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Program-chair download of all venue papers + reviews from OpenReview.")
    parser.add_argument("--config", default=".openreview_config.json",
                        help="Path to OpenReview credentials JSON file")
    sub = parser.add_subparsers(dest="command", required=True)

    st = sub.add_parser("stats", help="Decision distribution across active submissions")
    st.add_argument("--venue", required=True)
    st.add_argument("--workers", type=int, default=8)

    dl = sub.add_parser("download", help="Download papers + review data")
    dl.add_argument("--venue", required=True)
    dl.add_argument("--filter", choices=["accepted", "all"], default="accepted",
                    help="Which active submissions to download (default: accepted)")
    dl.add_argument("--output-dir", default="./openreview-chair-data")
    dl.add_argument("--workers", type=int, default=8)
    dl.add_argument("--skip-existing-pdf", action="store_true",
                    help="Do not re-download a paper.pdf that already exists")

    args = parser.parse_args()
    if args.command == "stats":
        cmd_stats(args)
    else:
        cmd_download(args)


if __name__ == "__main__":
    main()
