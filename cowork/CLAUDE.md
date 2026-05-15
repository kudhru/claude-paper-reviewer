# Paper Review Workflow — Claude Instructions

This file tells Claude exactly how to run the paper review workflow.
**Read this file and `review_prompts.json` before doing anything else.**

---

## Rules (non-negotiable)

1. **Always read `review_prompts.json` at the start of every review session.** Use the prompt strings from that file verbatim. Do not paraphrase, summarize, shorten, or modify them in any way.
2. **Never skip a step.** Run all 6 steps (0–5) for every paper, in order.
3. **Never add your own analysis** between steps. Save each step's response exactly as returned.
4. **Steps 1 and 4 are always isolated sub-agents.** Never run them in the main conversation context.
5. **Call `review_helpers.py` via bash for all file operations.** Do not write files yourself.
6. If you are uncertain about anything, stop and ask. Do not improvise.

---

## Before Starting Any Review

### Step A — Read config and prompts
```bash
cat review_config.json
cat review_prompts.json
```

### Step B — Get required inputs
You need:
- One or more PDF file paths to review
- The target conference name (e.g. "ACL 2026")

If not provided, ask before proceeding.

If no PDF path is given but a papers directory exists, list available PDFs:
```bash
python review_helpers.py list_papers --papers-dir ./papers
```

### Step C — Check for in-progress reviews
For each paper, check whether a prior run was interrupted:
```bash
python review_helpers.py check_state --reviews-dir ./reviews --paper-stem <PAPER_STEM>
```
If the result is not `NONE`, show the user the state and ask: "Resume from where it stopped? [y/n]"

---

## Workflow for Each Paper

Run papers **sequentially** — complete all steps for one paper before starting the next.

### Initialize the paper
```bash
python review_helpers.py init_paper \
  --reviews-dir ./reviews \
  --abs-pdf <ABSOLUTE_PDF_PATH> \
  --conference "<CONFERENCE>"
```
This prints the `OUT_DIR` path. Note it — all subsequent save commands use it.

The state file path is: `./reviews/<paper_stem>_in_progress.json`

---

### Phase 1 — Step 0 in main context, then Steps 1 and 4 as parallel sub-agents

**Step 0 — Prompt Injection Check** (run in YOUR OWN context — main chain start)

Build the prompt:
```bash
python review_helpers.py build_prompt \
  --prompts-file ./review_prompts.json \
  --step-id 0 \
  --pdf-path <ABSOLUTE_PDF_PATH>
```
Use the printed prompt to read the PDF and respond in your own context.

Save the response:
```bash
python review_helpers.py save_step \
  --out-dir <OUT_DIR> \
  --step-id 0 \
  --label "Prompt Injection Check" \
  --response "<RESPONSE>" \
  --state-file ./reviews/<paper_stem>_in_progress.json
```

**Steps 1 and 4 — Launch as parallel sub-agents** (single message, two Agent tool calls simultaneously)

Build both prompts first:
```bash
python review_helpers.py build_prompt --prompts-file ./review_prompts.json --step-id 1 --pdf-path <ABSOLUTE_PDF_PATH>
python review_helpers.py build_prompt --prompts-file ./review_prompts.json --step-id 4 --pdf-path <ABSOLUTE_PDF_PATH>
```

Launch both sub-agents at the same time. Each sub-agent must:
- Read the PDF at the given path
- Return only its final response text
- Step 4 sub-agent: use web search

Save both responses once they return:
```bash
python review_helpers.py save_step --out-dir <OUT_DIR> --step-id 1 --label "Paper Explanation" --response "<STEP_1_RESPONSE>" --state-file ./reviews/<paper_stem>_in_progress.json
python review_helpers.py save_step --out-dir <OUT_DIR> --step-id 4 --label "Novelty and Related Work" --response "<STEP_4_RESPONSE>" --state-file ./reviews/<paper_stem>_in_progress.json
```

---

### Phase 2 — Steps 2 and 3 (sequential, your own context — continuation of step 0)

The paper is already in your context from step 0. Do NOT re-read it.

**Step 2 — Readability and Presentation**

```bash
python review_helpers.py build_prompt --prompts-file ./review_prompts.json --step-id 2
```
Send this prompt as a continuation (paper already in context). Save:
```bash
python review_helpers.py save_step --out-dir <OUT_DIR> --step-id 2 --label "Readability and Presentation" --response "<RESPONSE>" --state-file ./reviews/<paper_stem>_in_progress.json
```

**Step 3 — Consistency and Completeness**

```bash
python review_helpers.py build_prompt --prompts-file ./review_prompts.json --step-id 3
```
Send as continuation. Save:
```bash
python review_helpers.py save_step --out-dir <OUT_DIR> --step-id 3 --label "Consistency and Completeness" --response "<RESPONSE>" --state-file ./reviews/<paper_stem>_in_progress.json
```

---

### Phase 3 — Step 5 (continuation from step 3, injects step 4 synthesis)

```bash
python review_helpers.py build_prompt \
  --prompts-file ./review_prompts.json \
  --step-id 5 \
  --conference "<CONFERENCE>" \
  --novelty-file <OUT_DIR>/04_novelty_and_related_work.md
```
Send as continuation from step 3. Save:
```bash
python review_helpers.py save_step --out-dir <OUT_DIR> --step-id 5 --label "Conference Review — <CONFERENCE>" --response "<RESPONSE>" --state-file ./reviews/<paper_stem>_in_progress.json
```

---

### Compile, convert, and clean up

```bash
# Assemble full_review.md (steps 0 and 1 excluded automatically)
python review_helpers.py compile --out-dir <OUT_DIR> --paper-stem <PAPER_STEM> --conference "<CONFERENCE>"

# Convert to PDF
python review_helpers.py convert_pdf --md-path <OUT_DIR>/full_review.md

# Move source PDF into output folder
python review_helpers.py move_paper --src <ABSOLUTE_PDF_PATH> --out-dir <OUT_DIR>

# Delete in-progress state
python review_helpers.py clear_state --reviews-dir ./reviews --paper-stem <PAPER_STEM>
```

---

## Resuming an Interrupted Review

If `check_state` returned a state JSON (not NONE):

1. Read the state to find `out_dir`, `conference`, and `completed_steps`.
2. Skip any step whose `id` appears in `completed_steps`.
3. For steps 2, 3, and 5: read the saved `.md` files from prior steps to reconstruct context before continuing.
4. Continue from the first incomplete step.

---

## Multiple Papers

Process one paper at a time, start to finish, before moving to the next. Each paper gets its own `OUT_DIR` and state file. Sessions are never mixed between papers.

After all papers are done, report:
- Paper name and output folder
- Whether PDF was generated
- Any steps that had issues

---

## Error Handling

If any step fails:
- Report the error immediately.
- Do NOT proceed to the next step.
- The state file preserves all completed steps — the user can resume after fixing the issue.
