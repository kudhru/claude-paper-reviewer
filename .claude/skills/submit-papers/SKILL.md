---
name: submit-papers
description: Prepare and submit papers to OpenReview for a venue. Reads PDFs to extract metadata, queries the venue's submission form, generates pre-filled submission JSONs for review, and submits after user confirmation.
argument-hint: --venue "VENUE_ID" --papers-dir DIR [--author EMAIL]
disable-model-invocation: true
allowed-tools: Bash(find *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *) Bash(python3 *) Bash(cat *) Read Edit Write AskUserQuestion
---

# Submit Papers

**Working directory:** !`pwd`
**Scripts dir:** `${CLAUDE_SKILL_DIR}/scripts`
**Submit script:** `${CLAUDE_SKILL_DIR}/scripts/openreview_submit.py`
**Default config path:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/.openreview_config.json"`

Prepare and submit papers to OpenReview for a specific venue. Reads each PDF to extract title, abstract, authors, and keywords, then generates submission JSON files for user review before submitting.

## Arguments

Parse the following flags from `$ARGUMENTS`:

| Flag | Default | Description |
|------|---------|-------------|
| `--venue "VENUE_ID"` | ask user | OpenReview venue ID (e.g. `"ICLR.cc/2026/Conference"`) |
| `--papers-dir DIR` | ask user | Directory containing PDF files to submit |
| `--author EMAIL` | config username | Author email (for profile lookup) |
| `--config PATH` | default config path above | Path to `.openreview_config.json` |

If `--venue` or `--papers-dir` is missing, ask the user before proceeding.

## Steps

### 1. Validate config

Check that the config file exists. If not, tell the user to create it:

```json
{
  "username": "your-email@example.com",
  "password": "your-password",
  "baseurl": "https://api2.openreview.net"
}
```

### 2. Query the venue submission form

Run the get-form command to discover required fields:

```bash
python3 "{SUBMIT_SCRIPT}" --config "{CONFIG_PATH}" get-form --venue "{VENUE}"
```

This returns a JSON with:
- `invitation_id` — the exact invitation to use for submission
- `fields` — array of field definitions (name, type, required/optional, description, constraints)
- `note_signatures`, `note_readers`, `note_writers` — access control templates

Read this output carefully. Note which fields are required vs optional, their types, and any constraints (regex, maxLength, enum values, etc.).

### 3. List PDFs in the papers directory

Find all PDF files in the specified directory:

```bash
find "{PAPERS_DIR}" -maxdepth 1 -name "*.pdf" -type f | sort
```

Tell the user how many PDFs were found and list them.

### 4. Extract metadata from each PDF

For each PDF:

1. **Read the PDF** using the Read tool to view its contents
2. **Extract** the following information:
   - **Title** — from the paper header
   - **Abstract** — from the abstract section
   - **Authors** — list of author names
   - **Keywords** — if listed in the paper, otherwise generate relevant ones
   - **TL;DR** — generate a concise 1-2 sentence summary (max 250 chars)
3. **Fill in venue-specific fields** based on the form schema from step 2:
   - For enum/radio/dropdown fields, choose the most appropriate option based on the paper content
   - For checkbox fields (like code of ethics acknowledgments), set to the affirmative value
   - For text fields with descriptions, fill based on the paper content
   - For file upload fields other than pdf (supplementary material, code, etc.), leave blank and note them

### 5. Look up author profile IDs

For the submitting author (from config), look up their OpenReview profile ID:

```bash
python3 "{SUBMIT_SCRIPT}" --config "{CONFIG_PATH}" get-profile --email "{AUTHOR_EMAIL}"
```

For co-authors found in the PDF, note their names. The user will need to provide their email addresses or OpenReview profile IDs. Ask the user for co-author emails/profile IDs.

### 6. Generate submission JSON files

For each paper, create a `submission.json` file in a staging directory alongside the PDF. The JSON structure:

```json
{
  "invitation_id": "Venue/-/Submission",
  "signatures": ["~Author_Profile_ID1"],
  "readers": ["from form schema"],
  "writers": ["from form schema"],
  "content": {
    "title": {"value": "Extracted Title"},
    "abstract": {"value": "Extracted Abstract"},
    "authors": {"value": ["Author 1", "Author 2"]},
    "authorids": {"value": ["~Profile_ID1", "coauthor@email.com"]},
    "keywords": {"value": ["keyword1", "keyword2"]},
    "TLDR": {"value": "Generated summary"},
    ... (other venue-specific fields)
  },
  "pdf_path": "/absolute/path/to/paper.pdf"
}
```

**Important field formatting rules:**
- Every content field value must be wrapped as `{"value": <actual_value>}`
- String fields: `{"value": "text"}`
- Array fields (authors, keywords): `{"value": ["item1", "item2"]}`
- Enum/radio fields: `{"value": "selected_option"}` — must match an allowed option exactly
- Do NOT include `pdf` in the content — the submit script handles upload separately

### 7. Present submissions for review

For each paper, display a summary:
- Title
- Authors and their IDs
- Abstract (first 200 chars)
- Keywords
- TL;DR
- Any fields that need user attention (blanks, uncertain values)
- Any required fields that could not be auto-filled

Ask the user to review and confirm. They may:
- Approve all submissions
- Edit specific fields (modify the JSON files)
- Skip specific papers
- Cancel entirely

**CRITICAL: Do not submit without explicit user confirmation. Submissions to OpenReview are visible to venue organizers and cannot always be easily undone.**

### 8. Submit confirmed papers

**For a single paper**, use the submit command:

```bash
python3 "{SUBMIT_SCRIPT}" --config "{CONFIG_PATH}" submit \
    --venue "{VENUE}" \
    --submission-json "{SUBMISSION_JSON_PATH}" \
    --pdf-path "{PDF_PATH}"
```

**For multiple papers**, use batch-submit to avoid rate limiting. This uses a single API session and waits between submissions:

```bash
python3 "{SUBMIT_SCRIPT}" --config "{CONFIG_PATH}" batch-submit \
    --venue "{VENUE}" \
    --staging-dir "{STAGING_DIR}" \
    --wait-seconds 60
```

The batch-submit command:
- Finds all `*_submission.json` files in the staging directory
- Logs in once (single API session — avoids login rate limits)
- Submits each paper sequentially with `--wait-seconds` delay between them (default: 60s)
- Automatically retries on rate-limit or CAPTCHA errors with double the wait
- Uploads PDFs and supplementary files (including rebuttal PDFs for resubmissions)
- Outputs a JSON array of results at the end

**IMPORTANT:** OpenReview rate-limits logins to ~3 per 30 seconds and may trigger CAPTCHA after many rapid submissions. Always use batch-submit for 2+ papers. If CAPTCHA persists, increase `--wait-seconds` or submit the remaining paper(s) manually via the web interface.

### 9. Report

Print a summary table:

| Paper | Status | Note ID |
|-------|--------|---------|
| Title | SUCCESS/FAILED | note_id |

If any submissions failed, show the error details and suggest:
- Retrying with longer wait times (`--wait-seconds 120`)
- Submitting manually via the OpenReview web interface
- Checking the submission JSON for validation errors

**SAFETY REMINDERS:**
- Always confirm with the user before submitting
- Double-check author IDs — wrong IDs can cause issues
- Verify the venue deadline hasn't passed (check `duedate` from get-form)
- Never submit duplicate papers to the same venue
