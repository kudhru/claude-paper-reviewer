# Paper Rewrite Workflow (section-wise, clean)

The full de-slop rewrite of a paper. It produces a clean rewritten draft, section by section,
with each section handled by its own agent under a shared context pack so the sections stay
consistent. It shares the one pattern catalog with the rest of the skill.

Use this when the user wants the paper itself rewritten, not a list of suggestions.

## Preferred input: the LaTeX source

Always ask for the LaTeX source first. On the source we rewrite prose only and preserve every
command, math environment, number, citation, label, table, and figure exactly. If the source
is not available, fall back to text extracted from the PDF and tell the user plainly that this
is a best-effort draft, not a final submission (PDF extraction loses structure, and submission
PDFs often interleave margin line numbers into the text).

Template variables used below: `{SOURCE}` (the .tex or .txt), `{FORMAT}` (`latex` or `text`),
`{WORKDIR}` (a working directory), `{SCRIPTS}` (this skill's `scripts/` dir), `{CATALOG}`
(`references/ai_slop_patterns.md`).

---

## Step 0 — Obtain the source

- If the user gave a `.tex` (or a directory with a main `.tex`), use `{FORMAT}=latex`.
- If only a PDF is available, extract text first and use `{FORMAT}=text`:

  ```bash
  pdftotext "PAPER.pdf" "{WORKDIR}/paper.txt"
  ```

  Warn: best-effort. Offer to proceed only after the user accepts the caveat, or ask them to
  share the LaTeX.

## Step 1 — Split into sections and build the context pack

```bash
python3 "{SCRIPTS}/split_paper.py" --input "{SOURCE}" --format {FORMAT} --out "{WORKDIR}/sections"
```

This writes `00_front.*` (front matter, not rewritten), one `NN_<slug>.*` per rewritable
section, `zz_tail.*` (bibliography and appendix, not rewritten), `context_pack.md`, and
`manifest.json`. Read `manifest.json` to get the ordered section list.

Optionally, precompute per-section candidates so each agent starts from a checklist:

```bash
for f in "{WORKDIR}/sections/"[0-9][0-9]_*.*; do
  python3 "{SCRIPTS}/scan_ai_slop.py" --file "$f" --paper > "$f.scan.txt"
done
```

## Step 2 — Rewrite each section (one agent per section, in parallel)

Process sections in batches (up to 6 agents at a time). For each rewritable section in
`manifest.json`, spawn one `general-purpose` agent with the prompt below, filled in.

Do NOT spawn an agent for `00_front.*` or `zz_tail.*`. Those are preserved verbatim.

### Per-section agent prompt

```
You are rewriting ONE section of a research paper to remove AI-sloppy language, while
preserving every fact. You are a quality editor, not a detector-evader. Never add content.

Section file (rewrite this): {SECTION_FILE}
Its scanner candidate list (if present): {SECTION_FILE}.scan.txt
Shared context pack (read for consistency, do not rewrite it): {WORKDIR}/sections/context_pack.md
Pattern catalog: {CATALOG}
Format: {FORMAT}   (latex: touch prose only, preserve all commands, math, \cite, labels,
tables, figures. text: preserve numbers, names, citations.)

Rules:
1. Read the context pack first. Keep terminology, notation, and claims consistent with it.
   Do not restate or contradict the abstract.
2. Read the catalog. Apply [paper] and [both] patterns and the section 6 research-paper
   carve-outs (statistical "significant", technical "robust", required hedging, Methods
   passive, genuine parallel lists, defined-term repetition).
3. Golden rule: subtract and sharpen only. Never add a number, dataset, result, citation, or
   claim the section does not already contain. If a cleaner sentence would need a missing
   detail, keep the original meaning and mark it [PLACEHOLDER: what is missing]. Preserve
   every number, name, citation key, equation, and label verbatim.
4. Work the scanner candidates AND do your own semantic pass (importance inflation,
   superficial -ing analysis, overclaiming, formulaic openers, filler openers). Rewrite genuine
   tells. Leave list-separator semicolons, numeric ranges, and carve-out words alone. Also prefer
   sentences under 20 words: split long sentences (20 or more) where a natural boundary reads
   better, as much as possible but not forced, and never into choppy staccato. Splitting adds no
   content. Preserve every number, citation, and term when splitting.
5. Do not change section order or headings. Do not touch anything outside this section.

Write the rewritten section to {OUT_SECTION_FILE}, same format, ready to drop in. Then print
one line: `Section rewritten: {OUT_SECTION_FILE}` and a one-line note of how many edits you made.
```

Fill `{OUT_SECTION_FILE}` as `{WORKDIR}/rewritten/NN_<slug>.<ext>` (same basename as the input
section). Issue each batch's agent calls in a single message so they run in parallel. Wait for a
batch before starting the next.

## Step 3 — Stitch

Reassemble in manifest order: `00_front` + every rewritten section (ascending index) + `zz_tail`.

```bash
python3 - <<'PY'
import json, pathlib
work = pathlib.Path("{WORKDIR}")
man = json.loads((work/"sections"/"manifest.json").read_text())
ext = "tex" if man["format"]=="latex" else "txt"
parts = []
if man["front"]: parts.append((work/"sections"/man["front"]).read_text())
for s in man["sections"]:
    rw = work/"rewritten"/s["file"]
    parts.append(rw.read_text() if rw.exists() else (work/"sections"/s["file"]).read_text())
if man["tail"]: parts.append((work/"sections"/man["tail"]).read_text())
out = work/f"paper_deslop.{ext}"
out.write_text("\n".join(parts))
print("stitched:", out)
PY
```

For LaTeX this yields a compilable document (front has the preamble and `\begin{document}`, tail
has the bibliography and `\end{document}`). Do not try to compile it yourself unless asked.

## Step 4 — Verify

1. Re-scan the stitched result and compare candidate counts to the original:

   ```bash
   python3 "{SCRIPTS}/scan_ai_slop.py" --file "{WORKDIR}/paper_deslop.{ext}" --paper
   ```

   Mechanical tells (em-dashes, en-dash connectors, semicolon splices, 2A words) should drop
   sharply. Report the before and after numbers.

2. Spawn ONE consistency-check agent over the stitched draft. Its job: confirm terminology is
   consistent across sections, confirm no section added a fact/number/citation the original
   lacked (spot-check against the original), confirm the abstract is not duplicated in a body
   section, and flag any [PLACEHOLDER] markers for the user to fill from the real work. It
   reports issues only, it does not rewrite.

## Step 5 — Report

Tell the user where `paper_deslop.<ext>` is, the before/after scanner counts, any [PLACEHOLDER]
markers that need a real value, and the consistency-check findings. Remind them to proofread,
and if this was the text/PDF path, repeat that it is a best-effort draft and the LaTeX source
would give a clean, submittable result.

## Notes

- Preserve, never invent. The golden rule is the whole point. A rewrite that fabricates a
  specific is worse than the vague phrasing it replaced.
- The scanner gives recall (never miss a mechanical tell) and reproducible counts. The agents
  give judgment and catch the semantic slop regex cannot see. Use both.
- For a shorter job (one section, or an audit rather than a rewrite), use the standalone
  `cut-ai-slop` modes instead of this whole pipeline.
