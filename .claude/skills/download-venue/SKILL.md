---
name: download-venue
description: Download your papers and all review data (reviews, meta-reviews, decisions, author responses, comments) from OpenReview for selected venues, organized into a structured folder hierarchy with compiled review PDFs.
argument-hint: [--venue "VENUE_ID" ...] [--venue-type conference|workshop] [--author EMAIL]
disable-model-invocation: true
allowed-tools: Bash(find *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *) Bash(python3 *) Bash(cat *) AskUserQuestion
---

# Download Venue

**Working directory:** !`pwd`
**Scripts dir:** `${CLAUDE_SKILL_DIR}/scripts`
**Download script:** `${CLAUDE_SKILL_DIR}/scripts/openreview_venue_download.py`
**Compile script:** `${CLAUDE_SKILL_DIR}/scripts/review_compile.py`
**Default output dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/openreview-data"`
**Default config path:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/.openreview_config.json"`

Download all your papers and their complete review data from OpenReview. First discovers all venues where you have submissions, lets you pick which ones to download, then fetches everything and compiles review PDFs.

## Arguments

Parse the following flags from `$ARGUMENTS`:

| Flag | Default | Description |
|------|---------|-------------|
| `--venue "VENUE_ID"` | interactive | One or more venue IDs (skip discovery if provided) |
| `--venue-type TYPE` | auto-detect | Override venue type: `conference` or `workshop` |
| `--author EMAIL` | config username | Author email to filter submissions |
| `--output-dir DIR` | default output dir above | Root output directory |
| `--config PATH` | default config path above | Path to `.openreview_config.json` |

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

### 2. Discover venues (if `--venue` not provided)

If no `--venue` flag was given, run the discovery command:

```bash
python3 "{DOWNLOAD_SCRIPT}" --config "{CONFIG_PATH}" list-venues \
    [--author "{AUTHOR}"]
```

This outputs a JSON array of venues sorted by chronology (most recent first). Each entry has:
- `venue` — the venue ID
- `venue_type` — auto-detected as `conference` or `workshop`
- `num_papers` — number of your submissions
- `latest_date` — date of most recent submission
- `papers` — list of paper titles

### 3. Present venues and let user choose

Display the discovered venues in a numbered list, showing for each:
- Venue ID
- Type (conference/workshop)
- Number of papers
- Latest submission date
- Paper titles

Then ask the user which venues to download. They may select all, specific numbers, or specific venue IDs. Accept the user's selection.

### 4. Download papers and review data for each selected venue

For each selected venue, run the download script:

```bash
python3 "{DOWNLOAD_SCRIPT}" --config "{CONFIG_PATH}" download \
    --venue "{VENUE}" \
    --venue-type "{VENUE_TYPE}" \
    --output-dir "{OUTPUT_DIR}" \
    [--author "{AUTHOR}"]
```

Use the `venue_type` from the discovery output (or the `--venue-type` override if provided).

This creates per venue:

```
openreview-data/
└── {conferences|workshops}/
    └── {venue_slug}/
        ├── venue_summary.json
        └── {paper_slug}/
            ├── paper.pdf
            ├── meta.json
            ├── raw_data.json
            ├── review_1.txt, review_2.txt, ...
            ├── meta_review.txt
            ├── decision.txt
            ├── author_response.txt
            ├── comment_1.txt, ...
            └── (other reply types)
```

### 5. Compile reviews for each paper

For each venue, read its `venue_summary.json`, then for each paper run the compile script:

```bash
python3 "{COMPILE_SCRIPT}" --paper-dir "{PAPER_DIR}"
```

This creates `reviews.md` and `reviews.pdf` in each paper directory, containing:
- Paper title and decision
- Reviewer scores summary table
- All official reviews
- Meta review
- Decision details
- Ethics reviews (if any)
- Author responses
- Official and public comments

### 6. Report

Print a summary table per venue:

**Venue: ICLR.cc/2026/Conference (conference)**

| Paper | Decision | Reviews | Meta Review | Responses | PDF |
|-------|----------|---------|-------------|-----------|-----|
| Title | Accept/Reject | N | Yes/No | N | OK/Failed |

**Do not read any PDF yourself. Only orchestrate the discovery, download, and compilation.**
