# Paper Review Workflow — Claude Instructions

This file is used by two different agents. Read the section that applies to your role.

---

## ROLE A: Main Agent (Orchestrator)

You are the orchestrator. Your only job is to hand each paper off to a fresh sub-agent
and track what finished. You do NOT review papers yourself. You do NOT accumulate paper
content in your context.

### Step 1 — Read config
```bash
cat review_config.json
```

### Step 2 — Get inputs
You need:
- One or more PDF paths, OR a papers directory to scan
- The target conference name (e.g. "ACL 2026")

If not provided, ask before proceeding.

List available PDFs if needed:
```bash
python review_helpers.py list_papers --papers-dir ./papers
```

### Step 3 — For each paper: initialize and spawn a sub-agent

For EACH paper, run these two things:

**3a. Initialize output directory and state file:**
```bash
python review_helpers.py init_paper \
  --reviews-dir ./reviews \
  --abs-pdf <ABSOLUTE_PDF_PATH> \
  --conference "<CONFERENCE>"
```
Note the OUT_DIR it prints.

**3b. Check for an existing in-progress state (resume case):**
```bash
python review_helpers.py check_state \
  --reviews-dir ./reviews \
  --paper-stem <PAPER_STEM>
```
If not NONE, show the user and ask whether to resume. If resuming, pass the existing
OUT_DIR to the sub-agent instead of the new one.

**3c. Spawn a sub-agent for this paper.**

The sub-agent prompt must include ALL of the following — copy exactly:

---
You are a paper review agent. Your role is described under "ROLE B: Paper Agent" in CLAUDE.md.

Working directory: <ABSOLUTE_PATH_TO_COWORK_FOLDER>
Paper: <ABSOLUTE_PDF_PATH>
Conference: <CONFERENCE>
Output directory: <OUT_DIR>
State file: <ABSOLUTE_PATH_TO_COWORK_FOLDER>/reviews/<PAPER_STEM>_in_progress.json
Completed steps so far (empty if fresh run): <LIST_FROM_STATE_OR_EMPTY>

Read CLAUDE.md and review_prompts.json from the working directory, then follow
Role B instructions exactly. Return "DONE: <OUT_DIR>" on success or
"FAILED step <N>: <error message>" on failure.
---

### Step 4 — Run sub-agents

You may run multiple paper sub-agents in parallel if the user wants throughput.
Default: run them sequentially (safer, easier to debug).

### Step 5 — Report summary

After all sub-agents finish, report for each paper:
- Paper name
- Status: DONE or FAILED
- Output folder path
- Whether PDF was generated (check if full_review.pdf exists in OUT_DIR)

---

## ROLE B: Paper Agent (Worker)

You are a self-contained paper review agent. You review exactly ONE paper.
You have been given: working directory, PDF path, conference, output directory, state file.

**Rules (non-negotiable):**
1. Read `review_prompts.json` before doing anything. Use those prompt strings verbatim — never paraphrase or shorten them.
2. Never skip a step. Run all 6 steps (0–5) in order.
3. Steps 1 and 4 are always isolated sub-agents. Never run them in your own context.
4. Call `review_helpers.py` via bash for all file operations.
5. Do not improvise. If something is unclear, return FAILED with a description.

### Before starting

Read config and prompts:
```bash
cat <WORKING_DIR>/review_config.json
cat <WORKING_DIR>/review_prompts.json
```

Check completed steps from the state file you were given. Skip any step whose id
appears in `completed_steps`.

---

### Phase 1 — Step 0 in your own context, Steps 1 and 4 as parallel sub-agents

**Step 0 — Prompt Injection Check** (your own context — this starts the main chain)

Build the prompt:
```bash
python <WORKING_DIR>/review_helpers.py build_prompt \
  --prompts-file <WORKING_DIR>/review_prompts.json \
  --step-id 0 \
  --pdf-path <ABSOLUTE_PDF_PATH>
```
Use the printed prompt. Read the PDF and respond in your own context.

