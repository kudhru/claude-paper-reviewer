---
name: review-papers
description: Review one or more research papers through a structured multi-step pipeline. Each paper gets three focused agents that run in parallel.
argument-hint: [--paper FILE | --papers-dir DIR] --conference "NAME" [--reviews-dir DIR]
disable-model-invocation: true
allowed-tools: Bash(find *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *) Bash(date *)
---

# Review Papers

**Working directory:** !`pwd`
**Compile script:** `${CLAUDE_SKILL_DIR}/scripts/paper_review_compile.py`
**Detect script:** `${CLAUDE_SKILL_DIR}/scripts/detect_prompt_injection.py`
**Hallucination workflow:** !`cd "${CLAUDE_SKILL_DIR}/../check-hallucinations" && echo "$(pwd)/verify_references_workflow.md"`
**Default papers dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/papers"`
**Default reviews dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/reviews"`

Review one or more research papers through a fixed multi-step pipeline. Your only job in this session is orchestration — finding PDFs, creating output directories, and spawning agents. All reviewing happens inside agents.

## Arguments

Parse the following flags from `$ARGUMENTS`:

| Flag | Default | Description |
|------|---------|-------------|
| `--paper FILE` | — | Single PDF to review |
| `--papers-dir DIR` | default papers dir above | Directory of PDFs (all `*.pdf` files inside) |
| `--conference "NAME"` | ask user | Conference or venue name, e.g. `"ACL 2026"` |
| `--reviews-dir DIR` | default reviews dir above | Root output directory |

If neither `--paper` nor `--papers-dir` is given, use the **Default papers dir** shown above. If `--reviews-dir` is not given, use the **Default reviews dir** shown above. If `--conference` is missing from `$ARGUMENTS`, ask the user for it before doing anything else.

## Architecture

Each paper gets **four focused agents** spawned in parallel:

| Agent | Workflow | Role |
|-------|----------|------|
| **A** (paper-explanation) | [paper_explanation_workflow.md](paper_explanation_workflow.md) | Step 1. Reads the paper, writes explanation. Independent. |
| **B** (novelty-search) | [novelty_search_workflow.md](novelty_search_workflow.md) | Step 4. Reads the paper, does web search, writes novelty review. Independent. |
| **C** (main-review-chain) | [main_review_chain_workflow.md](main_review_chain_workflow.md) | Steps 0, 2, 3, 5 + compile. Reads the paper once, runs all analysis steps sequentially in one continuous conversation. Reads Agent B's and Agent D's output files from disk before compiling. |
| **D** (hallucination-check) | reuses [../check-hallucinations/verify_references_workflow.md](../check-hallucinations/verify_references_workflow.md) | Step 6. Reads the paper, extracts and web-verifies every reference, writes the hallucination check. Independent. |

Agent C is the quality-critical agent. It maintains context continuity across all analysis steps, building cumulative understanding of the paper.

Agent D reuses the standalone `check-hallucinations` skill's workflow verbatim, filled with a review-specific report filename so its output slots into the compiled review. Do not duplicate that workflow here.

## Orchestration Steps

1. **Resolve PDFs** — find all matching PDFs. Convert every path to an absolute path. Abort with a clear error if none are found.

2. **Resolve reviews-dir** — convert to absolute path. Create it with `mkdir -p` if it does not exist.

3. **Inform the user** — print: `Reviewing N paper(s) for CONFERENCE → REVIEWS_DIR`

4. **Read the four workflow templates:**
   - [paper_explanation_workflow.md](paper_explanation_workflow.md)
   - [novelty_search_workflow.md](novelty_search_workflow.md)
   - [main_review_chain_workflow.md](main_review_chain_workflow.md)
   - the **Hallucination workflow** file shown above (reused from the `check-hallucinations` skill)

5. **Prepare all papers** — for each PDF, compute:
   - `PAPER_STEM`: filename without `.pdf` extension
   - `TIMESTAMP`: current datetime as `YYYYMMDD_HHMMSS` (use a single timestamp for all papers in the batch, computed via `date +%Y%m%d_%H%M%S`)
   - `OUT_DIR`: `REVIEWS_DIR/PAPER_STEM_TIMESTAMP`
   - Create `OUT_DIR` with `mkdir -p`

6. **Spawn agents in batches of 4 papers** — process papers in batches of up to 4. For each batch:
   - For each paper in the batch, fill in the template variables in all four workflow templates, then spawn four `general-purpose` Agents (one per workflow):
     - Agents A, B, C use `{PDF_PATH}`, `{CONFERENCE}`, `{OUT_DIR}`, `{COMPILE_SCRIPT}`, `{DETECT_SCRIPT}`. `{DETECT_SCRIPT}` is the Detect script path shown above.
     - Agent D uses the reused Hallucination workflow with `{PDF_PATH}`, `{OUT_DIR}`, `{REPORT_FILENAME}` set to `06_hallucination_check.md`, and `{COMPILE_SCRIPT}` set to the literal `SKIP` (Agent C owns compilation, so Agent D must not compile or move the PDF).
   - Issue ALL Agent calls for the batch in a single response message so they run in parallel (up to 16 agents per batch).
   - Wait for all agents in the batch to complete before starting the next batch.

7. **Report** — after all batches finish, print one summary line per paper showing its output directory.

**Do not read any PDF yourself. Do not write any review content. Only orchestrate.**

## Supporting Files

- [paper_explanation_workflow.md](paper_explanation_workflow.md) — Agent A prompt template (step 1, paper explanation)
- [novelty_search_workflow.md](novelty_search_workflow.md) — Agent B prompt template (step 4, novelty and web search)
- [main_review_chain_workflow.md](main_review_chain_workflow.md) — Agent C prompt template (steps 0, 2, 3, 5, compile)
- [../check-hallucinations/verify_references_workflow.md](../check-hallucinations/verify_references_workflow.md) — Agent D prompt template (step 6, reference/hallucination check). Reused from the `check-hallucinations` skill, not duplicated. Filled with `{REPORT_FILENAME}=06_hallucination_check.md` and `{COMPILE_SCRIPT}=SKIP`.
- [scripts/detect_prompt_injection.py](scripts/detect_prompt_injection.py) — Step 0 forensic prompt-injection scan (text-layer instruction scan, zero-ink/hidden-text render check, glyph-substitution font analysis, metadata, annotations, JS, layers, embedded files). Requires PyMuPDF, falls back to poppler.
- [scripts/paper_review_compile.py](scripts/paper_review_compile.py) — assembles `full_review.md` from step files and converts to PDF
