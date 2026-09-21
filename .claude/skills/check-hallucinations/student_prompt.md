# Reference Hallucination Check — Standalone Prompt

Platform-independent version of this skill's verification methodology. Paste
this into any chat tool that can search the web and read a PDF (ChatGPT,
Gemini, claude.ai, etc.). It does not depend on Claude Code or this repo.

---

You are verifying the references in a research paper. Your goal is not just to
confirm that each cited work exists. It is to confirm that the cited metadata
(title, authors, venue, year, identifier) matches the real published record,
and to flag any reference whose metadata is wrong, truncated, or fabricated.

I will give you a research paper (as a PDF, pasted text, or its reference
list). Use web search and page-reading to verify each reference against its
real, canonical source (the arXiv abstract page, the ACL Anthology page, the
DOI or publisher page, or a library catalog for books). A search-result
snippet is not enough. Open the actual page and read its real title and full
author list before you compare anything.

STYLE RULES for your report
- No em-dashes or en-dashes anywhere.
- No semicolons as connectors between clauses.
- No colons to introduce a continuation of a sentence.
- Plain, direct sentences. Use a period and start a new sentence instead.
- Use Markdown for formatting.

PHASE 1: Extract references
1. Read the full paper.
2. Locate the References or Bibliography section.
3. Extract every entry as: ref_key, authors (as written, including any "et
   al." or "and others" placeholder), title, venue, year, identifiers
   (DOI/arXiv ID/URL/ISBN), and the raw citation text.
4. Note every in-text citation key used in the body, for a cross-check later.
5. Only extract from the actual References/Bibliography section, not
   appendix headings, tables, or inline URLs in the body.

PHASE 2: Completeness and placeholder detection
A valid reference needs at least one author, a title, and a venue. Flag
anything missing one of these as INCOMPLETE (exception: informal, pre-1950
references). Record any author-list placeholder ("et al.", "and others",
"and N others", a trailing comma implying omitted authors) and how many
authors are explicitly named.

PHASE 3: Verify existence and metadata
For each non-incomplete reference:
1. Search the title in quotes plus the first author's last name.
2. If an arXiv ID or DOI is present, open it directly (arXiv abstract page:
   https://arxiv.org/abs/<id>) and confirm it is actually this work, don't
   just trust the identifier.
3. Open the best candidate's canonical page (arXiv abstract page, ACL
   Anthology, publisher page, DOI record, dblp, or a library catalog for
   books) and read the real title and full author list.
4. If the reference cites only an arXiv preprint, check whether it has since
   been formally published (the arXiv page's "Journal reference" or
   "Comments" field, or one more search for the title plus "proceedings" /
   "ACL Anthology" / "dblp"). If nothing turns up, treat the arXiv version as
   the only known publication.
5. If two searches and an identifier lookup all fail, classify as NOT FOUND.

Compare these fields and record every discrepancy:
- Title: a content-word mismatch (not just casing or hyphenation) is a title
  mismatch.
- Authors: any named author not on the real paper, or different lead
  authors, is an author mismatch.
- Truncation: a placeholder that materially understates the real author
  count (e.g. "and 1 others" after 6 named authors, but the real paper has
  51) is a truncation error.
- Venue: a wrong conference or workshop, or a superseded arXiv preprint that
  has since been formally published, is a venue mismatch. Record the real
  venue so the citation can be corrected.
- Year: a mismatched publication year is a year mismatch (the arXiv year is
  fine for a genuine preprint).
- Identifier: an arXiv ID or DOI that does not resolve to this exact work is
  an identifier mismatch. Also flag, for manual review rather than an
  automatic fail, an arXiv ID whose encoded year and month is in the future.

Assign a status:
- VERIFIED: real record found, every field matches, no misleading
  truncation.
- MALFORMED: real record found, but at least one field is wrong. Name the
  failing fields, e.g. "MALFORMED (title, authors)".
- NOT FOUND: no real record found after a title search, an author-plus-
  keyword search, and an identifier lookup. This is a flag for manual
  review, not proof of fabrication.
- UNVERIFIABLE: plausibly real but cannot be confirmed online (an
  anonymized submission, an obscure regional book, a paywalled record).
  State why.

Assign a confidence:
- High: canonical record opened, fields compared directly.
- Medium: strong search evidence but the canonical page could not be fully
  opened.
- Low: weak or conflicting evidence, explain why.

PHASE 4: Consistency checks
1. Flag any two entries referring to the same underlying work that disagree
   on year, venue, or edition.
2. Cross-check in-text citation keys against the bibliography. List any
   in-text citation with no bibliography entry, and any bibliography entry
   never cited in the body. Both are advisory, not errors on their own.

PHASE 5 (optional, best-effort): Claim consistency
Pick up to five in-text citations that make a specific empirical or
definitional claim. Open each cited work's abstract and judge whether the
citing sentence is plausibly supported. Record SUPPORTED, UNSUPPORTED, or
UNCHECKED with a one-line reason. Skip this phase if time is short.

PHASE 6: Write the report, using this structure

# Hallucination Check

## Summary
- Paper: {name}
- Total references extracted: N
- Verified: V
- Malformed (real work, wrong metadata): M
- Not found (possible fabrication): F
- Unverifiable: U
- Incomplete: W

## Detailed Results
A table with columns: # | Ref | Status | Confidence | Cited title |
Issue(s) | Canonical source (URL). Every row, including VERIFIED ones, must
carry a canonical source URL where one exists, so each verdict is
auditable.

## Malformed References
For each: raw citation, a field-by-field cited-vs-real comparison (title,
authors plus real author count, venue, year, identifier), the canonical
source URL, and, if it is a superseded-preprint case, the correct citation
to use instead.

## Not Found References
For each: raw citation, authors listed, search queries tried, outcome.

## Unverifiable References
For each: raw citation and the reason it cannot be confirmed.

## Incomplete References
For each: ref_key, raw text (first 200 characters), missing fields.

## Consistency Issues
Duplicate-work clusters, orphan in-text cites, uncited bibliography
entries. Write "None found" if there are none.

## Claim Consistency
If Phase 5 was run, list the sampled claims and their verdicts. Otherwise
write "Not performed in this pass."

## Methodology Note
One paragraph explaining VERIFIED vs MALFORMED vs NOT FOUND vs
UNVERIFIABLE, noting that NOT FOUND is a flag for manual review rather than
proof of fabrication, and that some genuine works (anonymized submissions,
obscure books, paywalled records) may be UNVERIFIABLE.

---
Now check the following paper: [paste the paper's text, its reference list,
or attach the PDF here]
