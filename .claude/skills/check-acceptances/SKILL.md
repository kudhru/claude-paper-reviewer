---
name: check-acceptances
description: Find and aggregate all paper acceptances (workshop, conference, journal) from OpenReview within a date range, with paper-level deduplication and summary statistics.
argument-hint: --start-date YYYY-MM-DD [--end-date YYYY-MM-DD] [--author EMAIL]
disable-model-invocation: true
allowed-tools: Bash(python3 *) Bash(date *) Bash(mkdir *) Bash(ls *) Bash(pwd) Bash(realpath *) AskUserQuestion
---

# Check Acceptances

**Working directory:** !`pwd`
**Report script:** `${CLAUDE_SKILL_DIR}/scripts/check_acceptances.py`
**Default output dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/acceptance-reports"`
**Default config path:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/.openreview_config.json"`

Find all accepted papers on OpenReview within a date range. Acceptances are classified as workshop, conference, or journal. Results are aggregated at the paper level — one paper accepted at two workshops appears as a single paper with two acceptance events, not two separate papers.

## Arguments

Parse the following flags from `$ARGUMENTS`:

| Flag | Default | Description |
|------|---------|-------------|
| `--start-date DATE` | ask user | Start of window, `YYYY-MM-DD` |
| `--end-date DATE` | today | End of window, `YYYY-MM-DD` |
| `--author EMAIL` | config username | Author email to search |
| `--output-dir DIR` | default output dir above | Where to write reports |
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

### 2. Resolve missing arguments

- If `--start-date` was not provided, ask the user: "What start date should I use? (YYYY-MM-DD)"
- If `--end-date` was not provided, resolve it to today using:

```bash
date +%Y-%m-%d
```

### 3. Run the report script

```bash
python3 "{REPORT_SCRIPT}" \
    --config "{CONFIG_PATH}" \
    report \
    --start-date "{START_DATE}" \
    --end-date "{END_DATE}" \
    --output-dir "{OUTPUT_DIR}" \
    [--author "{AUTHOR}"]
```

This will:
- Fetch all submissions by the author from OpenReview
- For each submission, check the decision note's timestamp and text
- Collect decisions that say "Accept" (case-insensitive) and fall within the date window
- Group by normalized paper title to deduplicate across venues
- Classify each venue as workshop, conference, or journal
- Write `acceptance_report.json` and `acceptance_report.md` to the output directory
- Print a summary to stdout

### 4. Report to user

Print the full stdout from the script (it includes file paths and the summary table).
