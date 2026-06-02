# Reference Verification Workflow

Template variables: `{PDF_PATH}`, `{OUT_DIR}`, `{COMPILE_SCRIPT}`

---

You are verifying the references in a research paper to detect hallucinated, incomplete, or mismatched citations.

**Paper:** `{PDF_PATH}`
**Output directory:** `{OUT_DIR}`

## Style Rules

Apply these to everything you write:
- Do not use em-dashes (--) or en-dashes (-) anywhere.
- Do not use semicolons (;) as connectors between clauses.
- Do not use colons (:) to introduce a continuation of a sentence.
- Write in plain, direct sentences. Use a period and start a new sentence instead.
- Use Markdown for formatting.

## Tool Restrictions

Use `Read` to read the paper PDF. Use `WebSearch` and `WebFetch` to verify each reference. Use `Write` to write the output report. Use `Bash` only for the final compile step. Do NOT use Agent tools. Do not spawn subagents.

---

## Phase 1 -- Extract References

1. Read the full paper at `{PDF_PATH}`.
2. Locate the References or Bibliography section. This is typically near the end of the paper, before any appendices.
3. Extract EVERY reference entry as structured data. For each reference, record:
   - `ref_number`: The reference number or key as it appears in the paper (e.g., [1], [23], [Smith2020])
   - `authors`: List of author names as written
   - `title`: The paper/book/thesis title
   - `venue`: Conference name, journal name, or publication venue
   - `year`: Publication year
   - `identifiers`: Any DOI, arXiv ID, URL, or ISBN present
   - `raw_text`: The full raw reference text as it appears in the paper

4. IMPORTANT: Only extract entries from the actual References/Bibliography section. Do NOT extract:
   - Appendix headings or section titles
   - Table contents or captions
   - Code snippets or pseudocode
   - Footnotes that are not bibliographic references
   - URLs that appear inline in the paper body

5. After extraction, print: `Extracted N references. Beginning verification.`

## Phase 2 -- Check Completeness

Before doing any web searches, check each reference for completeness. A valid reference MUST have all three of:
1. At least one author name
2. A title
3. A venue or publication context (journal, conference, workshop, arXiv, thesis type, book publisher, or technical report series)

Mark any reference missing one or more of these as **INCOMPLETE**. Note which fields are missing.

Very old or classic references (pre-1950) that have author + title but use informal venue descriptions are acceptable and should not be flagged.

After this phase, print: `Completeness check done. N references complete, M incomplete.`

## Phase 3 -- Verify via Web Search

For each reference that is NOT incomplete, verify it exists through web search.

### Search strategy

1. Construct a search query using the title in quotes plus the first author's last name.
   - Example: `"Attention Is All You Need" Vaswani`
   - If the title contains special characters, remove them from the quoted string.
   - If the title is very long (>15 words), use the most distinctive portion.

2. Perform a web search using `WebSearch`.

3. Evaluate the search results:

   - **VERIFIED**: A search result's title is an exact or near-exact match to the reference title (allowing minor punctuation or capitalization differences), AND the authors in the result overlap with the reference (at least the first author matches).

   - **DETAIL MISMATCH**: The title matches a search result, BUT one of the following is true:
     - The venue or year in the paper differs from what is found online
     - The author list is substantially different (not just ordering or abbreviation differences)
     Record what the mismatch is.

   - **NOT FOUND (first attempt)**: No search result's title matches. Before finalizing, do a second search with a different query:
     - Try just the title without quotes, or
     - Try the first author's last name plus 3-4 key words from the title
     If the second search also fails, classify as **NOT FOUND**.

4. If a reference includes an arXiv ID (e.g., arXiv:2301.12345), search for that ID directly. An arXiv match is a strong verification signal.

5. If a reference includes a DOI, search for that DOI directly.

6. Process references sequentially. After each reference, print a one-line status:
   `[N/TOTAL] STATUS -- title (first 60 chars)`

After all references are checked, print: `Verification done. Verified: X, Not found: Y, Detail mismatch: Z`

## Phase 4 -- Write Report

Write the full report to `{OUT_DIR}/hallucination_check.md` using the following structure:

```
# Hallucination Check

## Summary

- **Paper:** {filename of the PDF}
- **Total references extracted:** N
- **Verified:** X
- **Not found (potential hallucinations):** Y
- **Detail mismatch:** Z
- **Incomplete:** W

{If Y == 0 and Z == 0 and W == 0, write: "All references were verified successfully. No issues detected."}

{If Y > 0, write: "**Y reference(s) could not be found** via web search. These may be hallucinated citations, very recent preprints, or papers from non-indexed venues."}

{If Z > 0, write: "**Z reference(s) had detail mismatches.** The paper exists but some details (venue, year, or authors) differ from the online record."}

{If W > 0, write: "**W reference(s) are incomplete.** They are missing required fields (authors, title, or venue)."}

## Detailed Results

| # | Ref | Status | Title | Authors (first) | Venue | Year |
|---|-----|--------|-------|-----------------|-------|------|
| 1 | [1] | VERIFIED | Attention Is All You Need | Vaswani et al. | NeurIPS 2017 | 2017 |
| 2 | [2] | NOT FOUND | Some Fabricated Paper Title | Unknown et al. | - | 2023 |
...

## Flagged References

{For each NOT FOUND reference:}

### NOT FOUND: [ref_number] title

**Raw citation:** {the full raw text of the reference as it appears in the paper}
**Authors listed:** {authors from the reference}
**Search queries tried:** {what was searched}
**Search outcome:** No matching results found.

{For each DETAIL MISMATCH reference:}

### DETAIL MISMATCH: [ref_number] title

**Raw citation:** {the full raw text of the reference as it appears in the paper}
**Paper claims:** {venue/year/authors as listed in the paper}
**Found online:** {what was actually found, with source URL if available}
**Discrepancy:** {what differs}

## Incomplete References

{For each INCOMPLETE reference:}

- **[ref_number]** {raw_text (first 200 chars)} -- Missing: {list of missing fields}

## Methodology Note

References were verified via web search (Google). Verification checks whether a paper with a matching title and overlapping authors can be found online. Limitations: very recent papers (last few weeks), papers from non-indexed or regional venues, and non-English papers may not appear in search results even if they exist. A "NOT FOUND" result is a flag for manual review, not definitive proof of hallucination.
```

---

## Phase 5 -- Compile and Move PDF

Run this Bash command to convert the report to PDF and move the source paper into the output directory:

```bash
python3 "{COMPILE_SCRIPT}" \
    --out-dir "{OUT_DIR}" \
    --pdf-path "{PDF_PATH}"
```

This will:
- Convert `hallucination_check.md` to `hallucination_check.pdf` (using Chrome headless or weasyprint)
- Move the source PDF into `{OUT_DIR}/`

---

## Done

Print exactly one line: `Hallucination check complete: {OUT_DIR}/hallucination_check.md`
Print a second line with counts: `Verified: X, Not found: Y, Detail mismatch: Z, Incomplete: W (Total: N)`
