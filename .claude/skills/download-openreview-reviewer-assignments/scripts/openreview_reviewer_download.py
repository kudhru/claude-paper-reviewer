#!/usr/bin/env python3
"""
openreview_reviewer_download.py — Download a reviewer's assigned papers and all
related data from an OpenReview venue (e.g. CAISc/2026/Conference).

This is the OpenReview, reviewer-side analog of the `download-venue` skill (which
is author-side) and the direct counterpart of the HotCRP
`download-hotcrp-reviewer-assignments` skill: instead of fetching your own
submissions, it fetches the papers OpenReview has assigned to YOU as a reviewer,
together with everything readable on each forum — the submission PDF, every
existing official review (including your own, flagged), meta-reviews, decisions,
author responses, and discussion comments.

Assignments are discovered two ways and merged for robustness:
  1. Assignment edges:  {venue}/Reviewers/-/Assignment  with tail = your id
     (each edge's `head` is a submission note id), and
  2. Per-paper reviewer group membership: you are a member of
     {venue}/Submission{N}/Reviewers and an anonymized
     {venue}/Submission{N}/Reviewer_{anon} group for each assigned paper.
The anon groups also identify which review on a forum is your own.

Authentication reuses the same OpenReview credentials file as `download-venue`
(.openreview_config.json: username / password / baseurl).

Subcommands:
    list-venues        List venues where you are a reviewer (+ assignment counts)
    list-assignments   List the papers assigned to you in a venue
    download           Download PDFs + reviews + comments + responses per paper

Usage:
    python3 openreview_reviewer_download.py --config .openreview_config.json \
        list-venues

    python3 openreview_reviewer_download.py --config .openreview_config.json \
        list-assignments --venue "CAISc/2026/Conference"

    python3 openreview_reviewer_download.py --config .openreview_config.json \
        download --venue "CAISc/2026/Conference" \
        --output-dir ./openreview-reviewer-data \
        [--paper-numbers 9,188]
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import openreview


POLITE_DELAY_SECONDS = 0.3
LOGIN_MAX_RETRIES = 6


# --------------------------------------------------------------------------- #
# Config + client
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
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: config file is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)


def _get_client(config: dict) -> openreview.api.OpenReviewClient:
    """Log in to OpenReview, retrying on the /login rate limit (3 req/window)."""
    baseurl = config.get("baseurl", "https://api2.openreview.net")
    last_err = None
    for attempt in range(LOGIN_MAX_RETRIES):
        try:
            return openreview.api.OpenReviewClient(
                baseurl=baseurl,
                username=config["username"],
                password=config["password"],
            )
        except openreview.openreview.OpenReviewException as e:
            last_err = e
            msg = str(e)
            if "RateLimit" in msg or "Too many requests" in msg or "429" in msg:
                m = re.search(r"try again in (\d+) seconds", msg)
                wait = (int(m.group(1)) + 2) if m else 20
                print(
                    f"Login rate-limited; waiting {wait}s and retrying "
                    f"({attempt + 1}/{LOGIN_MAX_RETRIES})...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            raise
    print(f"Error: could not log in to OpenReview: {last_err}", file=sys.stderr)
    sys.exit(1)


def _user_id(client) -> str:
    """The authenticated user's profile id (tilde id), set at login."""
    prof = getattr(client, "profile", None)
    if prof is not None and getattr(prof, "id", None):
        return prof.id
    user = getattr(client, "user", None) or {}
    pid = (user.get("profile") or {}).get("id")
    if pid:
        return pid
    print("Error: could not determine the logged-in user's profile id.", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Venue normalization
# --------------------------------------------------------------------------- #

# Role suffixes that sit directly under a venue id; strip them to get the venue.
_ROLE_SUFFIXES = (
    "/Reviewers/Invited",
    "/Reviewers",
    "/Reviewer",
    "/Area_Chairs",
    "/Senior_Area_Chairs",
    "/Program_Chairs",
)


def _normalize_venue(raw: str) -> str:
    """Accept a venue id, a reviewers-group id, or a full OpenReview group URL,
    and return the bare venue id (e.g. 'CAISc/2026/Conference')."""
    s = (raw or "").strip()
    if not s:
        return s
    # Full URL: https://openreview.net/group?id=CAISc/2026/Conference/Reviewers
    m = re.search(r"[?&]id=([^&]+)", s)
    if m:
        from urllib.parse import unquote
        s = unquote(m.group(1))
    s = s.strip().strip("/")
    for suffix in _ROLE_SUFFIXES:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    return s.strip("/")


# --------------------------------------------------------------------------- #
# Small data helpers (shared shape with the author-side download-venue script)
# --------------------------------------------------------------------------- #

def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    if len(slug) > 80:
        slug = slug[:80].rstrip("_")
    return slug


def _get_title(note) -> str:
    if note.content:
        title_field = note.content.get("title", {})
        if isinstance(title_field, dict):
            return title_field.get("value", "")
        return str(title_field)
    return ""


def _extract_note_data(note) -> dict:
    content = note.content or {}
    result = {"id": note.id, "forum": note.forum}
    result["invitations"] = getattr(note, "invitations", None) or []
    result["signatures"] = getattr(note, "signatures", None) or []
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


# --------------------------------------------------------------------------- #
# Reply rendering
# --------------------------------------------------------------------------- #

def _format_official_review(data: dict, index: int, mine: bool = False) -> str:
    tag = " (YOUR REVIEW)" if mine else ""
    lines = [f"=== Official Review {index}{tag} ===\n"]

    score_keys = [
        "rating", "soundness", "presentation", "contribution",
        "confidence", "overall_assessment",
    ]
    for key in score_keys:
        if key in data:
            lines.append(f"{key.replace('_', ' ').title()}: {data[key]}")
    lines.append("")

    text_keys = [
        "summary", "review", "main_review", "strengths_and_weaknesses",
        "strengths", "weaknesses", "questions",
        "limitations", "ethical_concerns", "suggestions",
        "requested_changes", "minor_comments",
    ]
    for key in text_keys:
        if key in data and data[key]:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(data[key]))
            lines.append("")

    known = set(score_keys + text_keys + ["id", "forum", "invitations", "signatures"])
    for key, val in data.items():
        if key not in known and val:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(val))
            lines.append("")
    return "\n".join(lines)


