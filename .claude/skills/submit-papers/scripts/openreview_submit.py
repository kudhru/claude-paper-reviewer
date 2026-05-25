#!/usr/bin/env python3
"""
openreview_submit.py — Query submission forms and submit papers to OpenReview.

Subcommands:
    get-form    Query a venue's submission invitation and output required fields
    submit      Upload PDF and submit a paper using a prepared submission JSON

Usage:
    python openreview_submit.py get-form --venue "ICLR.cc/2026/Conference"
    python openreview_submit.py submit --venue "ICLR.cc/2026/Conference" \
        --submission-json submission.json --pdf-path paper.pdf
"""

import argparse
import json
import sys
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


def _extract_field_info(field_name: str, field_schema: dict) -> dict:
    info = {"name": field_name}

    if isinstance(field_schema, dict):
        info["order"] = field_schema.get("order", 999)
        info["description"] = field_schema.get("description", "")

        if "value" in field_schema:
            val = field_schema["value"]
            if isinstance(val, dict) and "param" in val:
                param = val["param"]
                info["type"] = param.get("type", "string")
                info["optional"] = param.get("optional", False)
                if "regex" in param:
                    info["regex"] = param["regex"]
                if "maxSize" in param:
                    info["max_size_mb"] = param["maxSize"]
                if "extensions" in param:
                    info["extensions"] = param["extensions"]
                if "maxLength" in param:
                    info["max_length"] = param["maxLength"]
                if "minLength" in param:
                    info["min_length"] = param["minLength"]
                if "enum" in param:
                    info["enum"] = param["enum"]
                if "items" in param:
                    info["items"] = param["items"]
                if "minimum" in param:
                    info["minimum"] = param["minimum"]
                if "maximum" in param:
                    info["maximum"] = param["maximum"]
                if "input" in param:
                    info["input"] = param["input"]
                if "default" in param:
                    info["default"] = param["default"]
                if "markdown" in param:
                    info["markdown"] = param["markdown"]
            elif isinstance(val, dict) and "param" not in val:
                info["type"] = "fixed"
                info["fixed_value"] = val
            else:
                info["type"] = "fixed"
                info["fixed_value"] = val
        elif "value-radio" in field_schema:
            info["type"] = "radio"
            info["options"] = field_schema["value-radio"]
        elif "value-dropdown" in field_schema:
            info["type"] = "dropdown"
            info["options"] = field_schema["value-dropdown"]
        elif "value-checkbox" in field_schema:
            info["type"] = "checkbox"

    return info


def _find_submission_invitation(client, venue: str):
    candidates = [
        f"{venue}/-/Submission",
        f"{venue}/-/Blind_Submission",
    ]
    for inv_id in candidates:
        try:
            return client.get_invitation(inv_id)
        except openreview.OpenReviewException:
            continue

    try:
        all_invs = client.get_all_invitations(prefix=venue, expired=True)
        for inv in all_invs:
            inv_lower = inv.id.lower()
            if inv.id.endswith("/-/Submission") or inv.id.endswith("/-/Blind_Submission"):
                return inv
        for inv in all_invs:
            if "submission" in inv.id.lower().split("/")[-1].lower() and "withdrawal" not in inv.id.lower():
                return inv
    except openreview.OpenReviewException:
        pass

    return None


