#!/usr/bin/env python3
"""
onboard_reviewers.py — Add reviewers to an OpenReview conference and send invitations.

Subcommands:
    invite    Add reviewer emails to Reviewers/Invited group and send OpenReview messages

Usage:
    # Single email (test)
    python3 onboard_reviewers.py --config .openreview_config.json invite \\
        --venue "CAISc/2026/Conference" \\
        --email "reviewer@example.com"

    # Batch from file
    python3 onboard_reviewers.py --config .openreview_config.json invite \\
        --venue "CAISc/2026/Conference" \\
        --emails-file reviewers.txt

    # Dry run (preview only, no changes)
    python3 onboard_reviewers.py --config .openreview_config.json invite \\
        --venue "CAISc/2026/Conference" \\
        --emails-file reviewers.txt \\
        --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

import openreview


INVITATION_MESSAGE = """\
Hi,

You have been added to the Program Committee as a reviewer for the Conference \
for AI Scientists (CAISc) 2026 on OpenReview.

Please log in to your OpenReview account at https://openreview.net \
(or create one if you don't have an account yet) to access your reviewer \
profile for this conference.

Conference page: https://openreview.net/group?id=CAISc/2026/Conference

We will assign at most 4 papers per reviewer. Paper assignments will be \
released in the next 2-3 days, and reviews are due by June 25th, 2026. \
Final decisions will be released by June 30th, 2026.

If you have any questions, please reach out to any of us:
- Dhruv Kumar: dhruv.kumar@pilani.bits-pilani.ac.in
- Pratik Narang: pratik.narang@pilani.bits-pilani.ac.in
- Murari Mandal: murari.nus@gmail.com
- Dhruv Trehan: dhruv.trehan@lossfunk.com

Thanks,
CAISc 2026 Program Committee
"""

# Signature and reply-to used for group messages
_MESSAGE_SIGNATURE = "CAISc/2026/Conference"
_MESSAGE_REPLY_TO = "dhruv.kumar@pilani.bits-pilani.ac.in"


def _load_config(config_path: str) -> dict:
    p = Path(config_path).resolve()
    if not p.exists():
        print(f"Error: config file not found: {p}", file=sys.stderr)
        print(
            'Create it with:\n'
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


def _get_invited_members(client: openreview.api.OpenReviewClient, venue_id: str) -> set:
    group_id = f"{venue_id}/Reviewers/Invited"
    try:
        group = client.get_group(group_id)
        return set(group.members or [])
    except openreview.OpenReviewException as e:
        print(f"Warning: could not fetch {group_id}: {e}", file=sys.stderr)
        return set()


def _send_group_invitation_message(
    client: openreview.api.OpenReviewClient,
    venue_id: str,
    dry_run: bool = False,
) -> bool:
    """Send one invitation message to the entire Reviewers/Invited group."""
    group_id = f"{venue_id}/Reviewers/Invited"
    if dry_run:
        print(f"  DRY-RUN: would send group invitation message to {group_id}")
        return True
    try:
        client.post_message(
            subject="You have been added as a reviewer for CAISc 2026",
            recipients=[group_id],
            message=INVITATION_MESSAGE,
            invitation=f"{venue_id}/-/Message",
            signature=_MESSAGE_SIGNATURE,
            replyTo=_MESSAGE_REPLY_TO,
        )
        return True
    except Exception as e:
        print(f"  Warning: group message send failed: {e}", file=sys.stderr)
        return False


def _load_emails_from_file(path: str) -> list:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    emails = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            emails.append(line)
    return emails


def cmd_invite(args):
    config = _load_config(args.config)
    client = _get_client(config)

    # Collect emails
    if args.email:
        emails = [args.email.strip()]
    elif args.emails_file:
        emails = _load_emails_from_file(args.emails_file)
    else:
        print("Error: provide --email or --emails-file", file=sys.stderr)
        sys.exit(1)

    if not emails:
        print("Error: no emails found to process", file=sys.stderr)
        sys.exit(1)

    venue_id = args.venue
    invited_group_id = f"{venue_id}/Reviewers/Invited"

    print(f"Venue:   {venue_id}")
    print(f"Group:   {invited_group_id}")
    print(f"Emails:  {len(emails)}")
    if args.dry_run:
        print("Mode:    DRY RUN (no changes will be made)")
    print()

    # Fetch current members once
    current_members = _get_invited_members(client, venue_id)
    print(f"Already in Reviewers/Invited: {len(current_members)}\n")

    results = []

    newly_added = []

    for email in emails:
        if email in current_members:
            print(f"  SKIP    {email}  (already in Reviewers/Invited)")
            results.append((email, "skipped"))
            continue

        if args.dry_run:
            print(f"  DRY-RUN {email}  → would add to {invited_group_id}")
            results.append((email, "dry-run"))
            continue

        # Add to Reviewers/Invited
        try:
            client.add_members_to_group(invited_group_id, [email])
            print(f"  ADDED   {email}")
            results.append((email, "added"))
            newly_added.append(email)
        except openreview.OpenReviewException as e:
            print(f"  FAILED  {email}  (could not add to group: {e})")
            results.append((email, "failed-add"))

    # Send one group invitation message to all current Reviewers/Invited members
    if newly_added and not args.dry_run:
        print()
        print(f"Sending invitation message to {invited_group_id} group...")
        sent = _send_group_invitation_message(client, venue_id, dry_run=False)
        if sent:
            print(f"  Group invitation message sent.")
            # Mark all newly added as sent
            results = [
                (email, "added+sent") if status == "added" else (email, status)
                for email, status in results
            ]
        else:
            print(f"  Warning: group message failed — reviewers were still added to the group.")
    elif args.dry_run and newly_added:
        _send_group_invitation_message(client, venue_id, dry_run=True)

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    counts = {}
    for _, status in results:
        counts[status] = counts.get(status, 0) + 1
    for status, count in sorted(counts.items()):
        print(f"  {status:<20} {count}")
    print()

    # JSON output for skill to parse
    print("JSON_RESULTS:" + json.dumps(results))

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Onboard reviewers to an OpenReview conference",
    )
    parser.add_argument(
        "--config",
        default=".openreview_config.json",
        help="Path to OpenReview config JSON",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    invite_parser = subparsers.add_parser(
        "invite",
        help="Add reviewers to Reviewers/Invited and send invitation messages",
    )
    invite_parser.add_argument("--venue", required=True, help="OpenReview venue ID")
    invite_parser.add_argument("--email", help="Single reviewer email")
    invite_parser.add_argument("--emails-file", help="File with one email per line")
    invite_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without making any changes",
    )

    args = parser.parse_args()

    if args.command == "invite":
        cmd_invite(args)


if __name__ == "__main__":
    main()