def _format_meta_review(data: dict) -> str:
    lines = ["=== Meta Review ===\n"]
    for key in ["recommendation", "metareview", "meta_review", "summary", "confidence"]:
        if key in data and data[key]:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(data[key]))
            lines.append("")
    known = {"recommendation", "metareview", "meta_review", "summary",
             "confidence", "id", "forum", "invitations", "signatures"}
    for key, val in data.items():
        if key not in known and val:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(val))
            lines.append("")
    return "\n".join(lines)


def _format_decision(data: dict) -> str:
    lines = ["=== Decision ===\n"]
    for key in ["decision", "comment", "title"]:
        if key in data and data[key]:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(data[key]))
            lines.append("")
    known = {"decision", "comment", "title", "id", "forum", "invitations", "signatures"}
    for key, val in data.items():
        if key not in known and val:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(val))
            lines.append("")
    return "\n".join(lines)


def _format_author_response(data: dict, index: int) -> str:
    lines = [f"=== Author Response {index} ===\n"]
    for key in ["rebuttal", "comment", "title"]:
        if key in data and data[key]:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(data[key]))
            lines.append("")
    known = {"rebuttal", "comment", "title", "id", "forum", "invitations", "signatures"}
    for key, val in data.items():
        if key not in known and val:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(val))
            lines.append("")
    return "\n".join(lines)


def _format_comment(data: dict, index: int) -> str:
    lines = [f"=== Comment {index} ===\n"]
    for key in ["comment", "title"]:
        if key in data and data[key]:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(data[key]))
            lines.append("")
    known = {"comment", "title", "id", "forum", "invitations", "signatures"}
    for key, val in data.items():
        if key not in known and val:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(val))
            lines.append("")
    return "\n".join(lines)