def cmd_get_form(args):
    config = _load_config(args.config)
    client = _get_client(config)
    venue = args.venue

    invitation = _find_submission_invitation(client, venue)
    if not invitation:
        print(f"Error: Could not find submission invitation for venue: {venue}", file=sys.stderr)
        sys.exit(1)

    invitation_id = invitation.id

    result = {
        "invitation_id": invitation_id,
        "venue": venue,
        "duedate": invitation.duedate,
        "expdate": getattr(invitation, "expdate", None),
        "fields": [],
    }

    edit = getattr(invitation, "edit", None)
    if edit and isinstance(edit, dict):
        note_schema = edit.get("note", {})
        if isinstance(note_schema, dict):
            content_schema = note_schema.get("content", {})
            if isinstance(content_schema, dict):
                for field_name, field_schema in content_schema.items():
                    field_info = _extract_field_info(field_name, field_schema)
                    result["fields"].append(field_info)

            readers = note_schema.get("readers", None)
            if readers:
                result["note_readers"] = readers
            writers = note_schema.get("writers", None)
            if writers:
                result["note_writers"] = writers
            signatures = note_schema.get("signatures", None)
            if signatures:
                result["note_signatures"] = signatures

        readers = edit.get("readers", None)
        if readers:
            result["edit_readers"] = readers
        writers = edit.get("writers", None)
        if writers:
            result["edit_writers"] = writers
        signatures = edit.get("signatures", None)
        if signatures:
            result["edit_signatures"] = signatures

    result["fields"].sort(key=lambda f: f.get("order", 999))

    print(json.dumps(result, indent=2, default=str))


def cmd_submit(args):
    config = _load_config(args.config)
    client = _get_client(config)
    venue = args.venue

    submission_path = Path(args.submission_json).resolve()
    if not submission_path.exists():
        print(f"Error: submission JSON not found: {submission_path}", file=sys.stderr)
        sys.exit(1)

    submission_data = json.loads(submission_path.read_text(encoding="utf-8"))

    pdf_path = Path(args.pdf_path).resolve() if args.pdf_path else None
    if pdf_path and not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    invitation_id = submission_data.get("invitation_id")
    if not invitation_id:
        inv = _find_submission_invitation(client, venue)
        if not inv:
            print(f"Error: Could not find submission invitation for venue: {venue}", file=sys.stderr)
            sys.exit(1)
        invitation_id = inv.id
    content = submission_data.get("content", {})

    if pdf_path:
        print(f"Uploading PDF: {pdf_path.name}...", file=sys.stderr)
        pdf_url = client.put_attachment(
            file_path=str(pdf_path),
            invitation=invitation_id,
            name="pdf",
        )
        content["pdf"] = {"value": pdf_url}
        print(f"  Uploaded: {pdf_url}", file=sys.stderr)

    for sup_field in ["supplementary_material", "software", "code", "data", "explanation_of_revisions_PDF"]:
        sup_path_str = submission_data.get(f"{sup_field}_path")
        if sup_path_str:
            sup_path = Path(sup_path_str).resolve()
            if sup_path.exists():
                print(f"Uploading {sup_field}: {sup_path.name}...", file=sys.stderr)
                sup_url = client.put_attachment(
                    file_path=str(sup_path),
                    invitation=invitation_id,
                    name=sup_field,
                )
                content[sup_field] = {"value": sup_url}
                print(f"  Uploaded: {sup_url}", file=sys.stderr)

    signatures = submission_data.get("signatures", [f"~{config['username']}"])
    note_readers = submission_data.get("readers")
    note_writers = submission_data.get("writers")

    note = openreview.api.Note(
        content=content,
        readers=note_readers,
        writers=note_writers,
        signatures=signatures,
    )

    print("Submitting paper...", file=sys.stderr)
    try:
        result = client.post_note_edit(
            invitation=invitation_id,
            signatures=signatures,
            note=note,
        )
        edit_id = result.get("id", "unknown")
        note_info = result.get("note", {})
        note_id = note_info.get("id", "unknown") if isinstance(note_info, dict) else "unknown"

        output = {
            "status": "success",
            "edit_id": edit_id,
            "note_id": note_id,
            "invitation_id": invitation_id,
            "title": content.get("title", {}).get("value", ""),
        }
        print(json.dumps(output, indent=2))

    except openreview.OpenReviewException as e:
        error_output = {
            "status": "error",
            "error": str(e),
            "invitation_id": invitation_id,
        }
        print(json.dumps(error_output, indent=2))
        sys.exit(1)


