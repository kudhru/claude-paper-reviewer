---
name: check-hallucinations
description: Verify that all references cited in a research paper actually exist by searching the web. Flags hallucinated, incomplete, or mismatched references.
argument-hint: [--paper FILE | --papers-dir DIR] [--out-dir DIR]
disable-model-invocation: true
allowed-tools: Bash(find *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *) Bash(date *)
---

# Check Hallucinations

**Working directory:** !`pwd`
**Compile script:** `${CLAUDE_SKILL_DIR}/scripts/compile_report.py`
**Default papers dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/papers_to_be_checked_for_hallucinations"`
**Default output dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/papers_checked_for_hallucinations"`

Verify that references in one or more research papers actually exist. Your only job in this session is orchestration -- finding PDFs, creating output directories, and spawning agents. All verification happens inside agents.

## Arguments

Parse the following flags from `$ARGUMENTS`:

| Flag | Default | Description |
|------|---------|-------------|
| `--paper FILE` | -- | Single PDF to check |
| `--papers-dir DIR` | -- | Directory of PDFs (all `*.pdf` files inside) |
| `--out-dir DIR` | default output dir above | Root output directory |

If neither `--paper` nor `--papers-dir` is given, ask the user which folder contains the papers to check. Suggest the **Default papers dir** shown above as the default option. Use whatever the user provides.

If `--out-dir` is not given, use the **Default output dir** shown above.

## Orchestration Steps

1. **Resolve PDFs** -- find all matching PDFs. Convert every path to an absolute path. Abort with a clear error if none are found.

2. **Resolve out-dir** -- convert to absolute path. Create it with `mkdir -p` if it does not exist.

3. **Inform the user** -- print: `Checking references in N paper(s) -> OUT_DIR`

4. **Read the workflow template:**
   - [verify_references_workflow.md](verify_references_workflow.md)

5. **Prepare all papers** -- for each PDF, compute:
   - `PAPER_STEM`: filename without `.pdf` extension
   - `TIMESTAMP`: current datetime as `YYYYMMDD_HHMMSS` (use a single timestamp for all papers in the batch, computed via `date +%Y%m%d_%H%M%S`)
   - `PAPER_OUT_DIR`: `OUT_DIR/PAPER_STEM_TIMESTAMP`
   - Create `PAPER_OUT_DIR` with `mkdir -p`

6. **Spawn agents in batches of 5 papers** -- process papers in batches of up to 5. For each batch:
   - For each paper in the batch, fill in the template variables (`{PDF_PATH}`, `{OUT_DIR}`, `{COMPILE_SCRIPT}`) in the workflow template, then spawn one `general-purpose` Agent per paper.
   - `{OUT_DIR}` is the per-paper `PAPER_OUT_DIR` (not the root output dir).
   - `{COMPILE_SCRIPT}` is the absolute path to the **Compile script** shown above.
   - Issue ALL Agent calls for the batch in a single response message so they run in parallel.
   - Wait for all agents in the batch to complete before starting the next batch.

7. **Report** -- after all batches finish, print one summary line per paper showing its output directory and the result counts reported by the agent.

**Do not read any PDF yourself. Do not perform any web searches. Only orchestrate.**

## Supporting Files

- [verify_references_workflow.md](verify_references_workflow.md) -- Agent workflow template (extract references, verify via web search, write report)
- [scripts/compile_report.py](scripts/compile_report.py) -- converts hallucination_check.md to PDF and moves the source PDF into the output directory
