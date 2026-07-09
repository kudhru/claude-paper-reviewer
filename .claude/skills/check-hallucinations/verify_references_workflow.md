# Reference Verification Workflow

Template variables: `{PDF_PATH}`, `{OUT_DIR}`, `{REPORT_FILENAME}`, `{COMPILE_SCRIPT}`

---

You are verifying the references in a research paper. Your goal is not only to confirm that each cited work exists. It is to confirm that the cited metadata (title, authors, venue, year, identifier) matches the real published record, and to flag any reference whose metadata is wrong, truncated, or fabricated.

**Paper:** `{PDF_PATH}`
**Output directory:** `{OUT_DIR}`

## Style Rules

Apply these to everything you write:
- Do not use em-dashes or en-dashes anywhere.
- Do not use semicolons as connectors between clauses.
- Do not use colons to introduce a continuation of a sentence.
- Write in plain, direct sentences. Use a period and start a new sentence instead.
- Use Markdown for formatting.

## Tool Restrictions

Use `Read` to read the paper PDF. Use `WebSearch` to find candidate records and `WebFetch` to open the canonical record page and read its real title and full author list. Use `Write` to write the output report. Use `Bash` only for the final compile step. Do NOT use Agent tools. Do not spawn subagents.

Key principle. A web search result title in a snippet is not enough to VERIFY a reference. You must open the canonical record (the arXiv abstract page, the ACL Anthology page, the DOI or publisher page, or a library catalog for books) and compare fields against the citation. Existence is necessary but not sufficient. Metadata must match.

---

## Phase 1 -- Extract References

1. Read the full paper at `{PDF_PATH}`.
2. Locate the References or Bibliography section. This is typically near the end of the paper, before any appendices.
3. Extract EVERY reference entry as structured data. For each reference, record:
   - `ref_key`: The author-year key or number as it appears (e.g., Smith et al., 2020, or [23]).
   - `authors`: The author names exactly as written, including any placeholder such as "and others", "and N others", or "et al.".
   - `title`: The title exactly as written.
   - `venue`: Conference, journal, workshop, publisher, or series.
   - `year`: Publication year.
   - `identifiers`: Any DOI, arXiv ID, URL, or ISBN present.
   - `raw_text`: The full raw reference text.
4. Also record the set of in-text citation keys that appear in the body (author-year or numeric). You will use this in Phase 4 for a consistency cross-check.
5. Only extract entries from the actual References/Bibliography section. Do NOT extract appendix headings, table contents, code snippets, non-bibliographic footnotes, or inline URLs from the body.
6. After extraction, print: `Extracted N references. Beginning verification.`

## Phase 2 -- Completeness and Placeholder Detection

For each reference, check completeness. A valid reference MUST have all three of:
1. At least one author name (or a corporate or editorial author).
2. A title.
3. A venue or publication context.

Mark any reference missing one or more of these as **INCOMPLETE** and note the missing fields. Very old or classic references (pre-1950) that use informal venue descriptions are acceptable and should not be flagged as incomplete.

Placeholder and truncation detection. For each reference, detect any author-list placeholder: "and others", "and N others", "et al.", or a trailing comma that implies omitted authors. Record the number of explicitly named authors and the placeholder text. You will resolve the true author count in Phase 3 and decide whether the truncation is misleading.

After this phase, print: `Completeness check done. N complete, M incomplete, P entries carry an author placeholder.`

## Phase 3 -- Verify Existence and Metadata

For every reference that is not INCOMPLETE, do the following.

### Step 3.1 Find the canonical record
1. Search with the title in quotes plus the first author's last name using `WebSearch`.
2. If an arXiv ID or DOI is present, treat it as a lead but not as proof. Open it directly with `WebFetch` (for arXiv use the abstract page `https://arxiv.org/abs/<id>`; for a DOI use the resolver). Confirm the page you land on is actually the cited work.
3. Open the best candidate's canonical page with `WebFetch` (arXiv abstract page, ACL Anthology page, publisher page, DOI record, or dblp). Read the real title and the FULL author list from that page. For books, use a library catalog, the publisher page, or archive.org.
4. If two searches and an identifier lookup all fail to surface any matching work, classify the reference as **NOT FOUND** and move on.

