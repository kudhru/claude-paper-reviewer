---
name: download-hotcrp-reviewer-assignments
description: Download the papers assigned to YOU to review on a HotCRP conference site (e.g. https://yourconf.hotcrp.com), plus all related data: the submission PDF, supplementary and revision files, every existing review (including your own draft), discussion comments, and author responses. Output is organized into a structured per-paper folder hierarchy. Reviewer-side; uses a HotCRP API token.
argument-hint: [--site URL] [--config PATH] [--output-dir DIR] [--paper-ids ID1,ID2]
disable-model-invocation: true
allowed-tools: Bash(find *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *) Bash(python3 *) Bash(cat *) AskUserQuestion
---

# Download HotCRP Reviewer Assignments

**Working directory:** !`pwd`
**Scripts dir:** `${CLAUDE_SKILL_DIR}/scripts`
**Download script:** `${CLAUDE_SKILL_DIR}/scripts/hotcrp_download.py`
**Default output dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/hotcrp-data"`
**Default config path:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/.hotcrp_config.json"`

Download every paper assigned to you to review on a HotCRP site, together with everything attached to it. This is the **reviewer-side** counterpart to the OpenReview `download-venue` skill (which is author-side): instead of your own submissions, it fetches the papers HotCRP has assigned to *you* as a reviewer. First lists your assignments, lets you pick which to download, then fetches PDFs, existing reviews (including your own in-progress draft), comments, author responses, and any revision/supplementary files.

The HotCRP JSON API reference is at https://hotcrp.com/devel/api/.

## Arguments

Parse the following flags from `$ARGUMENTS`:

| Flag | Default | Description |
|------|---------|-------------|
| `--site URL` | from config | HotCRP site URL, e.g. `https://middleware26c2.hotcrp.com`. Optional if the config names exactly one site. |
| `--paper-ids ID1,ID2` | all assigned | Comma-separated paper IDs to download (default: all your assignments) |
| `--output-dir DIR` | default output dir above | Root output directory |
| `--config PATH` | default config path above | Path to `.hotcrp_config.json` |

## Steps

### 1. Validate config

Check that the config file exists at the resolved config path. If not, tell the user to create it. HotCRP authenticates with a per-conference **API token** (not a username/password). The user generates one in the HotCRP UI under **Account settings → Developer**; tokens start with `hct_` and can be scoped read-only.

Single-site config:

```json
{
  "site": "https://middleware26c2.hotcrp.com",
  "token": "hct_your_token_here"
}
```

Multi-site config (one token per conference, keyed by site URL):

```json
{
  "sites": {
    "https://middleware26c2.hotcrp.com": "hct_token_for_this_conf",
    "https://otherconf.hotcrp.com": "hct_token_for_other_conf"
  }
}
```

The token can also be supplied via the `HOTCRAPI_TOKEN` environment variable or a `--token` flag. **Never print the token back to the user or write it into any output file.**

### 2. List your assignments

Run the discovery command (omit `--site` if the config has a single site):

```bash
python3 "{DOWNLOAD_SCRIPT}" --config "{CONFIG_PATH}" --site "{SITE}" list-assignments
```

This validates the token via `/api/whoami` (printing who you are on stderr), then outputs a JSON array of the papers assigned to you to review (HotCRP collection `t=r`). Each entry has:
- `pid` — the paper number
- `title`
- `status` — `submitted` / `draft` / `withdrawn`
- `submitted_at`, `modified_at` — timestamps
- `possibly_revised` — `true` when the paper was modified after its initial submission (a hint that it has a revision)

### 3. Present assignments and let the user choose

Display the assignments in a numbered list, showing for each: `pid`, title, status, and a `(possibly revised)` marker when `possibly_revised` is true.

Then ask the user which to download — all, specific numbers, or specific `pid`s. Accept the selection and translate it to a comma-separated `pid` list for `--paper-ids` (or download all if they choose all).

### 4. Download assigned papers and data

Run the download command. Pass `--paper-ids` only if the user selected a subset:

```bash
python3 "{DOWNLOAD_SCRIPT}" --config "{CONFIG_PATH}" --site "{SITE}" download \
    --output-dir "{OUTPUT_DIR}" \
    [--paper-ids "{PAPER_IDS}"]
```

This creates:

```
hotcrp-data/
└── {site_slug}/                     (e.g. middleware26c2_hotcrp_com)
    ├── site_summary.json
    └── {NNNN}_{paper_slug}/          (zero-padded pid + title slug)
        ├── paper.pdf
        ├── paper.json               (full HotCRP paper object)
        ├── meta.json
        ├── raw_reviews.json
        ├── raw_comments.json
        ├── review_1.txt, review_2.txt, ...
        ├── my_review.txt            (your own assigned/draft review, if any)
        ├── comment_1.txt, ...
        ├── author_response_1.txt, ...
        ├── {field}_{filename}       (supplementary files, if any)
        └── revisions/               (prior document versions, if HotCRP exposes them)
```

Review field values are keyed by conference-specific field UIDs (e.g. `S01` for a score). The `review_*.txt` files render them best-effort; `raw_reviews.json` is the lossless source of truth.

### 5. Report

Print a summary table per site:

**Site: middleware26c2.hotcrp.com**

| pid | Title | Status | Reviews | My draft | Comments | Responses | Supplements |
|-----|-------|--------|---------|----------|----------|-----------|-------------|
| 12 | Title | submitted | N | Yes/No | N | N | N |

Read these counts from each paper's `meta.json` (or the `site_summary.json`). Then tell the user where the data landed. Each paper's PDF is at `{paper_dir}/paper.pdf`, so review one with the `review-papers` skill via `--paper "{paper_dir}/paper.pdf"`. To review the whole batch at once, the PDFs first need to be collected into a flat directory (they are all named `paper.pdf` inside separate per-paper folders), so offer to copy them into one folder under unique names before invoking `review-papers --papers-dir`.

**Do not read any PDF yourself. Only orchestrate the discovery, download, and reporting. Never echo the API token.**

## Notes

- Each HotCRP site is a single conference, so there is no multi-venue discovery step like OpenReview — the unit of selection is the paper, not the venue.
- Some assigned papers may have only a *requested* review with no draft yet; `my_review.txt` is written only when a draft exists.
- The downloaded `paper.pdf` files have **not** been scanned for prompt injection. Run them through the `review-papers` pipeline, whose Step 0 performs the forensic prompt-injection scan, before LLM-reviewing.