def _format_generic(data: dict, label: str, index: int) -> str:
    lines = [f"=== {label} {index} ===\n"]
    for key, val in data.items():
        if key not in ("id", "forum", "invitations", "signatures") and val:
            lines.append(f"--- {key.replace('_', ' ').title()} ---")
            lines.append(str(val))
            lines.append("")
    return "\n".join(lines)


def _is_mine(reply, my_signatures: set, uid: str) -> bool:
    sigs = set(getattr(reply, "signatures", None) or [])
    if sigs & my_signatures:
        return True
    return uid in sigs


def _write_typed_files(paper_dir: Path, categorized: dict) -> bool:
    """Write per-reply .txt renderings. Returns True if your own review was found."""
    found_mine = False
    for i, rev in enumerate(categorized["official_review"], 1):
        mine = rev.get("_mine", False)
        text = _format_official_review(rev, i, mine=mine)
        (paper_dir / f"review_{i}.txt").write_text(text, encoding="utf-8")
        if mine:
            (paper_dir / "my_review.txt").write_text(text, encoding="utf-8")
            found_mine = True

    for i, mr in enumerate(categorized["meta_review"], 1):
        fname = "meta_review.txt" if len(categorized["meta_review"]) == 1 else f"meta_review_{i}.txt"
        (paper_dir / fname).write_text(_format_meta_review(mr), encoding="utf-8")

    for i, dec in enumerate(categorized["decision"], 1):
        fname = "decision.txt" if len(categorized["decision"]) == 1 else f"decision_{i}.txt"
        (paper_dir / fname).write_text(_format_decision(dec), encoding="utf-8")

    for i, er in enumerate(categorized["ethics_review"], 1):
        fname = "ethics_review.txt" if len(categorized["ethics_review"]) == 1 else f"ethics_review_{i}.txt"
        (paper_dir / fname).write_text(_format_generic(er, "Ethics Review", i), encoding="utf-8")

    for i, ar in enumerate(categorized["author_response"], 1):
        fname = "author_response.txt" if len(categorized["author_response"]) == 1 else f"author_response_{i}.txt"
        (paper_dir / fname).write_text(_format_author_response(ar, i), encoding="utf-8")

    for i, comment in enumerate(categorized["comment"], 1):
        (paper_dir / f"comment_{i}.txt").write_text(_format_comment(comment, i), encoding="utf-8")

    for i, pc in enumerate(categorized["public_comment"], 1):
        (paper_dir / f"public_comment_{i}.txt").write_text(_format_comment(pc, i), encoding="utf-8")

    for i, other in enumerate(categorized["other"], 1):
        (paper_dir / f"other_{i}.txt").write_text(_format_generic(other, "Other", i), encoding="utf-8")

    return found_mine


# --------------------------------------------------------------------------- #
# Assignment discovery
# --------------------------------------------------------------------------- #

def _member_groups(client, uid: str) -> list:
    """All group ids the authenticated user is a member of."""
    try:
        groups = client.get_all_groups(member=uid)
    except Exception as e:
        print(f"Warning: could not list group memberships: {e}", file=sys.stderr)
        return []
    return [g.id for g in groups]


def _assignment_numbers_from_groups(venue: str, member_groups: list) -> set:
    """Submission numbers for which the user is in a per-paper reviewer group."""
    pat = re.compile(rf"^{re.escape(venue)}/(?:Submission|Paper)(\d+)/Reviewer")
    nums = set()
    for gid in member_groups:
        m = pat.match(gid)
        if m:
            nums.add(int(m.group(1)))
    return nums


def _my_anon_groups(venue: str, member_groups: list) -> set:
    """The user's anonymized per-paper reviewer groups (sign your own reviews)."""
    pat = re.compile(rf"^{re.escape(venue)}/(?:Submission|Paper)\d+/Reviewer_")
    return {gid for gid in member_groups if pat.match(gid)}


def _assignment_note_ids_from_edges(client, venue: str, uid: str) -> set:
    """Submission note ids from assignment edges where you are the tail."""
    note_ids = set()
    for inv in (
        f"{venue}/Reviewers/-/Assignment",
        f"{venue}/Reviewers/-/Paper_Assignment",
    ):
        try:
            edges = client.get_all_edges(invitation=inv, tail=uid)
        except Exception:
            edges = []
        for e in edges:
            head = getattr(e, "head", None)
            if head:
                note_ids.add(head)
        if note_ids:
            break
    return note_ids


