---
name: cut-ai-slop
description: Cut AI-sloppy language from writing, research papers first. Removes AI tells and clichés (formulaic openers, importance inflation, superficial -ing analysis, filler transitions, em-dashes, overclaiming) while preserving meaning, numbers, citations, and technical terms. Outputs a clean rewritten draft. This is a quality editor, it never adds grammar errors or invents content. For a whole-paper rewrite, a section-wise pipeline splits the paper and rewrites each section, LaTeX preferred and PDF best-effort.
argument-hint: [<text|file|dir>] [--paper] [--format plain|latex|markdown|docx] [--out PATH] [--batch]  (whole paper: --rewrite-paper --source PATH [--format latex|text])
disable-model-invocation: true
allowed-tools: Read Write Edit Bash(python3 *) Bash(cp *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *)
---

# Cut AI Slop

**Skill dir:** !`pwd`
**Pattern catalog:** `${CLAUDE_SKILL_DIR}/references/ai_slop_patterns.md`
**Scanner:** `${CLAUDE_SKILL_DIR}/scripts/scan_ai_slop.py`
**Section splitter:** `${CLAUDE_SKILL_DIR}/scripts/split_paper.py`
**Paper rewrite workflow:** `${CLAUDE_SKILL_DIR}/paper_rewrite_workflow.md`

Rewrite text so it stops reading as machine-generated, while keeping it accurate and, for
papers, submittable. The catalog at the path above is the single source of truth for what
counts as slop and, just as important, the research-paper carve-outs that keep it from
firing on prose that is correct in academic writing. Read the catalog before editing.

## What this is, and what it is not

This is a **quality editor**. It removes AI tells and clichés so the prose reads like a
careful human wrote it. It is the opposite of the `humanize-text` skill on one axis:

- `humanize-text` lowers neural AI-**detector** scores and deliberately **adds** small
  grammar errors and de-lists structure. Its goal is evasion, and quality can suffer.
- `cut-ai-slop` improves writing **quality**. It **never** adds grammar errors, never
  invents content, and never games a detector. The two are complementary, not the same.

## The golden rule

You may subtract and sharpen. You may not add. Cut filler, make an existing claim concrete
from material already in the text, surface a buried point. Never introduce a number, name,
date, citation, result, stance, or personality the source did not contain. In a paper a
fabricated specific is a research-integrity failure, so when a supporting detail is
missing, flag the gap, do not fill it.

## Sentence length (best-effort target)

Prefer sentences under 20 words. Split long sentences (20 or more words) where a natural
boundary exists and the split reads better. Apply this as much as possible, but it is a target,
not a strict cap. This applies to direct rewrites and to the section-wise paper rewrite. Leave a long
sentence intact when splitting would make it choppy, force an awkward break, or blur a precise
claim, and never manufacture staccato. Splitting restructures only, it never adds content. The
scanner flags long sentences (`--max-sentence-words`, default 20) as an advisory recall aid, not
a mandate.

## Output

The skill produces a **clean rewritten draft** only. It outputs the rewritten document with
structure and headings preserved, ready to paste, with no original-versus-updated diff.

## Paper mode vs general

- Pass `--paper` (auto-on when `--format=latex` or the file is `.tex`) to apply only the
  catalog entries tagged `[paper]` or `[both]`, honor the cluster and density thresholds,
  and apply the **research-paper carve-outs** in section 6 of the catalog. This keeps
  academic prose quiet and precise.
- Without `--paper`, apply the `[both]` entries. The `[general]` extensions (blogs, social,
  marketing) are deferred and listed in the catalog appendix, do not apply them yet.

## Full paper rewrite (section-wise)

