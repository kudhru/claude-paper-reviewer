---
name: humanize-reviews
description: Humanize the conference-review output of the review-papers pipeline so it reads less AI-generated and scores lower on neural AI detectors, while preserving every fact, number, score, citation, and the Accept/Reject recommendation. Targets the 05_conference_review_*.md files, applies the two validated humanize-text levers, de-lists the Strengths/Weaknesses, and writes _humanized copies.
argument-hint: [--reviews-dir DIR | --file FILE ...] [--grammar-dose light|medium|heavy] [--recompile]
disable-model-invocation: true
allowed-tools: Bash(find *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *) Bash(grep *) Bash(python3 *)
---

# Humanize Reviews

**Working directory:** !`pwd`
**Default reviews dir:** !`cd "${CLAUDE_SKILL_DIR}/../../.." && echo "$(pwd)/reviews"`
**Compile script:** `${CLAUDE_SKILL_DIR}/../review-papers/scripts/paper_review_compile.py`
**Humanize method reference:** `${CLAUDE_SKILL_DIR}/../humanize-text/SKILL.md`

Rewrite the conference-review files produced by the `review-papers` pipeline so a modern neural AI detector scores them lower, while keeping each review accurate and submittable. Your job in this session is orchestration only. Find the conference-review files, spawn one humanizer agent per file, then report. All rewriting happens inside agents.

This skill is review-specific. It only touches the `05_conference_review_*.md` files (Part 1 review + Part 2 revision plan, plus any embedded novelty-review block in the same file). It never touches the explanation, readability, consistency, or novelty-search step files.

## Arguments

Parse from `$ARGUMENTS`:

| Flag | Default | Description |
|------|---------|-------------|
| `--reviews-dir DIR` | default reviews dir above | Humanize every `*/05_conference_review_*.md` under this dir |
| `--file FILE` | — | One or more explicit conference-review markdown files (repeatable) |
| `--grammar-dose light\|medium\|heavy` | `medium` | Lever 2 grammar-slip density. `light` ≈ 1 slip / 3 sentences, `medium` ≈ 1 / 2, `heavy` ≈ 1 / sentence |
| `--recompile` | off | After humanizing, recompile each paper's `full_review.pdf` from the humanized review |

If neither `--reviews-dir` nor `--file` is given, use the default reviews dir. If `--grammar-dose` is missing, ask the user which dose they want before spawning agents, and warn that `heavy` lowers detector scores most but costs readability in a review authors will read.

## Method (what each humanizer agent must do)

Read the full `humanize-text` SKILL.md (path above) for the rationale. The operational rules for a review file are:

**Lever 1 — rewrite the LLM structure (do first, thoroughly).**
- **De-list the Strengths and Weaknesses.** Turn the bulleted Strengths and Weaknesses into flowing paragraphs joined by conjunctions, subordination, and cause-and-effect. Keep the bold lead-in labels only if they read naturally inside prose, otherwise fold them in. Every listed point must survive as a sentence.
- **Thin in-paragraph enumerations** in the Summary and Recommendation. A sentence that packs a 4-6 item parallel list is a tell. Split items across shorter uneven sentences, fold some into clauses, group unevenly. Keep every fact.
- **Break templated parallel blocks.** Vary the opening and shape of repeated structures ("The X result restates…/The Y result restates…").
- **Keep as lists:** the embedded novelty-review citation entries (arXiv IDs, named works) and the numbered revision-plan action items. These are long, varied, genuinely parallel entries. Humanize the prose inside each item and break their templated parallelism, but do not dissolve the numbering or merge distinct actions.

**Lever 2 — light grammatical imperfection** at the chosen dose. Natural non-native slips only (dropped/extra articles, agreement slips, occasional wrong preposition or tense). Subtle and plausible, never broken English or typos. Slips go ONLY in ordinary connective prose.

**Final style cleanup (always).** No em-dashes, en-dashes, semicolons, or colons used to join clauses. No cliché AI-fingerprint vocabulary (delve, leverage, utilise, robust, comprehensive, seamless, underscore, pivotal, landscape, realm, and the like).

**Hard constraints (never violate).**
1. Preserve every fact, number, score, percentage, dataset name, model name, arXiv ID, citation, and proper noun verbatim.
2. Preserve all Markdown headings and section structure (`## Part 1`, `### 1. Paper Summary`, the `A.`/`B.` revision-plan groups). Do not reorder sections.
3. Preserve the Overall Recommendation verdict token exactly (e.g. **Reject**, **Weak Accept**). Only the surrounding justification prose may be rewritten.
4. Slips and edits never go inside numbers, math, names, citation keys, arXiv IDs, or technical terms.
5. The result must stay accurate and submittable.

## Orchestration steps

1. **Resolve files.** From `--file` args, or by globbing `*/05_conference_review_*.md` under the reviews dir. Convert to absolute paths. Abort with a clear error if none are found.
2. **Inform the user.** Print: `Humanizing N conference review(s) at <dose> grammar dose → *_humanized.md`
3. **Spawn one `general-purpose` agent per file**, in batches of up to 8, issuing each batch's Agent calls in a single message so they run in parallel. Each agent prompt must embed: the file path, the output path (same name with `_humanized` before `.md`), the chosen grammar dose, and the full Method above. The agent reads the file, rewrites it under the rules, writes the `_humanized.md` file, and returns one line.
4. **Verify.** For each humanized file, confirm it exists and that a spot-check of numbers and the recommendation token still matches the original (the agent reports this). If `--recompile` was passed, recompile that paper's bundle from the humanized review.
5. **Report.** One line per file: original → humanized path. Remind the user that the grammar slips are intentional and to proofread before submitting, especially that no slip landed on a number or claim.

**Do not rewrite any review content yourself. Only orchestrate.**
