---
name: pangram-check
description: Check which portions of a review (or any text file) are flagged as AI-generated using the Pangram Python SDK. Reports a document-level verdict plus every flagged segment, mapped to the review section it falls under. Works on the humanized reviews or any files you drop into the check folder.
argument-hint: [--file FILE ...] [--input-dir DIR] [--threshold 0.5] [--out-dir DIR]
disable-model-invocation: true
allowed-tools: Bash(find *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *) Bash(python3 *) Bash(cp *)
---

# Pangram Check

**Working directory:** !`pwd`
**Check script:** `${CLAUDE_SKILL_DIR}/scripts/pangram_check.py`
**API key file:** `${CLAUDE_SKILL_DIR}/.env`  (you create this; one line `PANGRAM_API_KEY=...`)
**Default check folder:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/pangram_to_check"`

Run Pangram's per-segment AI detector over text files and report which portions read as AI-generated. Uses the Pangram Python SDK (`predict`), which returns a document verdict and a `windows` array of per-segment results. The script maps each flagged segment back to the nearest Markdown heading, so you see which part of the review tripped the detector.

## One-time setup

1. Install the SDK into the project venv:

   ```bash
   pip install pangram-sdk
   ```

2. Create the API key file at `${CLAUDE_SKILL_DIR}/.env` with a single line:

   ```
   PANGRAM_API_KEY=your_key_here
   ```

   The script loads this automatically. It is gitignored, so the key is never committed. (`PANGRAM_API_KEY` set in the environment also works and takes precedence.)

## The check folder

Put any files you want to check into the **Default check folder** above (`pangram_to_check/`). Update that folder whenever you want, then re-run this skill to re-check. The scan picks up `.md`, `.txt`, and `.tex` files and skips its own `*.pangram.md` report files. To check files elsewhere instead, pass `--file` (repeatable) or `--input-dir DIR`.

## Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--file FILE` | — | One or more specific files to check (repeatable). Overrides the folder scan. |
| `--input-dir DIR` | default check folder above | Folder to scan when no `--file` is given |
| `--ext EXT` | `.md .txt .tex` | Extensions to include in a folder scan (repeatable) |
| `--threshold N` | `0.5` | Flag a segment when its `ai_assistance_score` >= N (segments Pangram labels AI / AI-Assisted / Mixed are always flagged) |
| `--out-dir DIR` | next to each input | Where to write the `<name>.pangram.md` reports |
| `--json PATH` | — | Also write all findings as one JSON file |

## Steps

1. **Check setup.** Confirm `${CLAUDE_SKILL_DIR}/.env` exists with `PANGRAM_API_KEY`. If not, tell the user to create it (see setup above) and stop. Confirm the SDK imports (`python3 -c "import pangram"`); if not, tell them to `pip install pangram-sdk`.

2. **Resolve inputs.** Use `--file` args if given, else scan `--input-dir` (default check folder). If the folder is empty, tell the user to drop files in and stop.

3. **Run the detector:**

   ```bash
   python3 "{CHECK_SCRIPT}" [--file FILE ...] [--input-dir DIR] [--threshold N] [--out-dir DIR] [--json PATH]
   ```

4. **Report.** Show the printed summary table (verdict, AI / AI-assisted / human fractions, flagged-segment count per file). For each file with flagged segments, summarize which review sections were flagged and quote the worst few segments from its `<name>.pangram.md` report. Point the user at the per-file reports.

5. If the user wants to lower the flags, hand the flagged sections to the `humanize-reviews` skill (heavier dose on exactly those sections), then re-run this check.

**Notes**
- Pangram is a paid API. Each `predict` call on a file consumes quota. Only the files in scope are sent.
- The review text is sent to Pangram's servers. Do not check anything that must not leave the machine.
- `.docx`, `.pdf`, and `.rtf` are supported by the SDK's `predict_file`, but this skill targets the Markdown review files via `predict` on their text.