The direct rewrite above handles text you pass in. To rewrite an ENTIRE paper into a clean draft,
use the section-wise pipeline in [paper_rewrite_workflow.md](paper_rewrite_workflow.md). It
splits the paper into sections with `scripts/split_paper.py`, hands each section to its own
agent under a shared context pack so terminology stays consistent, stitches the result, and
re-scans to verify the tells are gone. Always ask for the LaTeX source first, prose is
rewritten while math, citations, numbers, and labels are preserved exactly. If only a PDF is
available it runs best-effort on extracted text and says so. Use this when the user wants the
whole paper rewritten rather than a snippet. The scanner supplies recall
and reproducible counts, the agents supply judgment and catch the semantic slop regex cannot
see. Both are used, neither alone is trusted.

## Hard constraints (never violate)

1. Preserve every fact, number, statistic, result, dataset name, model name, proper noun,
   acronym, and technical term verbatim.
2. Preserve every citation, `\cite{}` key, reference marker, URL, footnote, equation, and
   label verbatim. Never add or remove a citation.
3. `latex`: touch only prose. Preserve every command, math environment, table, figure, and
   `\cite{}`. `markdown`: preserve headings, code, tables, links. Edits go only in ordinary
   connective prose.
4. Never introduce grammar errors, and never add the "never inject" items from catalog
   section 1 (fake first person, manufactured stakes, forced contrarianism, performed
   candor, em-dash theatrics, staccato conversion, invented specifics).
5. Do not reorder sections or change headings. Keep the author's register. For encyclopedic
   or technical text, plain and neutral is the correct human voice, do not add personality.
6. For `docx`, never modify the original. Copy to `name_deslop.docx` and edit the copy in
   place, rewriting only prose runs.

## What Claude does when invoked

1. **Parse input.** A directory with `--batch`: enumerate `.txt`/`.tex`/`.md` recursively.
   A file: read it. Inline text: use directly. Auto-detect `--format` from the extension if
   unset (`.tex`→latex and paper mode, `.md`→markdown, `.docx`→docx, else plain).
2. **Pre-scan (optional but recommended).** Run the scanner to get a fast list of candidate
   spans, then judge each one against the catalog. The scanner flags candidates, it does not
   decide, you do.

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/scan_ai_slop.py" --file "<path>" [--paper] [--json]
   ```

3. **Edit against the catalog.** Apply the golden rule and the hard constraints. In paper
   mode, apply the carve-outs so you do not "fix" correct academic phrasing (statistical
   "significant", technical "robust", required hedging, Methods passive, genuine lists).
4. **Produce the clean rewritten output** (see below).
5. **Self-check.** Re-read the result. Confirm no number, citation, or claim changed, and
   that no new AI tell was introduced by the rewrite. Fix and re-check if needed.

## Output format

Output only the rewritten document, structure and headings preserved, ready to paste. With
`--out`, write it there (batch mirrors the input tree, appending `_deslop` before the
extension). For `docx`, write the edited copy as `name_deslop.docx`. Return only the
rewritten text, no preamble.

## Options

- `--paper` — apply paper carve-outs and only `[paper]`/`[both]` patterns.
- `--format plain|latex|markdown|docx` — what markup to preserve (default: auto-detect).
- `--out PATH` — write output to a file or directory instead of the terminal.
- `--batch` — process every `.txt`/`.tex`/`.md` under a directory, mirror under `--out`.

## Examples

```
/cut-ai-slop "In recent years, X has attracted increasing attention."   # inline, prints the rewrite
/cut-ai-slop path/to/intro.tex --paper --out path/to/intro_deslop.tex
/cut-ai-slop path/to/paper_dir/ --paper --batch --out path/to/deslopped/
```

## Scope and honesty

The flagged patterns are statistically more common in AI text, but real papers, deadline
writing, and second-language authors produce the same shapes. They are signals, not proof.
Never use this skill's output as evidence that a human did or did not write something. Its
job is to make the writing better, not to render a verdict.

## Attribution

Pattern catalog adapted, in our own words, from two MIT-licensed skills: `avoid-ai-writing`
by Conor Bronsdon and `no-ai-slop` by Peter Yang. See the catalog header for details.
