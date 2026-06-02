---
name: humanize-text
description: Rewrite AI-generated text to lower neural AI-detector scores (e.g. Turnitin) while preserving meaning, citations, and structure. Uses two validated levers — structural rewriting (de-listing and thinning parallel enumeration) and light grammatical imperfection — not perplexity/burstiness tactics.
argument-hint: [<text|file_path|directory>] [--out=<path>] [--format=plain|latex|markdown|docx] [--batch]
disable-model-invocation: true
allowed-tools: Read Write Edit Bash(python3 *) Bash(cp *) Bash(ls *) Bash(pwd) Bash(realpath *) Bash(mkdir *)
---

# Humanize Text

Rewrite AI-generated text so a modern neural AI detector (such as Turnitin) scores it lower,
while keeping the document accurate, readable, and submittable.

## What to know about the target

Modern detectors are transformer classifiers trained on human vs. LLM text. They score the
document **per segment** (roughly per paragraph), and they key on the *fluent regularities of
LLM prose*: clean grammar, plus the parallel, list-like, evenly-packed structure of machine
writing (every sentence smooth, every point delivered as a tidy enumeration). Two consequences:

- Surface edits do nothing. Swapping synonyms, changing punctuation, or "varying sentence
  rhythm" keeps the text fluent — which is what the classifier detects. These can even raise
  the score, because crisp, punchy, high-variance prose is itself a hallmark of LLM output.
- You lower the score by leaving the fluent-LLM manifold in ways associated with human
  writing: less parallel/list-like structure, and small natural imperfections.

## The two levers (apply in this order)

**Lever 1 — Rewrite the LLM architecture (biggest effect, little or no readability cost).**
This does most of the score reduction, so do it first and thoroughly. The signal is not only
bullet lists — it is the *parallel, evenly-packed structure* of machine prose. Attack all
three forms of it:

