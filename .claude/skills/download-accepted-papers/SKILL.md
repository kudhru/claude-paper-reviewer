---
name: download-accepted-papers
description: Program-chair side download of ALL papers of an OpenReview venue (not just your own), filtered to accepted ones by default, with every review, meta-review, decision, response and comment, compiled review PDFs, and a ranked index. Use for best-paper selection, award committees, proceedings assembly, or any chair-level audit of a venue.
argument-hint: --venue "VENUE_ID" [--filter accepted|all] [--output-dir DIR] [--stats-only]
disable-model-invocation: true
allowed-tools: Bash(python3 *) Bash(ls *) Bash(find *) Bash(pwd) Bash(mkdir *) Bash(cat *) Bash(head *) Bash(du *) Read AskUserQuestion
---

# Download Accepted Papers (Program Chair)

**Working directory:** !`pwd`
**Scripts dir:** `${CLAUDE_SKILL_DIR}/scripts`
**Download script:** `${CLAUDE_SKILL_DIR}/scripts/openreview_chair_download.py`
**Compile script:** `${CLAUDE_SKILL_DIR}/scripts/review_compile.py`
**Index script:** `${CLAUDE_SKILL_DIR}/scripts/build_index.py`
**AI-involvement script:** `${CLAUDE_SKILL_DIR}/scripts/extract_ai_involvement.py`
**Default output dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/openreview-chair-data"`
**Default config path:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/.openreview_config.json"`

This is the chair-side counterpart to `download-venue` (which only fetches YOUR
submissions) and to the reviewer download skills (which only fetch YOUR
assignments). It fetches the whole venue, so the configured OpenReview account
must be a Program Chair (or otherwise have read access to reviews and decisions).

## Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--venue "VENUE_ID"` | required | Venue id, e.g. `CAISc/2026/Conference`. A Program-Chairs group URL like `.../group?id=CAISc/2026/Conference/Program_Chairs` maps to the venue id by dropping the trailing `/Program_Chairs`. |
| `--filter accepted\|all` | `accepted` | Which active submissions to download. `all` keeps rejected ones too. |
| `--output-dir DIR` | default output dir above | Root output directory. |
| `--config PATH` | default config path above | Path to `.openreview_config.json`. |
| `--stats-only` | off | Only report the decision distribution, download nothing. |
| `--workers N` | 8 | Parallel forum fetches. |

## Steps

### 1. Resolve the venue id

If the user pasted an OpenReview URL, strip the query string and any trailing
group segment (`/Program_Chairs`, `/Reviewers`, `/Authors`) to get the venue id.

### 2. Validate config

Config file must exist with `{ "username", "password", "baseurl" }`. Never print
the password.

### 3. Decision stats first

```bash
python3 "{DOWNLOAD_SCRIPT}" --config "{CONFIG_PATH}" stats --venue "{VENUE}"
```

Prints JSON with total/active submission counts, the venue's configured
`accept_decision_options`, the decision distribution, and a per-paper row list.
Withdrawn and desk-rejected submissions are excluded from "active" by their
`venueid`.

Report the counts to the user before downloading. Stop here if `--stats-only`.

**Watch the acceptance-option warning.** Some venues misconfigure
`accept_decision_options` (for example listing `Reject` as an acceptance option).
The script drops rejection-like entries and prints a warning on stderr. Surface
that warning to the user, since the same misconfiguration also affects the
venue's `Authors/Accepted` group on OpenReview.

### 4. Download

```bash
python3 "{DOWNLOAD_SCRIPT}" --config "{CONFIG_PATH}" download \
    --venue "{VENUE}" \
    --filter "{FILTER}" \
    --output-dir "{OUTPUT_DIR}" \
    --skip-existing-pdf
```

Layout:

```
openreview-chair-data/
└── {venue_slug}/
    ├── venue_summary.json
    ├── index.md / index.csv        (after step 6)
    └── {NNNN}_{title_slug}/
        ├── paper.pdf
        ├── meta.json               (title, authors, track, type, decision, ratings, forum url)
        ├── raw_data.json           (every reply, categorized)
        ├── review_1.txt, review_2.txt, ...
        ├── meta_review.txt, decision.txt, author_response.txt, comment_*.txt
        └── reviews.md / reviews.pdf  (after step 5)
```

`NNNN` is the OpenReview submission number, zero-padded, so directories sort in
submission order and match the paper numbers chairs see in the console.

### 5. Compile per-paper review documents

```bash
for d in "{OUTPUT_DIR}/{venue_slug}"/*/; do
    python3 "{COMPILE_SCRIPT}" --paper-dir "$d"
done
```

Produces `reviews.md` and `reviews.pdf` per paper (scores table, all reviews,
meta-review, decision, responses, comments).

### 6. Build the index

```bash
python3 "{INDEX_SCRIPT}" --venue-dir "{OUTPUT_DIR}/{venue_slug}"
```

Writes `index.md` (markdown table sorted by mean reviewer rating, titles linked
to their forums) and `index.csv` for spreadsheet use.

### 7. Optional: extract AI-involvement self-reports (CAISc-style venues)

Only for venues whose submissions carry an AI Involvement Checklist. First extract
the PDF text, then parse:

```bash
for d in "{OUTPUT_DIR}/{venue_slug}"/*/; do pdftotext -layout "$d/paper.pdf" "$d/paper.txt"; done
python3 "{AI_SCRIPT}" --venue-dir "{OUTPUT_DIR}/{venue_slug}" \
    [--track "Open-Ended"] [--out-prefix ai_involvement]
```

Writes `<prefix>.csv` / `.json` plus a per-paper `ai_involvement_section.txt`. Reports
a `composite_ai_score` (mean stage letter A=0/B=1/C=2/D=3, plus half the declared
iteration effort), the named AI systems, and flags papers whose declared letters
contradict their own prose.

Report the parse coverage and always state that these are **self-reports, not
verified**. Papers with no parsable checklist are a compliance finding, since venues
that mandate the checklist usually desk-reject submissions without one.

### 8. Report

Give the user: venue, total vs active vs downloaded counts, decision
distribution, rating distribution, track/type breakdown, output path, and any
papers whose PDF failed to download (`pdf_downloaded: false` in `meta.json`).

**Do not read any of the downloaded PDFs yourself.** This skill only downloads
and organizes. Reviewing, ranking, or award shortlisting is a separate,
explicitly requested step.
