---
name: onboard-reviewers
description: Add reviewers to an OpenReview conference venue by adding them to the Reviewers/Invited group and sending each an OpenReview invitation message. Skips anyone already in the group. Supports a dry-run mode for verification before committing changes.
argument-hint: --venue "VENUE_ID" [--email EMAIL | --emails-file FILE] [--dry-run]
disable-model-invocation: true
allowed-tools: Bash(find *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *) Bash(python3 *) Bash(cat *) AskUserQuestion
---

# Onboard Reviewers

**Working directory:** !`pwd`
**Scripts dir:** `${CLAUDE_SKILL_DIR}/scripts`
**Onboard script:** `${CLAUDE_SKILL_DIR}/scripts/onboard_reviewers.py`
**Default config path:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/.openreview_config.json"`

Add reviewers to an OpenReview conference. For each email provided, adds to the `Reviewers/Invited` group and sends an OpenReview invitation message. Already-invited reviewers are skipped automatically.

## Arguments

Parse the following flags from `$ARGUMENTS`:

| Flag | Default | Description |
|------|---------|-------------|
| `--venue "VENUE_ID"` | ask user | OpenReview venue ID (e.g. `"CAISc/2026/Conference"`) |
| `--email EMAIL` | — | Single reviewer email to invite |
| `--emails-file FILE` | — | Path to file with one reviewer email per line (lines starting with `#` ignored) |
| `--dry-run` | false | Preview what would happen without making any changes |
| `--config PATH` | default config path above | Path to `.openreview_config.json` |

Exactly one of `--email` or `--emails-file` must be provided. If neither is given, ask the user.

## Steps

### 1. Validate config

Check that the config file exists at the resolved config path. If not, tell the user to create it:

```json
{
  "username": "your-email@example.com",
  "password": "your-password",
  "baseurl": "https://api2.openreview.net"
}
```

### 2. Run the onboard script

```bash
python3 "{ONBOARD_SCRIPT}" --config "{CONFIG_PATH}" invite \
    --venue "{VENUE}" \
    [--email "{EMAIL}" | --emails-file "{EMAILS_FILE}"] \
    [--dry-run]
```

The script will output one line per reviewer showing: `SKIP`, `ADDED + SENT`, or `ADDED + MSG_FAILED`.

### 3. Report

After the script completes, present a summary table:

| Reviewer Email | Status |
|----------------|--------|
| email@example.com | Added + Invited |
| already@here.com | Skipped (already invited) |
| problem@email.com | Added (message failed) |

If any message sends failed, note that the reviewer was still added to `Reviewers/Invited` — they can be messaged separately via the OpenReview Program Chairs console.

If `--dry-run` was used, remind the user to re-run without `--dry-run` to commit changes.