def _extract_profile_info(profile) -> dict:
    output = {"profile_id": profile.id, "name": None, "emails": []}
    if profile.content:
        names = profile.content.get("names", [])
        if names:
            name_entry = names[0]
            if isinstance(name_entry, dict):
                parts = []
                for k in ["first", "middle", "last"]:
                    v = name_entry.get(k, "")
                    if v:
                        parts.append(v)
                output["name"] = " ".join(parts)
        emails_confirmed = profile.content.get("emailsConfirmed", [])
        if emails_confirmed:
            output["emails"] = emails_confirmed
    return output


def cmd_get_profile(args):
    config = _load_config(args.config)
    client = _get_client(config)

    query = args.email

    if query == config.get("username") or query == "self":
        if hasattr(client, "profile") and client.profile:
            output = _extract_profile_info(client.profile)
            output["query"] = query
            print(json.dumps(output, indent=2))
            return

    try:
        results = client.search_profiles(confirmedEmails=[query])
        if results:
            output = _extract_profile_info(results[0])
            output["query"] = query
            print(json.dumps(output, indent=2))
            return
    except Exception:
        pass

    try:
        if query.startswith("~"):
            profile = client.get_profile(query)
            output = _extract_profile_info(profile)
            output["query"] = query
            print(json.dumps(output, indent=2))
            return
    except Exception:
        pass

    try:
        results = client.search_profiles(fullname=query)
        if results:
            matches = [_extract_profile_info(p) for p in results[:5]]
            print(json.dumps({"query": query, "matches": matches}, indent=2))
            return
    except Exception:
        pass

    print(json.dumps({"query": query, "profile_id": None, "name": None}))


def _submit_one(client, submission_data, pdf_path, invitation_id):
    """Submit a single paper using an existing client session. Returns result dict."""
    content = submission_data.get("content", {})

    if pdf_path and Path(pdf_path).exists():
        print(f"  Uploading PDF: {Path(pdf_path).name}...", file=sys.stderr)
        pdf_url = client.put_attachment(
            file_path=str(pdf_path), invitation=invitation_id, name="pdf",
        )
        content["pdf"] = {"value": pdf_url}
        print(f"  Uploaded: {pdf_url}", file=sys.stderr)

    for sup_field in ["supplementary_material", "software", "code", "data", "explanation_of_revisions_PDF"]:
        sup_path_str = submission_data.get(f"{sup_field}_path")
        if sup_path_str:
            sup_path = Path(sup_path_str).resolve()
            if sup_path.exists():
                print(f"  Uploading {sup_field}: {sup_path.name}...", file=sys.stderr)
                sup_url = client.put_attachment(
                    file_path=str(sup_path), invitation=invitation_id, name=sup_field,
                )
                content[sup_field] = {"value": sup_url}
                print(f"  Uploaded: {sup_url}", file=sys.stderr)

    signatures = submission_data.get("signatures", [])
    note = openreview.api.Note(
        content=content,
        readers=submission_data.get("readers"),
        writers=submission_data.get("writers"),
        signatures=signatures,
    )

    result = client.post_note_edit(
        invitation=invitation_id, signatures=signatures, note=note,
    )
    edit_id = result.get("id", "unknown")
    note_info = result.get("note", {})
    note_id = note_info.get("id", "unknown") if isinstance(note_info, dict) else "unknown"
    return {
        "status": "success",
        "edit_id": edit_id,
        "note_id": note_id,
        "title": content.get("title", {}).get("value", ""),
    }


