#!/usr/bin/env python3
"""
hotcrp_download.py — Download a reviewer's assigned papers and all related data
from a HotCRP conference site (e.g. https://yourconf.hotcrp.com).

This is the reviewer-side analog of the OpenReview download skill: instead of
fetching your own submissions, it fetches the papers assigned to YOU to review,
together with everything attached to them — the submission PDF and any
supplementary/revision files, all existing reviews (including your own draft),
discussion comments, and author responses.

Authentication uses a HotCRP API bearer token (generate one in the HotCRP UI
under Account settings > Developer). Tokens are per-conference and start with
"hct_". See the HotCRP API reference at https://hotcrp.com/devel/api/.

Subcommands:
    list-assignments   List the papers assigned to you to review on a site
    download           Download PDFs + reviews + comments + responses per paper

Usage:
    python3 hotcrp_download.py --config .hotcrp_config.json list-assignments \
        --site https://middleware26c2.hotcrp.com

    python3 hotcrp_download.py --config .hotcrp_config.json download \
        --site https://middleware26c2.hotcrp.com \
        --output-dir ./hotcrp-data \
        [--paper-ids 12,34]

Config file (.hotcrp_config.json) — either a single site:
    { "site": "https://middleware26c2.hotcrp.com", "token": "hct_..." }
or several sites keyed by URL:
    { "sites": { "https://middleware26c2.hotcrp.com": "hct_..." } }
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

HTTP_TIMEOUT = 60
POLITE_DELAY_SECONDS = 0.3

# HotCRP review type codes -> human label (src/review form).
RTYPE_LABELS = {
    1: "external",
    2: "PC",
    3: "secondary",
    4: "primary",
    5: "metareview",
}


# --------------------------------------------------------------------------- #
# Config + site/token resolution
# --------------------------------------------------------------------------- #

def _load_config(config_path: str) -> dict:
    p = Path(config_path).resolve()
    if not p.exists():
        print(f"Error: config file not found: {p}", file=sys.stderr)
        print(
            "Create it with one of:\n"
            '  { "site": "https://yourconf.hotcrp.com", "token": "hct_..." }\n'
            '  { "sites": { "https://yourconf.hotcrp.com": "hct_..." } }\n'
            "Generate the token in HotCRP under Account settings > Developer.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: config file is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)


def _normalize_site(url: str) -> str:
    """Normalize a site URL to its root (no scheme assumptions broken, no
    trailing slash, no /api suffix). The API base is this + '/api'."""
    site = url.strip().rstrip("/")
    if not re.match(r"^https?://", site, re.IGNORECASE):
        site = "https://" + site
    for suffix in ("/api.php", "/api"):
        if site.lower().endswith(suffix):
            site = site[: -len(suffix)].rstrip("/")
            break
    return site


def _resolve_site_token(config: dict, site_arg, token_arg) -> tuple[str, str]:
    """Return (site_root, token). Resolves the site from the CLI flag or the
    config (single 'site' key, or the sole entry of a 'sites' map), and the
    token from the CLI flag, the HOTCRAPI_TOKEN env var, or the config."""
    sites_map = config.get("sites") or {}
    # Normalize the sites map for matching.
    norm_sites = {_normalize_site(k): v for k, v in sites_map.items()}

    # Resolve the site.
    if site_arg:
        site_root = _normalize_site(site_arg)
    elif config.get("site"):
        site_root = _normalize_site(config["site"])
    elif len(norm_sites) == 1:
        site_root = next(iter(norm_sites))
    elif len(norm_sites) > 1:
        avail = ", ".join(sorted(norm_sites))
        print(
            "Error: config lists multiple sites; pass --site to choose one.\n"
            f"  Available: {avail}",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print(
            "Error: no site given. Pass --site URL or set 'site'/'sites' in the config.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Resolve the token.
    token = token_arg or os.environ.get("HOTCRAPI_TOKEN")
    if not token:
        token = norm_sites.get(site_root)
    if not token and config.get("token"):
        token = config["token"]
    if not token:
        print(
            f"Error: no API token for site {site_root}.\n"
            "Add it to the config, pass --token, or set HOTCRAPI_TOKEN.\n"
            "Generate one in HotCRP under Account settings > Developer.",
            file=sys.stderr,
        )
        sys.exit(1)

    return site_root, token


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #

def _session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers["Authorization"] = f"bearer {token}"
    s.headers["Accept"] = "application/json"
    return s


def _get_json(session, api_base, endpoint, params=None, soft=False):
    """GET a JSON endpoint. Returns the parsed dict. On HotCRP-level failure
    (ok:false) or transport error, exits — unless soft=True, which returns None."""
    url = f"{api_base}/{endpoint}"
    try:
        r = session.get(url, params=params or {}, timeout=HTTP_TIMEOUT)
    except requests.RequestException as e:
        if soft:
            return None
        print(f"Error: request to {endpoint} failed: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        data = r.json()
    except ValueError:
        if soft:
            return None
        print(
            f"Error: {endpoint} did not return JSON (HTTP {r.status_code}). "
            "Check the site URL and token.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not data.get("ok", False):
        msgs = _format_messages(data.get("message_list"))
        if soft:
            return None
        print(f"Error: {endpoint} returned ok=false. {msgs}", file=sys.stderr)
        if r.status_code in (401, 403):
            print("This usually means the token is invalid or lacks rights.", file=sys.stderr)
        sys.exit(1)
    return data


def _format_messages(message_list) -> str:
    if not message_list:
        return ""
    parts = []
    for m in message_list:
        if isinstance(m, dict):
            txt = m.get("message") or m.get("text") or ""
            field = m.get("field")
            parts.append(f"[{field}] {txt}" if field else txt)
        else:
            parts.append(str(m))
    return " | ".join(p for p in parts if p)


def _get_bytes(session, url, params=None):
    """GET raw bytes (for document downloads). Returns (content, content_type)
    or None. Treats a JSON body as 'no document' (HotCRP returns JSON on error)."""
    try:
        r = session.get(url, params=params or {}, timeout=HTTP_TIMEOUT, stream=False)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    ctype = r.headers.get("Content-Type", "")
    if "application/json" in ctype.lower():
        return None
    return r.content, ctype


# --------------------------------------------------------------------------- #
# Small data helpers
# --------------------------------------------------------------------------- #

def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    if len(slug) > 80:
        slug = slug[:80].rstrip("_")
    return slug


def _strip_html(text):
    """HotCRP returns some display strings (reviewer/author names) wrapped in
    HTML, e.g. <span class="my-mention">Name</span>. Strip tags for the .txt
    renderings; the raw JSON keeps the original."""
    if not isinstance(text, str):
        return text
    import html as _html
    return _html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def _site_slug(site_root: str) -> str:
    host = re.sub(r"^https?://", "", site_root, flags=re.IGNORECASE)
    return _slugify(host)


def _status_label(status) -> str:
    """Normalize the paper status (object or string) to a short label."""
    if isinstance(status, str):
        return status
    if isinstance(status, dict):
        if status.get("withdrawn"):
            return "withdrawn"
        if status.get("submitted") or status.get("submitted_at"):
            return "submitted"
        if status.get("draft"):
            return "draft"
    return "unknown"


def _status_times(status) -> tuple:
    if isinstance(status, dict):
        return status.get("submitted_at"), status.get("modified_at")
    return None, None


def _paper_title(paper: dict) -> str:
    t = paper.get("title")
    if isinstance(t, dict):
        return t.get("value", "")
    return t or ""


# --------------------------------------------------------------------------- #
# Document discovery + download
# --------------------------------------------------------------------------- #

def _looks_like_document(obj) -> bool:
    return isinstance(obj, dict) and "hash" in obj and (
        "siteurl" in obj or "docid" in obj or "filename" in obj
    )


def _iter_document_fields(paper: dict):
    """Yield (field_name, doc_obj) for every document attached to the paper,
    including multi-file fields (arrays of doc objects)."""
    for key, val in paper.items():
        if _looks_like_document(val):
            yield key, val
        elif isinstance(val, list):
            for item in val:
                if _looks_like_document(item):
                    yield key, item


def _is_main_submission(field_name: str, obj: dict) -> bool:
    if field_name.lower() in ("submission", "paper"):
        return True
    if obj.get("dtype") == 0:
        return True
    return False


def _download_one_doc(session, site_root, api_base, pid, field, obj, dest: Path) -> bool:
    """Download a single document object to dest. Prefers the embedded siteurl,
    falls back to /api/document by field+hash. Returns True on success."""
    siteurl = obj.get("siteurl")
    if siteurl:
        url = f"{site_root}/{siteurl.lstrip('/')}"
        got = _get_bytes(session, url)
        if got:
            dest.write_bytes(got[0])
            return True
    # Fallback: /api/document with the field as dt and the content hash.
    params = {"p": pid, "dt": field}
    if obj.get("hash"):
        params["hash"] = obj["hash"]
    got = _get_bytes(session, f"{api_base}/document", params)
    if got:
        dest.write_bytes(got[0])
        return True
    return False


def _download_documents(session, site_root, api_base, pid, paper, paper_dir: Path) -> dict:
    """Download the main PDF, supplementary files, and any prior revisions.
    Returns a summary dict {documents, supplements, revisions}."""
    summary = {"documents": [], "supplements": [], "revisions": []}
    doc_fields = list(_iter_document_fields(paper))

    main_done = False
    seen_hashes = set()

    for field, obj in doc_fields:
        h = obj.get("hash")
        if h and h in seen_hashes:
            continue
        if h:
            seen_hashes.add(h)

        if not main_done and _is_main_submission(field, obj):
            if _download_one_doc(session, site_root, api_base, pid, field, obj, paper_dir / "paper.pdf"):
                summary["documents"].append("paper.pdf")
                main_done = True
            continue

        # Supplementary / named-field document.
        fname = obj.get("filename") or f"{field}.bin"
        safe = _slugify(field) + "_" + re.sub(r"[^A-Za-z0-9._-]+", "_", fname)
        dest = paper_dir / safe
        if _download_one_doc(session, site_root, api_base, pid, field, obj, dest):
            summary["supplements"].append(dest.name)

        # Prior versions of this document field, if HotCRP exposed history.
        history = obj.get("history")
        if isinstance(history, list) and history:
            rev_dir = paper_dir / "revisions"
            for i, hist in enumerate(history, 1):
                if not isinstance(hist, dict) or not hist.get("hash"):
                    continue
                if hist["hash"] in seen_hashes:
                    continue
                rev_dir.mkdir(exist_ok=True)
                hname = hist.get("filename") or f"{field}_v{i}.bin"
                rdest = rev_dir / (f"{field}_v{i}_" + re.sub(r"[^A-Za-z0-9._-]+", "_", hname))
                if _download_one_doc(session, site_root, api_base, pid, field, hist, rdest):
                    summary["revisions"].append(rdest.name)
                    seen_hashes.add(hist["hash"])

    # Fallback if no embedded doc object yielded the main PDF.
    if not main_done:
        got = _get_bytes(session, f"{api_base}/document", {"p": pid, "dt": "paper"})
        if got:
            (paper_dir / "paper.pdf").write_bytes(got[0])
            summary["documents"].append("paper.pdf")
            main_done = True

    if not main_done:
        print(f"  Warning: no submission PDF found for paper {pid}", file=sys.stderr)

    return summary


# --------------------------------------------------------------------------- #
# Review + comment rendering
# --------------------------------------------------------------------------- #

_REVIEW_META_KEYS = {
    "object", "pid", "rid", "rtype", "round", "status", "version", "ordinal",
    "draft", "blind", "my_review", "my_request", "reviewer", "reviewer_email",
    "review_token", "modified_at", "format", "editable", "ratings",
    "user_rating", "message_list",
}


def _format_review(rev: dict, index: int) -> str:
    lines = [f"=== Review {index} ===\n"]

    rtype = rev.get("rtype")
    rtype_label = RTYPE_LABELS.get(rtype, str(rtype) if rtype is not None else "")
    meta_bits = [
        ("Review ID", rev.get("rid")),
        ("Ordinal", rev.get("ordinal")),
        ("Type", rtype_label),
        ("Round", rev.get("round")),
        ("Status", rev.get("status")),
        ("Reviewer", _strip_html(rev.get("reviewer"))),
        ("Reviewer email", rev.get("reviewer_email")),
        ("Draft", rev.get("draft")),
        ("Mine", rev.get("my_review")),
        ("Modified at", rev.get("modified_at")),
    ]
    for label, val in meta_bits:
        if val not in (None, "", []):
            lines.append(f"{label}: {val}")
    lines.append("")

    # Review field values are keyed by conference-specific field UIDs
    # (e.g. "S01" for a score, "T02" for a text field).
    lines.append("--- Review fields (UIDs are conference-specific) ---")
    any_field = False
    for key, val in rev.items():
        if key in _REVIEW_META_KEYS:
            continue
        if isinstance(val, (dict, list)) or val in (None, ""):
            continue
        any_field = True
        lines.append(f"\n[{key}]")
        lines.append(str(val))
    if not any_field:
        lines.append("(no readable field values — see raw_reviews.json)")
    lines.append("")
    return "\n".join(lines)


def _format_comment(c: dict, index: int) -> str:
    is_response = bool(c.get("response"))
    header = "Author Response" if is_response else "Comment"
    lines = [f"=== {header} {index} ===\n"]

    meta_bits = [
        ("Comment ID", c.get("cid")),
        ("Response", c.get("response") if is_response else None),
        ("Visibility", c.get("visibility")),
        ("Topic", c.get("topic")),
        ("Author", _strip_html(c.get("author"))),
        ("Author email", c.get("author_email")),
        ("By author", c.get("by_author")),
        ("By shepherd", c.get("by_shepherd")),
        ("Draft", c.get("draft")),
        ("Modified at", c.get("modified_at")),
    ]
    for label, val in meta_bits:
        if val not in (None, "", []):
            lines.append(f"{label}: {val}")
    lines.append("")
    text = c.get("text")
    if text:
        lines.append("--- Text ---")
        lines.append(str(text))
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Assignment discovery
# --------------------------------------------------------------------------- #

def _fetch_assigned_papers(session, api_base) -> list:
    """Papers assigned to the authenticated user to review (collection t=r)."""
    data = _get_json(session, api_base, "papers", {"t": "r", "q": ""}, soft=True)
    if data and isinstance(data.get("papers"), list):
        return data["papers"]
    # Fallback: search for ids, then fetch each paper.
    search = _get_json(session, api_base, "search", {"t": "r", "q": ""})
    ids = search.get("ids", []) or []
    papers = []
    for pid in ids:
        pd = _get_json(session, api_base, "paper", {"p": pid}, soft=True)
        if pd and pd.get("paper"):
            papers.append(pd["paper"])
    return papers


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_list_assignments(args):
    config = _load_config(args.config)
    site_root, token = _resolve_site_token(config, args.site, args.token)
    api_base = f"{site_root}/api"
    session = _session(token)

    who = _get_json(session, api_base, "whoami")
    email = who.get("email", "")
    print(f"Authenticated as {email or '(unknown)'} on {site_root}", file=sys.stderr)

    papers = _fetch_assigned_papers(session, api_base)
    out = []
    for p in papers:
        status = p.get("status")
        submitted_at, modified_at = _status_times(status)
        out.append({
            "pid": p.get("pid"),
            "title": _paper_title(p),
            "status": _status_label(status),
            "submitted_at": submitted_at,
            "modified_at": modified_at,
            "possibly_revised": bool(
                submitted_at and modified_at and modified_at > submitted_at
            ),
        })
    out.sort(key=lambda x: (x["pid"] is None, x["pid"]))
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_download(args):
    config = _load_config(args.config)
    site_root, token = _resolve_site_token(config, args.site, args.token)
    api_base = f"{site_root}/api"
    session = _session(token)

    who = _get_json(session, api_base, "whoami")
    reviewer_email = who.get("email", "")

    if args.paper_ids:
        try:
            pids = [int(x) for x in re.split(r"[,\s]+", args.paper_ids.strip()) if x]
        except ValueError:
            print("Error: --paper-ids must be comma-separated integers.", file=sys.stderr)
            sys.exit(1)
    else:
        papers = _fetch_assigned_papers(session, api_base)
        pids = [p.get("pid") for p in papers if p.get("pid") is not None]

    if not pids:
        print("No assigned papers found.", file=sys.stderr)
        sys.exit(1)

    output_root = Path(args.output_dir).resolve()
    site_dir = output_root / _site_slug(site_root)
    site_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for pid in pids:
        pdata = _get_json(session, api_base, "paper", {"p": pid}, soft=True)
        if not pdata or not pdata.get("paper"):
            print(f"Warning: could not fetch paper {pid}; skipping.", file=sys.stderr)
            continue
        paper = pdata["paper"]
        title = _paper_title(paper)
        paper_slug = f"{pid:04d}_{_slugify(title)}" if title else f"{pid:04d}_paper"
        paper_dir = site_dir / paper_slug
        paper_dir.mkdir(parents=True, exist_ok=True)

        (paper_dir / "paper.json").write_text(
            json.dumps(paper, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        doc_summary = _download_documents(session, site_root, api_base, pid, paper, paper_dir)

        # Reviews (includes the user's own draft, flagged my_review).
        reviews = []
        rdata = _get_json(session, api_base, "reviews", {"p": pid}, soft=True)
        if rdata:
            reviews = rdata.get("reviews", []) or []
        (paper_dir / "raw_reviews.json").write_text(
            json.dumps(reviews, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        my_draft = False
        for i, rev in enumerate(reviews, 1):
            (paper_dir / f"review_{i}.txt").write_text(_format_review(rev, i), encoding="utf-8")
            if rev.get("my_review"):
                (paper_dir / "my_review.txt").write_text(_format_review(rev, i), encoding="utf-8")
                my_draft = True

        # Comments + author responses.
        comments = []
        cdata = _get_json(session, api_base, "comments", {"p": pid}, soft=True)
        if cdata:
            comments = cdata.get("comments", []) or []
        (paper_dir / "raw_comments.json").write_text(
            json.dumps(comments, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        num_responses = 0
        c_idx = 0
        for comment in comments:
            if comment.get("response"):
                num_responses += 1
                (paper_dir / f"author_response_{num_responses}.txt").write_text(
                    _format_comment(comment, num_responses), encoding="utf-8"
                )
            else:
                c_idx += 1
                (paper_dir / f"comment_{c_idx}.txt").write_text(
                    _format_comment(comment, c_idx), encoding="utf-8"
                )

        meta = {
            "pid": pid,
            "title": title,
            "status": _status_label(paper.get("status")),
            "paper_dir": str(paper_dir),
            "num_reviews": len(reviews),
            "has_my_draft_review": my_draft,
            "num_comments": c_idx,
            "num_author_responses": num_responses,
            "num_supplements": len(doc_summary["supplements"]),
            "num_revisions": len(doc_summary["revisions"]),
            "documents": doc_summary["documents"] + doc_summary["supplements"],
        }
        (paper_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        results.append(meta)
        print(
            f"Fetched paper {pid}: {title!r} "
            f"({len(reviews)} reviews, {c_idx} comments, {num_responses} responses, "
            f"{len(doc_summary['supplements'])} supplements) -> {paper_dir}"
        )
        time.sleep(POLITE_DELAY_SECONDS)

    summary = {
        "site": site_root,
        "reviewer_email": reviewer_email,
        "num_papers": len(results),
        "papers": results,
    }
    summary_path = site_dir / "site_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSummary: {summary_path}")
    print(f"Total: {len(results)} papers")


def main():
    parser = argparse.ArgumentParser(
        description="Download a reviewer's assigned papers and data from a HotCRP site."
    )
    parser.add_argument(
        "--config", default=".hotcrp_config.json",
        help="Path to HotCRP credentials JSON file",
    )
    parser.add_argument("--site", default=None, help="HotCRP site URL (e.g. https://yourconf.hotcrp.com)")
    parser.add_argument("--token", default=None, help="API token override (else from config or HOTCRAPI_TOKEN)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-assignments", help="List papers assigned to you to review")

    dl = sub.add_parser("download", help="Download assigned papers and all related data")
    dl.add_argument("--output-dir", default="./hotcrp-data", help="Root output directory")
    dl.add_argument("--paper-ids", default=None, help="Comma-separated paper IDs (default: all assigned)")

    args = parser.parse_args()

    if args.command == "list-assignments":
        cmd_list_assignments(args)
    elif args.command == "download":
        cmd_download(args)


if __name__ == "__main__":
    main()
