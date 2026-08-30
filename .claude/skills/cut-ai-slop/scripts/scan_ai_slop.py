#!/usr/bin/env python3
"""
scan_ai_slop.py -- Fast regex pre-scanner for AI-slop writing patterns.

This flags CANDIDATE spans for a model to judge against references/ai_slop_patterns.md.
It does not decide anything. Regex cannot tell a statistical "significant" from a puffery
one, so context-dependent hits are marked "verify". The model makes the final call.

Design mirrors detect_prompt_injection.py in review-papers: a deterministic scan produces
candidates, the model applies judgment.

Usage:
    python3 scan_ai_slop.py --file PATH [--paper] [--json]
    python3 scan_ai_slop.py --text "some inline text" [--paper] [--json]
    cat file.md | python3 scan_ai_slop.py [--paper] [--json]

Stdlib only. Exit code is 0 always (candidates are advisory, not errors).
"""

import argparse
import json
import re
import sys
from typing import List, Tuple

# Each pattern: (category, compiled regex, scope, severity, note)
#   scope: "both" | "paper" | "general"
#   severity: "P0" | "P1" | "P2" | "verify"
# In --paper mode we apply scope in {both, paper}. Otherwise {both, general}.

_RAW: List[Tuple[str, str, str, str, str]] = [
    # Formatting
    ("em_dash", r"\u2014|---|(?<=\w) -- (?=\w)", "both", "P1",
     "em dash as connector (LaTeX ---); split into sentences or use a comma"),
    ("en_dash_connector", r"(?<=[A-Za-z])\s?\u2013\s?(?=[A-Za-z])|(?<=[A-Za-z])--(?=[A-Za-z])", "both", "P1",
     "en dash joining words as a connector (LaTeX -- between letters); use a comma (numeric ranges like 1--4 are fine)"),
    ("semicolon", r";(?=\s)", "both", "P2",
     "semicolon; if it joins two independent clauses split into sentences (list-separator semicolons are fine)"),
    ("list_label_period", r"^\s*[-*]\s+\*\*[^*]+\.\*\*", "both", "P2",
     "list-label period; a person writes '**Label:** gloss'"),

    # Section 2A words (replace even in papers)
    ("word_2A", r"\bdelv(?:e|es|ed|ing)\b", "both", "P1", "replace: examine, study"),
    ("word_2A", r"\bleverag(?:e|es|ed|ing)\b", "both", "P1", "replace: use, apply"),
    ("word_2A", r"\bunderscor(?:e|es|ed|ing)\b", "both", "P1", "replace: show, highlight"),
    ("word_2A", r"\bshowcas(?:e|es|ed|ing)\b", "both", "P1", "replace: show, demonstrate"),
    ("word_2A", r"\bcutting-edge\b", "both", "P1", "replace: latest, recent"),
    ("word_2A", r"\bdeep dive\b|\bdiv(?:e|es|ed|ing) into\b", "both", "P1", "replace: examine"),
    ("word_2A", r"\bunpack(?:s|ed|ing)?\b", "both", "P1", "replace: explain, break down"),
    ("word_2A", r"\btapestry\b", "both", "P1", "metaphor slop; rewrite plainly"),
    ("word_2A", r"\brealm\b", "both", "P1", "metaphor; replace: area, field"),
    ("word_2A", r"\blandscape\b", "both", "P1", "metaphor; replace: field, setting (skip if literal)"),
    ("word_2A", r"\bbeacon\b", "both", "P1", "metaphor slop; rewrite plainly"),
    ("word_2A", r"\bembark(?:s|ed|ing)?\b", "both", "P1", "replace: start, begin"),
    ("word_2A", r"\btestament to\b", "both", "P1", "replace: shows, is evidence of"),
    ("word_2A", r"\bat its core\b", "both", "P1", "cut; state the thing"),
    ("word_2A", r"\bever-evolving\b|\brapidly evolving\b", "both", "P1", "replace: changing (or cut)"),
    ("word_2A", r"\bholistic(?:ally)?\b", "both", "P1", "replace: complete, whole"),
    ("word_2A", r"\bsynerg(?:y|ies|istic)\b", "both", "P1", "describe the combined effect"),
    ("word_2A", r"\bmeticulous(?:ly)?\b", "both", "P1", "replace: careful, precise"),
    ("word_2A", r"\bseamless(?:ly)?\b", "both", "P1", "replace: smooth, without extra steps"),
    ("word_2A", r"\blearnings\b", "both", "P1", "replace: findings, lessons"),
    ("word_2A", r"\bbest practices\b", "both", "P1", "name them"),
    ("word_2A", r"\bplethora\b|\bmyriad\b", "both", "P1", "replace: many (or give a number)"),
    ("word_2A", r"\bgame-chang(?:er|ing)\b", "both", "P1", "state what specifically changed"),

    # Section 2B words (context-dependent; keep the technical sense)
    ("word_2B", r"\bsignificant(?:ly)?\b", "paper", "verify",
     "keep if statistical (p-value/test); else give the number"),
    ("word_2B", r"\brobust(?:ness)?\b", "paper", "verify",
     "keep if a real property/study; cut if vague compliment"),
    ("word_2B", r"\bcomprehensive\b", "paper", "verify", "keep if truly exhaustive; else cut"),
    ("word_2B", r"\b(?:novel|innovative)\b", "paper", "verify", "claim once with the delta; do not repeat"),
    ("word_2B", r"\bnuanced\b", "paper", "verify", "name the actual nuance or cut"),
    ("word_2B", r"\b(?:crucial|pivotal|paramount|vital)\b", "paper", "verify",
     "usually importance puffery; prefer 'important' or state why"),

    # Section 2C cluster words (flagged only when 2+ in a paragraph; see cluster logic)
    ("cluster", r"\bfoster(?:s|ed|ing)?\b", "both", "P2", "cluster word"),
    ("cluster", r"\bfacilitat(?:e|es|ed|ing)\b", "both", "P2", "cluster word"),
    ("cluster", r"\bstreamlin(?:e|es|ed|ing)\b", "both", "P2", "cluster word"),
    ("cluster", r"\bharness(?:es|ed|ing)?\b", "both", "P2", "cluster word"),
    ("cluster", r"\belevat(?:e|es|ed|ing)\b", "both", "P2", "cluster word"),
    ("cluster", r"\bempower(?:s|ed|ing)?\b", "both", "P2", "cluster word"),
    ("cluster", r"\bunderpin(?:s|ned|ning)?\b", "both", "P2", "cluster word"),
    ("cluster", r"\bencompass(?:es|ed|ing)?\b", "both", "P2", "cluster word"),

    # Phrase and sentence patterns
    ("formulaic_opener", r"\bIn recent years\b|\bWith the advent of\b|\bIn the rapidly evolving\b"
     r"|\b(?:has|have|is|are) attracted (?:increasing|growing|significant) attention\b|\bIn today's\b"
     r"|\bIn an era (?:of|where)\b", "both", "P1", "formulaic opener; lead with the contribution"),
    ("importance_inflation",
     r"\bplays? an? (?:crucial|pivotal|key|vital|central|significant|important) role\b"
     r"|\bis of paramount importance\b|\bstands? as a testament\b"
     r"|\bmark(?:s|ed)? an? (?:significant|major|pivotal|important) "
     r"(?:milestone|advance|advancement|breakthrough|step)\b",
     "both", "P0", "importance inflation; state the fact, let the reader judge"),
    ("superficial_ing",
     r",\s+(?:highlighting|underscoring|demonstrating|showcasing|reflecting|emphasizing"
     r"|illustrating|revealing|signifying)\b",
     "both", "P0", "superficial -ing analysis; cut or give the concrete consequence"),
    ("binary_contrast",
     r"\bnot (?:just|merely|only)\b[^.]{0,80}\bbut\b|\bit['\u2019]s not\b[^.]{0,80},\s*it['\u2019]s\b",
     "both", "P1", "binary contrast; state the positive claim directly"),
    ("filler_opener",
     r"\bit is worth noting that\b|\bit is important to note that\b|\bit should be noted that\b"
     r"|(?:^|\.\s+)(?:Notably|Importantly|Interestingly),",
     "both", "P1", "filler opener; just state the fact"),
    ("transition_stack",
     r"(?:^|\.\s+)(?:Moreover|Furthermore|Additionally|Consequently|In addition),",
     "both", "P2", "transition word; fine once, a stack is a tell"),
    ("copula_avoid", r"\bserves as\b|\bact(?:s|ed)? as\b|\brepresents? an?\b|\bconstitutes? an?\b",
     "paper", "P2", "copula avoidance; prefer 'is' or 'has' if clearer"),
    ("hollow_intensifier",
     r"\b(?:truly|remarkably|genuinely|incredibly|extremely)\s+\w+",
     "both", "P2", "hollow intensifier; cut or give the number"),
    ("vague_attribution",
     r"\bstudies show\b|\bprior work has shown\b|\bit is widely (?:believed|accepted|known)\b"
     r"|\bresearchers agree\b|\bit has been shown that\b",
     "paper", "P1", "cite the specific work or cut; never invent a citation"),
    ("overclaim",
     r"\bunprecedented\b|\bstate-of-the-art\b|\bwe are the first\b",
     "both", "P0", "overclaiming; state the result and the standard of evidence"),
    ("generic_conclusion",
     r"(?:^|\.\s+)(?:In conclusion|To summarize|In summary|Overall|Ultimately|All in all)\b",
     "both", "P2", "generic conclusion; end on the concrete point or implication"),
    ("aphorism",
     r"\bis the (?:cornerstone|backbone|bedrock|heart|foundation|bridge) of\b",
     "both", "P2", "slot-fill profundity; replace with the concrete claim"),
    ("colon_reveal",
     r"(?:^|\.\s+)(?:The|Our|One|Here['\u2019]s) [A-Za-z][A-Za-z ]{2,40}:\s+[a-z]",
     "both", "P2", "possible colon reveal; rewrite as a plain sentence (low confidence)"),

    # General-writing only (skipped in --paper mode)
    ("chatbot_artifact",
     r"\bI hope this helps\b|\bGreat question\b|\bCertainly!|\bAbsolutely!|\bFeel free to\b",
     "general", "P0", "chatbot artifact; remove"),
    ("lets_opener", r"(?:^|\.\s+)Let['\u2019]s (?:dive|explore|take a look|break)",
     "general", "P1", "'let's' opener; start with the point"),
    ("hashtag_stuffing", r"#\w+(?:\s+#\w+){5,}", "general", "P0", "hashtag stuffing; keep 2-3 max"),
]

