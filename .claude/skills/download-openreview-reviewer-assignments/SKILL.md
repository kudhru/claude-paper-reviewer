---
name: download-openreview-reviewer-assignments
description: Download the papers assigned to YOU to review on an OpenReview venue (e.g. https://openreview.net/group?id=CAISc/2026/Conference/Reviewers), plus all readable data per paper — the submission PDF, every existing official review (with your own flagged), meta-reviews, decisions, author responses, and discussion comments. Output is organized into a structured per-paper folder hierarchy. Reviewer-side; reuses the OpenReview credentials file.
argument-hint: [--venue "VENUE_OR_REVIEWERS_GROUP" ...] [--paper-numbers N1,N2] [--output-dir DIR] [--config PATH]
disable-model-invocation: true
allowed-tools: Bash(find *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *) Bash(python3 *) Bash(cat *) AskUserQuestion
---

# Download OpenReview Reviewer Assignments

**Working directory:** !`pwd`
**Scripts dir:** `${CLAUDE_SKILL_DIR}/scripts`
**Download script:** `${CLAUDE_SKILL_DIR}/scripts/openreview_reviewer_download.py`
**Default output dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/openreview-reviewer-data"`
**Default config path:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/.openreview_config.json"`

Download every paper assigned to you to review on an OpenReview venue, together with everything readable on each forum. This is the **reviewer-side** counterpart to the `download-venue` skill (which is author-side, fetching your own submissions) and the OpenReview analog of `download-hotcrp-reviewer-assignments`: instead of your submissions, it fetches the papers OpenReview has assigned to *you* as a reviewer. First lists your assignments for the venue, lets you pick which to download, then fetches PDFs, existing reviews (your own is flagged), meta-reviews, decisions, comments, and author responses.

The venue is **always supplied by the user** — a venue id, a reviewers-group id, or the full group URL. All three of these resolve to the same venue `CAISc/2026/Conference`:
- `CAISc/2026/Conference`
- `CAISc/2026/Conference/Reviewers`
- `https://openreview.net/group?id=CAISc/2026/Conference/Reviewers`

## How assignments are found

Two independent signals are merged for robustness (the script does this; you don't have to):
1. **Assignment edges** — `{venue}/Reviewers/-/Assignment` edges whose tail is your profile id; each edge's head is a submission note id.
2. **Per-paper reviewer groups** — you are a member of `{venue}/Submission{N}/Reviewers` and an anonymized `{venue}/Submission{N}/Reviewer_{anon}` group for each assigned paper. The anon group also identifies which review on a forum is *yours*.

This correctly ignores papers where you are only an **author** (a separate `{venue}/Submission{N}/Authors` membership), which matters on venues where you both submit and review.

## Arguments

Parse the following flags from `$ARGUMENTS`:

| Flag | Default | Description |
|------|---------|-------------|
| `--venue "VENUE"` | interactive discovery | Venue id, reviewers-group id, or full group URL. If omitted, discover the venues where you are a reviewer first. |
| `--paper-numbers N1,N2` | all assigned | Comma-separated submission numbers to download (default: all your assignments) |
| `--output-dir DIR` | default output dir above | Root output directory |
| `--config PATH` | default config path above | Path to `.openreview_config.json` |

## Steps

### 1. Validate config

Check that the config file exists at the resolved config path. If not, tell the user to create it (this is the same file the `download-venue` skill uses):

```json
{
  "username": "your-email@example.com",
  "password": "your-password",
  "baseurl": "https://api2.openreview.net"
}
```

OpenReview rate-limits logins to a few per minute; the script retries automatically if it hits that. **Never print the password or write it into any output file.**

### 2. Discover reviewer venues (only if `--venue` not provided)

If the user did not name a venue, run discovery:

```bash
python3 "{DOWNLOAD_SCRIPT}" --config "{CONFIG_PATH}" list-venues
```

This outputs a JSON array of venues where you are a reviewer, each with `venue` and `num_assignments`. Present them as a numbered list and ask which venue to work with. Normally the user names the venue directly, so you can skip this step.

### 3. List your assignments for the venue

```bash
python3 "{DOWNLOAD_SCRIPT}" --config "{CONFIG_PATH}" list-assignments --venue "{VENUE}"
```

This authenticates (printing who you are on stderr), then outputs a JSON array of the papers assigned to you. Each entry has `number`, `id`, `title`, and `submitted_date`.

### 4. Present assignments and let the user choose

Display the assignments in a numbered list showing `number`, title, and submitted date. Then ask which to download — all, specific numbers, or specific submission `number`s. Translate the selection into a comma-separated list for `--paper-numbers` (or download all if they choose all).

### 5. Download assigned papers and data

Run the download command. Pass `--paper-numbers` only if the user selected a subset:

```bash
python3 "{DOWNLOAD_SCRIPT}" --config "{CONFIG_PATH}" download \
    --venue "{VENUE}" \
    --output-dir "{OUTPUT_DIR}" \
    [--paper-numbers "{PAPER_NUMBERS}"]
```

This creates:

```
openreview-reviewer-data/
└── {venue_slug}/                       (e.g. caisc_2026_conference)
    ├── venue_summary.json
    └── {NNNN}_{paper_slug}/            (zero-padded submission number + title slug)
        ├── paper.pdf
        ├── submission.json             (full submission note content)
        ├── meta.json
        ├── raw_replies.json            (lossless, categorized forum replies)
        ├── review_1.txt, review_2.txt, ...
        ├── my_review.txt               (your own review, if you have posted/drafted one)
        ├── meta_review.txt
        ├── decision.txt
        ├── author_response_1.txt, ...
        └── comment_1.txt, ...
```

Only data the venue lets a reviewer read is fetched — on many venues other reviewers' reviews stay hidden until you submit yours, so early in the cycle a paper may have no `review_*.txt` files yet. `raw_replies.json` is the source of truth; the `.txt` files are best-effort renderings.

### 6. Report

Print a summary table per venue:

**Venue: CAISc/2026/Conference**

| # | Title | PDF | Reviews | My review | Meta | Responses | Comments | Decision |
|---|-------|-----|---------|-----------|------|-----------|----------|----------|
| 9 | Title | OK | N | Yes/No | N | N | N | (if any) |

Read these counts from each paper's `meta.json` (or the `venue_summary.json`). Then tell the user where the data landed. Each paper's PDF is at `{paper_dir}/paper.pdf`, so review one with the `review-papers` skill via `--paper "{paper_dir}/paper.pdf"`. To review the whole batch at once, the PDFs first need to be collected into a flat directory (they are all named `paper.pdf` inside separate per-paper folders), so offer to copy them into one folder under unique names before invoking `review-papers --papers-dir`.

**Do not read any PDF yourself. Only orchestrate the discovery, download, and reporting. Never echo the OpenReview password.**

## Notes

- The same `.openreview_config.json` works for both this skill and `download-venue` — one OpenReview credential file, two directions (reviewer vs. author).
- `my_review.txt` is written only when a review on the forum is signed by one of your anonymized reviewer groups; if you have not started your review, there is no such file and `has_my_review` is `false`.
- The downloaded `paper.pdf` files have **not** been scanned for prompt injection. Run them through the `review-papers` pipeline, whose Step 0 performs the forensic prompt-injection scan (NeurIPS-style footer honeypots and similar), before LLM-reviewing.