def _fetch_submissions(client, venue: str) -> list:
    for inv in (f"{venue}/-/Submission", f"{venue}/-/Blind_Submission"):
        try:
            notes = client.get_all_notes(invitation=inv)
        except Exception:
            notes = []
        if notes:
            return notes
    return []


def _safe_get_note(client, note_id):
    try:
        return client.get_note(note_id)
    except Exception:
        return None


def _resolve_assigned_notes(client, venue: str, uid: str, member_groups: list) -> list:
    """Return the submission notes assigned to the user, sorted by number.
    Merges edge-derived note ids with group-derived submission numbers."""
    note_ids = _assignment_note_ids_from_edges(client, venue, uid)
    numbers = _assignment_numbers_from_groups(venue, member_groups)

    notes_by_number = {}

    # Resolve edge note ids directly (cheap: one get_note each).
    for nid in note_ids:
        n = _safe_get_note(client, nid)
        if n is not None and getattr(n, "number", None) is not None:
            notes_by_number[n.number] = n

    # Cover any group-only numbers not already resolved via edges.
    missing = {num for num in numbers if num not in notes_by_number}
    if missing:
        subs = _fetch_submissions(client, venue)
        by_num = {n.number: n for n in subs}
        for num in missing:
            n = by_num.get(num)
            if n is not None:
                notes_by_number[num] = n
            else:
                print(f"Warning: assigned submission #{num} is not readable; skipping.", file=sys.stderr)

    return [notes_by_number[k] for k in sorted(notes_by_number)]


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_list_venues(args):
    config = _load_config(args.config)
    client = _get_client(config)
    uid = _user_id(client)
    print(f"Authenticated as {uid}", file=sys.stderr)

    member_groups = _member_groups(client, uid)

    # A venue is the prefix of any '*/Reviewers' group that is NOT per-paper.
    venue_re = re.compile(r"^(.*)/Reviewers$")
    venues = {}
    for gid in member_groups:
        if "/Submission" in gid or "/Paper" in gid:
            continue
        m = venue_re.match(gid)
        if not m:
            continue
        venue = m.group(1)
        venues.setdefault(venue, 0)

    for venue in venues:
        venues[venue] = len(_assignment_numbers_from_groups(venue, member_groups))

    out = [
        {"venue": v, "num_assignments": n}
        for v, n in sorted(venues.items(), key=lambda kv: kv[0])
    ]
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_list_assignments(args):
    config = _load_config(args.config)
    venue = _normalize_venue(args.venue)
    client = _get_client(config)
    uid = _user_id(client)
    print(f"Authenticated as {uid}; venue {venue}", file=sys.stderr)

    member_groups = _member_groups(client, uid)
    notes = _resolve_assigned_notes(client, venue, uid, member_groups)

    out = []
    for n in notes:
        cdate = getattr(n, "cdate", 0) or 0
        out.append({
            "number": n.number,
            "id": n.id,
            "title": _get_title(n),
            "submitted_date": (
                datetime.fromtimestamp(cdate / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                if cdate else "unknown"
            ),
        })
    out.sort(key=lambda x: x["number"])
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_download(args):
    config = _load_config(args.config)
    venue = _normalize_venue(args.venue)
    client = _get_client(config)
    uid = _user_id(client)
    print(f"Authenticated as {uid}; venue {venue}", file=sys.stderr)

    member_groups = _member_groups(client, uid)
    my_signatures = _my_anon_groups(venue, member_groups)
    notes = _resolve_assigned_notes(client, venue, uid, member_groups)

    if args.paper_numbers:
        try:
            wanted = {int(x) for x in re.split(r"[,\s]+", args.paper_numbers.strip()) if x}
        except ValueError:
            print("Error: --paper-numbers must be comma-separated integers.", file=sys.stderr)
            sys.exit(1)
        notes = [n for n in notes if n.number in wanted]

    if not notes:
        print("No assigned papers found.", file=sys.stderr)
        sys.exit(1)

    output_root = Path(args.output_dir).resolve()
    venue_dir = output_root / _slugify(venue)
    venue_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for sub in notes:
        title = _get_title(sub)
        slug = _slugify(title) if title else "paper"
        paper_dir = venue_dir / f"{sub.number:04d}_{slug}"
        paper_dir.mkdir(parents=True, exist_ok=True)

        (paper_dir / "submission.json").write_text(
            json.dumps(_extract_note_data(sub), indent=2, ensure_ascii=False), encoding="utf-8"
        )

        pdf_ok = False
        try:
            (paper_dir / "paper.pdf").write_bytes(client.get_pdf(sub.id))
            pdf_ok = True
        except Exception as e:
            print(f"  Warning: could not download PDF for #{sub.number}: {e}", file=sys.stderr)

        categorized = {
            "official_review": [], "meta_review": [], "ethics_review": [],
            "decision": [], "author_response": [], "comment": [],
            "public_comment": [], "other": [],
        }
        try:
            replies = client.get_all_notes(forum=sub.id)
        except Exception as e:
            print(f"  Warning: could not fetch replies for #{sub.number}: {e}", file=sys.stderr)
            replies = []

        for reply in replies:
            if reply.id == sub.id:
                continue
            data = _extract_note_data(reply)
            category = _classify_reply(reply)
            if category == "official_review":
                data["_mine"] = _is_mine(reply, my_signatures, uid)
            categorized[category].append(data)

        (paper_dir / "raw_replies.json").write_text(
            json.dumps(categorized, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        my_review = _write_typed_files(paper_dir, categorized)

        decision_text = categorized["decision"][0].get("decision", "") if categorized["decision"] else ""
        meta = {
            "number": sub.number,
            "submission_id": sub.id,
            "title": title,
            "paper_dir": str(paper_dir),
            "pdf_downloaded": pdf_ok,
            "num_official_reviews": len(categorized["official_review"]),
            "has_my_review": my_review,
            "num_meta_reviews": len(categorized["meta_review"]),
            "num_author_responses": len(categorized["author_response"]),
            "num_comments": len(categorized["comment"]),
            "num_public_comments": len(categorized["public_comment"]),
            "num_ethics_reviews": len(categorized["ethics_review"]),
            "decision": decision_text,
        }
        (paper_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        results.append(meta)

        total_replies = sum(len(v) for v in categorized.values())
        print(
            f"Fetched #{sub.number}: {title!r} "
            f"({len(categorized['official_review'])} reviews"
            f"{', incl. yours' if my_review else ''}, {total_replies} total replies) -> {paper_dir}"
        )
        time.sleep(POLITE_DELAY_SECONDS)

    summary = {
        "venue": venue,
        "reviewer": uid,
        "num_papers": len(results),
        "papers": results,
    }
    (venue_dir / "venue_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSummary: {venue_dir / 'venue_summary.json'}")
    print(f"Total: {len(results)} papers")


def main():
    parser = argparse.ArgumentParser(
        description="Download a reviewer's assigned papers and data from an OpenReview venue."
    )
    parser.add_argument(
        "--config", default=".openreview_config.json",
        help="Path to OpenReview credentials JSON file",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-venues", help="List venues where you are a reviewer")

    la = sub.add_parser("list-assignments", help="List papers assigned to you in a venue")
    la.add_argument("--venue", required=True, help="Venue id or reviewers-group id/URL")

    dl = sub.add_parser("download", help="Download assigned papers and all related data")
    dl.add_argument("--venue", required=True, help="Venue id or reviewers-group id/URL")
    dl.add_argument("--output-dir", default="./openreview-reviewer-data", help="Root output directory")
    dl.add_argument("--paper-numbers", default=None, help="Comma-separated submission numbers (default: all assigned)")

    args = parser.parse_args()
    if args.command == "list-venues":
        cmd_list_venues(args)
    elif args.command == "list-assignments":
        cmd_list_assignments(args)
    elif args.command == "download":
        cmd_download(args)


if __name__ == "__main__":
    main()