def cmd_batch_submit(args):
    import glob
    import time as _time

    config = _load_config(args.config)
    venue = args.venue
    staging_dir = Path(args.staging_dir).resolve()
    wait_seconds = args.wait_seconds

    json_files = sorted(glob.glob(str(staging_dir / "*_submission.json")))
    if not json_files:
        print(f"Error: No *_submission.json files found in {staging_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(json_files)} submission(s) in {staging_dir}", file=sys.stderr)

    # Single login for the entire batch
    client = None
    for attempt in range(5):
        try:
            client = _get_client(config)
            break
        except openreview.OpenReviewException as e:
            if "RateLimit" in str(e) or "429" in str(e) or "HumanVerification" in str(e):
                backoff = wait_seconds * (attempt + 1)
                print(f"Login rate limited, waiting {backoff}s (attempt {attempt+1}/5)...", file=sys.stderr)
                _time.sleep(backoff)
            else:
                raise
    if client is None:
        print("Error: Could not log in after 5 attempts", file=sys.stderr)
        sys.exit(1)

    invitation = _find_submission_invitation(client, venue)
    if not invitation:
        print(f"Error: Could not find submission invitation for venue: {venue}", file=sys.stderr)
        sys.exit(1)
    invitation_id = invitation.id

    results = []
    for i, jf in enumerate(json_files):
        sub_data = json.loads(Path(jf).read_text(encoding="utf-8"))
        title = sub_data.get("content", {}).get("title", {}).get("value", Path(jf).stem)
        print(f"\n[{i+1}/{len(json_files)}] {title[:80]}", file=sys.stderr)

        pdf_path = sub_data.get("pdf_path")
        if args.pdf_dir:
            pdf_name = Path(pdf_path).name if pdf_path else None
            if pdf_name:
                pdf_path = str(Path(args.pdf_dir) / pdf_name)

        try:
            r = _submit_one(client, sub_data, pdf_path, invitation_id)
            results.append(r)
            print(f"  SUCCESS: note_id={r['note_id']}", file=sys.stderr)
        except openreview.OpenReviewException as e:
            err_str = str(e)
            if "HumanVerification" in err_str or "RateLimit" in err_str:
                print(f"  Rate limited / CAPTCHA. Waiting {wait_seconds * 2}s and retrying...", file=sys.stderr)
                _time.sleep(wait_seconds * 2)
                try:
                    client = _get_client(config)
                    r = _submit_one(client, sub_data, pdf_path, invitation_id)
                    results.append(r)
                    print(f"  SUCCESS (retry): note_id={r['note_id']}", file=sys.stderr)
                except openreview.OpenReviewException as e2:
                    results.append({"status": "error", "error": str(e2), "title": title[:80]})
                    print(f"  FAILED (retry): {e2}", file=sys.stderr)
            else:
                results.append({"status": "error", "error": err_str, "title": title[:80]})
                print(f"  FAILED: {e}", file=sys.stderr)

        if i < len(json_files) - 1:
            print(f"  Waiting {wait_seconds}s...", file=sys.stderr)
            _time.sleep(wait_seconds)

    print(json.dumps(results, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Query submission forms and submit papers to OpenReview."
    )
    parser.add_argument(
        "--config",
        default=".openreview_config.json",
        help="Path to OpenReview credentials JSON file",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gf = sub.add_parser("get-form", help="Get submission form fields for a venue")
    gf.add_argument("--venue", required=True, help="Venue ID (e.g. ICLR.cc/2026/Conference)")

    sm = sub.add_parser("submit", help="Submit a paper using a prepared JSON")
    sm.add_argument("--venue", required=True, help="Venue ID")
    sm.add_argument("--submission-json", required=True, help="Path to submission JSON")
    sm.add_argument("--pdf-path", default=None, help="Path to PDF (overrides JSON pdf_path)")

    bs = sub.add_parser("batch-submit", help="Submit all papers in a staging directory")
    bs.add_argument("--venue", required=True, help="Venue ID")
    bs.add_argument("--staging-dir", required=True, help="Directory with *_submission.json files")
    bs.add_argument("--pdf-dir", default=None, help="Override PDF directory (default: uses pdf_path from JSON)")
    bs.add_argument("--wait-seconds", type=int, default=60, help="Seconds to wait between submissions (default: 60)")

    gp = sub.add_parser("get-profile", help="Look up OpenReview profile ID for an email")
    gp.add_argument("--email", required=True, help="Email address to look up")

    args = parser.parse_args()

    if args.command == "get-form":
        cmd_get_form(args)
    elif args.command == "submit":
        cmd_submit(args)
    elif args.command == "batch-submit":
        cmd_batch_submit(args)
    elif args.command == "get-profile":
        cmd_get_profile(args)


if __name__ == "__main__":
    main()