### Step 3.2 Compare fields against the canonical record
Compare each field and record every discrepancy.

- **Title.** Normalize case and punctuation, then compare content words. A pure function-word or casing or hyphenation difference is acceptable. A different or invented subtitle, a changed distinctive term, or a reworded claim is a **title mismatch**. Record the cited title and the real title.
- **Authors.** Compare each explicitly named author to the real author list. If any named author is not on the real paper, or the lead authors differ, it is an **author mismatch**. Record which names are wrong and the real lead authors.
- **Truncation.** If the entry carries an author placeholder, compare the implied count to the real total. Flag a **truncation error** when the placeholder materially understates the real author count. For example, "and 1 others" after six named authors implies seven authors. If the real paper has 51, that hides 45 co-authors and is a truncation error. Record the real total.
- **Venue.** If the cited venue differs from the real one (for example a workshop cited as the main conference, or the wrong conference), it is a **venue mismatch**. A preprint cited as arXiv when a later peer-reviewed version exists is acceptable, note it but do not flag it.
- **Year.** If the cited year differs from the real publication year, it is a **year mismatch**. For a preprint, the arXiv year is acceptable.
- **Identifier.** If an arXiv ID or DOI is present, confirm it resolves to THIS work (matching real title and first author). If it resolves to a different paper, or does not resolve, it is an **identifier mismatch**. Also sanity-check plausibility: an arXiv ID encodes year and month as YYMM. If that month is in the future relative to today, flag it for manual review rather than auto-passing. A recent but genuine ID that resolves correctly is fine.

### Step 3.3 Assign a status
- **VERIFIED**: A real record was opened and the cited title, authors, venue, year, and any identifier all match. No misleading truncation.
- **MALFORMED**: A real record was found, but at least one field is wrong. List the failing field types explicitly, for example `MALFORMED (title, authors)` or `MALFORMED (truncation)`.
- **NOT FOUND**: No real record could be found after searching by title, by author plus keywords, and by identifier. Treat this as a possible fabrication and a flag for manual review.
- **UNVERIFIABLE**: The work may well be real but cannot be confirmed online. Examples are an anonymized concurrent submission, a regional book with no online catalog entry, or a paywalled record with no accessible metadata. State the reason.

### Step 3.4 Assign a confidence
Record a confidence for every reference.
- **High**: The canonical record was opened and fields were compared directly.
- **Medium**: Strong search evidence but the canonical page could not be fully opened, or a book confirmed only through a secondary catalog.
- **Low**: Weak or conflicting evidence. Explain.

### Step 3.5 Log progress
Process references sequentially. After each reference, print one line:
`[N/TOTAL] STATUS (confidence) -- ref_key -- issue summary`

After all references are checked, print: `Verification done. Verified: V, Malformed: M, Not found: F, Unverifiable: U`

## Phase 4 -- Intra-Bibliography Consistency

Run these checks across the whole reference list.

1. **Duplicate work with inconsistent metadata.** Detect two or more entries that refer to the same underlying work but disagree on year, venue, or edition. A classic case is the same book cited once with a correct year and once with an impossible or wrong year. Flag each such cluster.
2. **In-text versus bibliography cross-check.** Using the in-text citation keys from Phase 1, list any in-text citation that has no matching bibliography entry, and any bibliography entry that is never cited in the body. Report both lists. These are advisory, not errors on their own.

Print: `Consistency check done. Duplicates flagged: D. Orphan in-text cites: O. Uncited entries: E.`

## Phase 5 -- Claim Consistency (best-effort, optional)

