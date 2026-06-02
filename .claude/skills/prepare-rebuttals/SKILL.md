---
name: prepare-rebuttals
description: Fetch reviews from OpenReview for a conference venue and generate draft rebuttal responses for each paper. Spawns one agent per paper, each of which spawns subagents per review.
argument-hint: --venue "VENUE_ID" [--author EMAIL] [--paper-ids ID1,ID2,...] [--rebuttals-dir DIR]
disable-model-invocation: true
allowed-tools: Bash(find *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *) Bash(python3 *) Bash(cat *)
---

# Prepare Rebuttals

**Working directory:** !`pwd`
**Scripts dir:** `${CLAUDE_SKILL_DIR}/scripts`
**Fetch script:** `${CLAUDE_SKILL_DIR}/scripts/openreview_fetch.py`
**Compile script:** `${CLAUDE_SKILL_DIR}/scripts/rebuttal_compile.py`
**Default rebuttals dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/rebuttals"`
**Default config path:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/.openreview_config.json"`

Fetch reviews from OpenReview for a specific conference venue and generate draft rebuttal responses for all your submitted papers. Your only job is orchestration. All rebuttal writing happens inside subagents.

## Arguments

Parse the following flags from `$ARGUMENTS`:

| Flag | Default | Description |
|------|---------|-------------|
| `--venue "VENUE_ID"` | ask user | OpenReview venue ID (e.g. `"ICLR.cc/2026/Conference"`) |
| `--author EMAIL` | config username | Author email to filter submissions |
| `--paper-ids ID1,ID2,...` | all | Comma-separated submission IDs to process (default: all) |
| `--rebuttals-dir DIR` | default rebuttals dir above | Root output directory |
| `--config PATH` | default config path above | Path to `.openreview_config.json` |

If `--venue` is missing from `$ARGUMENTS`, ask the user for it before doing anything else.

## Orchestration Steps

### 1. Validate config

Check that the config file exists at the resolved config path. If not, tell the user to create it:

```json
{
  "username": "your-email@example.com",
  "password": "your-password",
  "baseurl": "https://api2.openreview.net"
}
```

### 2. Fetch all papers and reviews

Run the fetch script to download PDFs and raw reviews for all submissions:

```bash
python3 "{FETCH_SCRIPT}" --config "{CONFIG_PATH}" fetch-all \
    --venue "{VENUE}" \
    --rebuttals-dir "{REBUTTALS_DIR}" \
    [--author "{AUTHOR}"]
```

This creates the directory structure under `{REBUTTALS_DIR}/{venue_slug}/` with one subdirectory per paper, each containing `paper.pdf`, `raw_reviews.json`, `review_1.txt`, ..., `review_N.txt`, and `meta.json`.

### 3. Filter papers (if --paper-ids given)

If `--paper-ids` was specified, only process the matching papers. Otherwise process all.

### 4. Read the summary

Read the `summary.json` file from the venue directory to get the list of papers and their directories.

### 5. Inform the user

Print: `Preparing rebuttals for N paper(s) from VENUE`

List each paper with its title and number of reviews.

### 6. Read the workflow template

Read [per_paper_rebuttal_workflow.md](per_paper_rebuttal_workflow.md). This is the prompt template for per-paper agents.

### 7. Spawn one Agent per paper

For each paper, fill in the template variables and spawn a `general-purpose` Agent:

- `{PAPER_DIR}` — absolute path to this paper's output directory (contains paper.pdf, review files, meta.json)
- `{COMPILE_SCRIPT}` — absolute path to `rebuttal_compile.py`
- `{PER_REVIEW_TEMPLATE_PATH}` — absolute path to `per_review_rebuttal_workflow.md` (in the same directory as this SKILL.md)

If there are multiple papers, issue all Agent calls in a single response message so they run in parallel.

### 8. Report

After all agents finish, print a summary table:

| Paper | Reviews | Status | Output |
|-------|---------|--------|--------|
| Title | N | DONE/FAILED | path |

**Do not read any PDF yourself. Do not write any rebuttal content. Only orchestrate.**

## Supporting Files

- [per_paper_rebuttal_workflow.md](per_paper_rebuttal_workflow.md) — per-paper agent prompt template
- [per_review_rebuttal_workflow.md](per_review_rebuttal_workflow.md) — per-review subagent prompt template (read by the paper agent)
- [scripts/openreview_fetch.py](scripts/openreview_fetch.py) — OpenReview API fetch script
- [scripts/rebuttal_compile.py](scripts/rebuttal_compile.py) — rebuttal compilation and PDF conversion