- **De-list.** Turn bulleted/numbered lists of short procedural sentences ("We encode each X.
  That lets us do Y.") into flowing paragraphs joined by conjunctions, subordination and
  cause-and-effect. Keep lists only when the items are long, varied, genuinely parallel entries
  (comparison rows, numbered research questions).
- **Thin in-paragraph enumerations.** A sentence that packs a 4–6 item parallel list
  ("A, B, C, D and E") is a strong tell even with no bullet in sight. Stop naming everything in
  one breath: split the items across shorter, uneven sentences, fold some into clauses, or group
  them unevenly. Keep every fact — just stop presenting it as a tidy catalogue.
- **Break templated parallel blocks.** Kill repetition such as "The main X is…/The main Y
  is…" (anaphora), "The first phase focuses on…/This phase will…" (section templates), and
  component-by-component runs ("The crop module does…; the water module does…; the energy
  module does…"). Vary the opening and shape of each, merge some, let some be short.

Preserve every fact and citation in the reflow. These patterns concentrate in *technical and
methods* sections (catalogues of sensors, steps, objectives, components) — that is where the
signal survives a naive de-list, so restructure those hardest.

**Lever 2 — Light grammatical imperfection.**
LLMs almost never make genuine grammar errors, so clean grammar is itself the tell. Introduce
natural, non-native-style slips at about **one per 2–3 sentences**:

- dropped or extra articles, subject–verb agreement slips, singular/plural slips, the
  occasional wrong preposition or tense.
- Keep them subtle and plausible — a fluent non-native author, never broken English or typos.
- Vary the error type. Use the lightest density that works; heavier helps but costs readability.

**Dose by section.** The two halves of a document behave differently. Argument and narrative
prose (motivation, novelty, impact) usually clears at very light grammar once the architecture
is rewritten. Technical and methods sections are the stronghold — they stay parallel and dense
even after de-listing, so restructure them hardest (thin the enumerations) and, only if they
still flag, add a bit more grammatical slip there specifically. Spend effort where the detector
flags, not uniformly.

## Hard constraints (never violate)

1. Preserve all facts, numbers, arguments, and conclusions exactly.
2. Preserve all technical terms, jargon, proper nouns, acronyms, and named entities verbatim.
3. Preserve all citations, reference markers, URLs, and footnotes verbatim.
4. `latex`: preserve every command, math environment, label, table, figure, and `\cite{}`;
   only touch prose. `markdown`: preserve headings, code, tables, links; only touch prose.
5. Slips and edits go ONLY in ordinary connective prose — never inside numbers, math, names,
   citation keys, or technical terms.
6. Output must stay accurate and submittable. No reordered sections or changed headings.
7. For binary formats (e.g. `.docx`), never modify the original. Make a copy (e.g.
   `name_humanized.docx`) and edit the copy in place: preserve its styles, tables and figures,
   and rewrite only the prose runs (e.g. via `python-docx`). Do not regenerate the file from
   scratch (a converter round-trip loses the author's formatting).

## Do NOT do these (they don't lower neural-detector scores)

- Increasing "burstiness" / alternating very short and very long sentences.
- Inserting short punchy crystallizing sentences.
- Swapping common words for rarer synonyms to inflate "perplexity".
- Adding hedges, asides, or stance markers for their own sake.
- Misspellings, broken syntax, or word salad.
- Treating em-dash / semicolon / cliché-AI-word removal as a *score* tactic — it does not move
  the detector. (We still remove them, but for style, not score — see the next section.)

## Final style cleanup (always apply)

Independent of the detector score, the humanized output must read like clean human prose, so
finish every rewrite with this pass and never re-introduce these markers while rewriting:

- **No em-dashes, semicolons, or colons used to join clauses.** Split into separate sentences,
  or use a comma with a conjunction. (A colon introducing a genuine list is fine.)
- **No cliché AI-fingerprint vocabulary** — "delve", "leverage", "utilise", "harness", "robust",
  "seamless", "pivotal", "comprehensive", "underscore", "tapestry", "landscape", "realm", and
  the like. Replace each with a plain, specific word.

These do not lower the detector score on their own, but they are required house style: they keep
the text from looking AI-written to a *human* reader. Apply them after Levers 1–2.

## What Claude does when invoked

1. **Parse input.** Directory + `--batch`: enumerate `.txt`/`.tex`/`.md` recursively. File:
   read it. Inline text: use directly. Auto-detect `--format` from extension if unset
   (`.tex`→latex, `.md`→markdown, `.docx`→docx, else plain).
2. **Rewrite** each document by applying Lever 1, then Lever 2, then the final style cleanup,
   under the hard constraints above.
3. **Output.** For text formats, with `--out`: write there (batch mirrors the input tree,
   appending `_humanized` before the extension); with `--diff`: print a compact per-sentence
   diff; otherwise print to the terminal. For `docx`: write the edited copy next to the original
   as `name_humanized.docx` (see constraint 7). Return only the rewritten text/markup — no
   preamble or commentary.
4. **Summary:**

   ```
   Documents processed : <N>
   Format detected     : <plain|latex|markdown|docx>
   Output written to   : <path or "terminal">
   Levers applied      : restructured <N> paragraphs (de-listed / thinned enumerations); grammar slips ~1/<N> sentences; style cleanup (no em-dash/semicolon/cliché AI words)
   ```

## Options

- `--out=<path>` — write output to a file/dir instead of the terminal (text formats).
- `--format=plain|latex|markdown|docx` — what markup to preserve (default: auto-detect).
- `--batch` — process every `.txt`/`.tex`/`.md` under a directory; mirror under `--out`.
- `--diff` — show a per-sentence diff after each document (text formats).

## Examples

```
/humanize-text path/to/proposal.tex --format=latex --out=path/to/proposal_humanized.tex
/humanize-text "path/to/Draft.docx"          # writes Draft_humanized.docx alongside it
/humanize-text path/to/corpus/ --batch --out=path/to/humanized/
```

## If it still scores too high (calibration fallback)

Apply the two levers first and check the result. Only if the document still scores above
your target do you need to calibrate the dose — and even then, escalate gently: restructure the
still-flagged sections harder (thin their enumerations) and raise the grammatical density there,
before touching anything that passed.

When you do need to find the right dose, the detector is a black box and cannot be queried
programmatically, so calibrate with a cheap rotated test:

- Apply different doses to different sections of one file — the detector scores per segment,
  so a single submission tests several at once.
- Use two files that rotate the doses across sections, so you can tell "the dose worked"
  apart from "that section was just easier."
- Read the **per-segment highlights**, not only the headline percentage.
- Many detectors suppress the score and highlights below a threshold (e.g. 20%); a
  fully-passing document then gives no per-segment signal, so keep a known-flagging control
  section while you still need resolution.
- Settle on the lightest per-section dose that clears each segment, then stop.

## Scope / honesty

This is detection-robustness research. The structural lever has no quality cost; the
grammatical lever does. A low detector score is not the same as a truthful, reviewer-ready
document — for anything real, have a human read the output to confirm the intentional slips
did not land where precision matters and that any AI-use disclosure stays consistent. No
external APIs are called; all rewriting is in-context.
