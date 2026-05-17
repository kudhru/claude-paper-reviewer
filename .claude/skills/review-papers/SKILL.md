---
name: review-papers
description: Review one or more research papers through a structured multi-step pipeline. Each paper runs in its own isolated subagent following the paper_reviewer_v2 workflow.
argument-hint: [--paper FILE | --papers-dir DIR] --conference "NAME" [--reviews-dir DIR]
disable-model-invocation: true
allowed-tools: Bash(find *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *)
---

# Review Papers

**Working directory:** !`pwd`
**Compile script:** `${CLAUDE_SKILL_DIR}/scripts/paper_review_compile.py`
**Default papers dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/papers"`
**Default reviews dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/reviews"`

Review one or more research papers through a fixed multi-step pipeline. Your only job in this session is orchestration — finding PDFs and spawning one subagent per paper. All reviewing happens inside subagents.

## Arguments

Parse the following flags from `$ARGUMENTS`:

| Flag | Default | Description |
|------|---------|-------------|
| `--paper FILE` | — | Single PDF to review |
| `--papers-dir DIR` | default papers dir above | Directory of PDFs (all `*.pdf` files inside) |
| `--conference "NAME"` | ask user | Conference or venue name, e.g. `"ACL 2026"` |
| `--reviews-dir DIR` | default reviews dir above | Root output directory |

If neither `--paper` nor `--papers-dir` is given, use the **Default papers dir** shown above. If `--reviews-dir` is not given, use the **Default reviews dir** shown above. If `--conference` is missing from `$ARGUMENTS`, ask the user for it before doing anything else.

## Orchestration Steps

1. **Resolve PDFs** — find all matching PDFs. Convert every path to an absolute path. Abort with a clear error if none are found.
2. **Resolve reviews-dir** — convert to absolute path. Create it with `mkdir -p` if it does not exist.
3. **Inform the user** — print: `Reviewing N paper(s) for CONFERENCE → REVIEWS_DIR`
4. **Read the workflow** — read [per_paper_workflow.md](per_paper_workflow.md). This is the prompt template you will use for each subagent.
5. **Spawn one Agent per paper** — for each PDF, fill in `{PDF_PATH}`, `{CONFERENCE}`, `{REVIEWS_DIR}`, and `{COMPILE_SCRIPT}` (the compile script path shown above) in the template from per_paper_workflow.md, then spawn a `general-purpose` Agent using that filled-in text as the prompt. If there are multiple papers, issue all Agent calls in a single response message so they run in parallel.
6. **Report** — after all subagents finish, print one summary line per paper showing its output directory.

**Do not read any PDF yourself. Do not write any review content. Only orchestrate.**

## Supporting Files

- [per_paper_workflow.md](per_paper_workflow.md) — full per-paper subagent prompt template (read before spawning agents)
- [scripts/paper_review_compile.py](scripts/paper_review_compile.py) — assembles `full_review.md` from step files and converts to PDF; run it via Bash at the end of each paper's review