PATTERNS = [(cat, re.compile(rx, re.IGNORECASE | re.MULTILINE), scope, sev, note)
            for (cat, rx, scope, sev, note) in _RAW]

# ---------------------------------------------------------------------------
# Masking: blank out code, math, citations, and URLs so we never flag inside them.
# ---------------------------------------------------------------------------

_MASK_PATTERNS = [
    re.compile(r"`[^`]*`"),                      # inline code
    re.compile(r"\$\$.+?\$\$", re.DOTALL),        # display math
    re.compile(r"(?<!\$)\$[^$]+\$"),              # inline math
    re.compile(r"\\(?:cite|ref|label|eqref|citep|citet)\{[^}]*\}"),  # latex refs
    re.compile(r"https?://\S+"),                  # urls
]


def _mask(text: str) -> str:
    """Replace protected spans with same-length spaces so column offsets stay aligned."""
    def blank(m: re.Match) -> str:
        return " " * (m.end() - m.start())
    for pat in _MASK_PATTERNS:
        text = pat.sub(blank, text)
    return text


def scan(text: str, paper: bool, max_words: int = 20) -> List[dict]:
    lines = text.split("\n")

    # Precompute paragraph index per line (paragraphs split on blank lines).
    para_of_line = []
    p = 0
    prev_blank = True
    for ln in lines:
        if ln.strip() == "":
            prev_blank = True
            para_of_line.append(-1)
        else:
            if prev_blank:
                p += 1
            prev_blank = False
            para_of_line.append(p)

    # Track fenced code blocks (``` ... ```) to skip them entirely.
    in_fence = False
    fence_re = re.compile(r"^\s*```")
    # In paper mode, stop auditing at the References/Bibliography heading (and everything
    # after it, usually appendices). Reference lists and reproduced material are not the
    # author's expository prose and should not be flagged.
    stop_re = re.compile(r"^\s*#*\s*(?:references|bibliography)\b", re.IGNORECASE)

    findings: List[dict] = []
    cluster_hits: List[dict] = []  # collected, filtered by paragraph count at the end
    scope_lines = []  # (line_index, masked_text) for in-scope lines (sentence-length pass)

    for i, raw_line in enumerate(lines):
        if fence_re.match(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if paper and stop_re.match(raw_line):
            break
        masked = _mask(raw_line)
        scope_lines.append((i, masked))
        for cat, rx, scope, sev, note in PATTERNS:
            if paper and scope == "general":
                continue
            if (not paper) and scope == "paper":
                continue
            for m in rx.finditer(masked):
                # Map back to the real matched text from the unmasked line.
                snippet = raw_line[m.start():m.end()].strip()
                if not snippet:
                    continue
                rec = {
                    "line": i + 1,
                    "col": m.start() + 1,
                    "category": cat,
                    "severity": sev,
                    "match": snippet[:120],
                    "note": note,
                    "paragraph": para_of_line[i],
                }
                if cat == "cluster":
                    cluster_hits.append(rec)
                else:
                    findings.append(rec)

    # Cluster words: keep only those in paragraphs with 2+ cluster hits.
    counts: dict = {}
    for rec in cluster_hits:
        counts[rec["paragraph"]] = counts.get(rec["paragraph"], 0) + 1
    for rec in cluster_hits:
        if counts.get(rec["paragraph"], 0) >= 2:
            findings.append(rec)

    # Long-sentence pass: flag any sentence over the word cap (a hard house rule).
    para, start = [], None

    def flush(para, start):
        if not para or start is None:
            return
        for s in re.split(r"(?<=[.!?])\s+", " ".join(para)):
            n = len([w for w in s.split() if re.search(r"[A-Za-z0-9]", w)])
            if n > max_words:
                findings.append({"line": start + 1, "col": 1, "category": "long_sentence",
                                 "severity": "P2", "paragraph": -1,
                                 "match": (s[:70] + ("..." if len(s) > 70 else "")).strip(),
                                 "note": f"sentence is {n} words; consider splitting where a "
                                         f"natural boundary reads better (target under {max_words})"})
    for idx, txt in scope_lines:
        if txt.strip() == "":
            flush(para, start)
            para, start = [], None
        else:
            if start is None:
                start = idx
            para.append(txt)
    flush(para, start)

    findings.sort(key=lambda r: (r["line"], r["col"]))
    return findings


def main() -> None:
    ap = argparse.ArgumentParser(description="Regex pre-scanner for AI-slop patterns.")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--file", metavar="PATH", help="File to scan")
    src.add_argument("--text", metavar="STR", help="Inline text to scan")
    ap.add_argument("--paper", action="store_true",
                    help="Apply paper-relevant patterns only (skip general-writing tells)")
    ap.add_argument("--json", action="store_true", help="Emit JSON")
    ap.add_argument("--max-sentence-words", type=int, default=20,
                    help="Flag sentences longer than this many words (default 20)")
    args = ap.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    elif args.text is not None:
        text = args.text
    else:
        text = sys.stdin.read()

    findings = scan(text, paper=args.paper, max_words=args.max_sentence_words)

    if args.json:
        print(json.dumps({"paper_mode": args.paper,
                          "count": len(findings),
                          "findings": findings}, indent=2))
        return

    if not findings:
        print("No AI-slop candidates flagged. (Regex only; a human/model still judges.)")
        return

    by_sev: dict = {}
    for r in findings:
        by_sev.setdefault(r["severity"], 0)
        by_sev[r["severity"]] += 1
    order = {"P0": 0, "P1": 1, "P2": 2, "verify": 3}
    summary = ", ".join(f"{k}: {by_sev[k]}" for k in sorted(by_sev, key=lambda x: order.get(x, 9)))
    print(f"{len(findings)} candidate span(s) [{summary}] "
          f"({'paper mode' if args.paper else 'general mode'}). These are candidates, not verdicts.\n")
    for r in findings:
        print(f"  L{r['line']}:{r['col']} [{r['severity']}/{r['category']}] "
              f"\"{r['match']}\" -- {r['note']}")


if __name__ == "__main__":
    main()