This phase is optional and best-effort. If time and tool budget allow, pick up to five in-text citations that make a specific empirical or definitional claim (for example a benchmark size, a headline result, or a named method attributed to a work). For each, open the cited work's abstract with `WebFetch` and judge whether the citing sentence is plausibly supported. Record SUPPORTED, UNSUPPORTED, or UNCHECKED with a one-line reason. Do not spend more than a small fraction of the run on this phase, and never let it block the report.

Print: `Claim consistency: S supported, N unsupported, checked K of the sampled claims.`

## Phase 6 -- Write Report

Write the full report to `{OUT_DIR}/{REPORT_FILENAME}` using this structure.

```
# Hallucination Check

## Summary
- **Paper:** {filename of the PDF}
- **Total references extracted:** N
- **Verified:** V
- **Malformed (real work, wrong metadata):** M
- **Not found (possible fabrication):** F
- **Unverifiable:** U
- **Incomplete:** W

{If M == 0 and F == 0 and W == 0, write: "All references verified against their canonical records. No metadata issues detected."}
{If F > 0, write: "**F reference(s) could not be found** and may be fabricated. Manual review required."}
{If M > 0, write: "**M reference(s) are malformed.** The work exists but the cited title, authors, venue, year, or identifier does not match the real record."}
{If W > 0, write: "**W reference(s) are incomplete.**"}

## Detailed Results

| # | Ref | Status | Confidence | Cited title | Issue(s) | Canonical source |
|---|-----|--------|-----------|-------------|----------|------------------|
| 1 | Vaswani et al., 2017 | VERIFIED | High | Attention Is All You Need | none | https://arxiv.org/abs/1706.03762 |
...

Every row must carry a canonical source URL where one exists, including VERIFIED rows, so each verdict is auditable.

## Malformed References

{For each MALFORMED reference:}

### MALFORMED: [ref_key] -- {failing fields}

**Raw citation:** {raw text}
**Cited vs real, field by field:**
- Title cited: {...} | Title real: {...}
- Authors cited: {...} | Authors real: {...} | Real author count: {...}
- Venue cited: {...} | Venue real: {...}
- Year cited: {...} | Year real: {...}
- Identifier cited: {...} | Resolves to: {...}
**Canonical source:** {URL}

## Not Found References

{For each NOT FOUND reference: raw citation, authors listed, search queries tried, outcome.}

## Unverifiable References

{For each UNVERIFIABLE reference: raw citation and the reason it cannot be confirmed.}

## Incomplete References

{For each INCOMPLETE reference: - **[ref_key]** raw_text (first 200 chars) -- Missing: fields}

## Consistency Issues

{Duplicate-work clusters with inconsistent metadata. In-text cites with no bib entry. Bib entries never cited. If none, write "None found."}

## Claim Consistency

{If Phase 5 was run, list the sampled claims and their SUPPORTED / UNSUPPORTED / UNCHECKED verdicts. If skipped, write "Not performed in this pass."}

## Methodology Note

Each reference was checked against its canonical record (arXiv, ACL Anthology, DOI or publisher page, or a library catalog for books), not by title existence alone. VERIFIED means the cited title, authors, venue, year, and identifier all match the real record. MALFORMED means the work is real but at least one cited field is wrong, including author lists truncated by a placeholder that hides many co-authors. NOT FOUND is a flag for manual review, not definitive proof of fabrication. Limitations: anonymized submissions, some regional books, and paywalled records may be UNVERIFIABLE even when genuine.
```

## Phase 7 -- Compile and Move PDF

If the compile script value below is the literal word `SKIP`, do NOT run this phase. Skip straight to Done.

Otherwise run:

```bash
python3 "{COMPILE_SCRIPT}" \
    --out-dir "{OUT_DIR}" \
    --pdf-path "{PDF_PATH}"
```

---

## Done

Print exactly one line: `Hallucination check complete: {OUT_DIR}/{REPORT_FILENAME}`
Print a second line with counts: `Verified: V, Malformed: M, Not found: F, Unverifiable: U, Incomplete: W (Total: N)`
