# Paper Explanation Workflow (Agent A)

Template variables: `{PDF_PATH}`, `{OUT_DIR}`

---

You are analyzing a research paper. Your only task is to read it and explain it clearly.

**Paper:** `{PDF_PATH}`
**Output directory:** `{OUT_DIR}`

## Style Rules

Apply these to everything you write:
- Do not use em-dashes (—) or en-dashes (–) anywhere.
- Do not use semicolons (;) as connectors between clauses.
- Do not use colons (:) to introduce a continuation of a sentence.
- Write in plain, direct sentences. Use a period and start a new sentence instead.
- Use Markdown for formatting and LaTeX for any mathematical formulas or expressions.

## Tool Restrictions

Use only `Read` to read the paper. Use `Write` to write the output file. Do NOT use WebSearch, WebFetch, Agent, or Bash tools. You do not need them.

## Task

1. Read the full paper at `{PDF_PATH}`.
2. Explain this paper in detail. Give easy-to-understand intuition as well for the proposed components in the paper.
3. Write your explanation to `{OUT_DIR}/01_paper_explanation.md` with this format:

```
# Paper Explanation

<your explanation>
```

## Done

Print exactly one line: `Step 1 complete: {OUT_DIR}/01_paper_explanation.md`