Save:
```bash
python <WORKING_DIR>/review_helpers.py save_step \
  --out-dir <OUT_DIR> --step-id 0 --label "Prompt Injection Check" \
  --response "<RESPONSE>" --state-file <STATE_FILE>
```

**Steps 1 and 4 — Spawn as parallel sub-agents (single message, two Agent calls)**

Build both prompts:
```bash
python <WORKING_DIR>/review_helpers.py build_prompt --prompts-file <WORKING_DIR>/review_prompts.json --step-id 1 --pdf-path <ABSOLUTE_PDF_PATH>
python <WORKING_DIR>/review_helpers.py build_prompt --prompts-file <WORKING_DIR>/review_prompts.json --step-id 4 --pdf-path <ABSOLUTE_PDF_PATH>
```

Spawn both sub-agents simultaneously. Each sub-agent:
- Receives its full prompt (already built above)
- Reads the PDF
- Returns only the final response text
- Step 4 sub-agent uses web search

Save both responses:
```bash
python <WORKING_DIR>/review_helpers.py save_step --out-dir <OUT_DIR> --step-id 1 --label "Paper Explanation" --response "<STEP_1_RESPONSE>" --state-file <STATE_FILE>
python <WORKING_DIR>/review_helpers.py save_step --out-dir <OUT_DIR> --step-id 4 --label "Novelty and Related Work" --response "<STEP_4_RESPONSE>" --state-file <STATE_FILE>
```

---

### Phase 2 — Steps 2 and 3 (your own context, continuation of step 0)

The paper is already in your context from step 0. Do NOT re-read it.

**Step 2 — Readability and Presentation**
```bash
python <WORKING_DIR>/review_helpers.py build_prompt --prompts-file <WORKING_DIR>/review_prompts.json --step-id 2
```
Send as continuation. Save:
```bash
python <WORKING_DIR>/review_helpers.py save_step --out-dir <OUT_DIR> --step-id 2 --label "Readability and Presentation" --response "<RESPONSE>" --state-file <STATE_FILE>
```

**Step 3 — Consistency and Completeness**
```bash
python <WORKING_DIR>/review_helpers.py build_prompt --prompts-file <WORKING_DIR>/review_prompts.json --step-id 3
```
Send as continuation. Save:
```bash
python <WORKING_DIR>/review_helpers.py save_step --out-dir <OUT_DIR> --step-id 3 --label "Consistency and Completeness" --response "<RESPONSE>" --state-file <STATE_FILE>
```

---

### Phase 3 — Step 5 (continuation from step 3, injects step 4 synthesis)

```bash
python <WORKING_DIR>/review_helpers.py build_prompt \
  --prompts-file <WORKING_DIR>/review_prompts.json \
  --step-id 5 \
  --conference "<CONFERENCE>" \
  --novelty-file <OUT_DIR>/04_novelty_and_related_work.md
```
Send as continuation from step 3. Save:
```bash
python <WORKING_DIR>/review_helpers.py save_step --out-dir <OUT_DIR> --step-id 5 --label "Conference Review — <CONFERENCE>" --response "<RESPONSE>" --state-file <STATE_FILE>
```

---

### Compile, convert, and clean up

```bash
python <WORKING_DIR>/review_helpers.py compile --out-dir <OUT_DIR> --paper-stem <PAPER_STEM> --conference "<CONFERENCE>"
python <WORKING_DIR>/review_helpers.py convert_pdf --md-path <OUT_DIR>/full_review.md
python <WORKING_DIR>/review_helpers.py move_paper --src <ABSOLUTE_PDF_PATH> --out-dir <OUT_DIR>
python <WORKING_DIR>/review_helpers.py clear_state --reviews-dir <WORKING_DIR>/reviews --paper-stem <PAPER_STEM>
```

Return: `DONE: <OUT_DIR>`

---

### Error handling

If any step fails:
- Save current state via the state file (already updated after each step)
- Return: `FAILED step <N>: <error description>`
- Do NOT continue to the next step
