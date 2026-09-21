#!/usr/bin/env python3
"""
extract_ai_involvement.py — Extract each paper's CAISc AI Involvement Checklist.

The CAISc template has a Research Stage Assessment with four stages
(hypothesis development, experimental design and implementation, analysis and
interpretation, writing). Each stage carries:

    Answer: [A|B|C|D]          Iteration Effort: [Low|Medium|High|NA|Unclear]

with the scale:
    [A] Human-generated              humans produced >=95%
    [B] Mostly human, assisted by AI humans produced >50%
    [C] Mostly AI, assisted by human AI produced >50%
    [D] AI-generated                 AI produced >95%

Items 5-6 are free text: which AI systems were used, and their observed
limitations.

This script parses the four stage answers, maps them to a 0-3 scale, adds the
declared iteration effort, records which AI systems were named, and flags
papers whose declared letters contradict their own prose (some authors invert
the scale). Everything here is a *self-report* extraction, not a verification.

Requires paper.txt next to each paper.pdf (produce with `pdftotext -layout`).

Usage:
    python extract_ai_involvement.py --venue-dir VENUE_DIR [--track "Open-Ended"]
"""

import argparse
import csv
import json
import re
import statistics
from pathlib import Path

LETTER_SCORE = {"A": 0.0, "B": 1.0, "C": 2.0, "D": 3.0}
EFFORT_SCORE = {"low": 0.33, "medium": 0.66, "high": 1.0, "na": 0.0, "unclear": 0.0}

STAGE_NAMES = ["hypothesis", "experiment", "analysis", "writing"]

# Named AI systems worth reporting when they appear in the checklist section.
_SYSTEMS = [
    ("Claude Opus", r"claude[\s-]*opus[\s-]*[\d.]*"),
    ("Claude Sonnet", r"claude[\s-]*sonnet[\s-]*[\d.]*"),
    ("Claude (other)", r"\bclaude\b"),
    ("Claude Code", r"claude[\s-]*code"),
    ("GPT-5", r"\bgpt[\s-]*5[\w.-]*"),
    ("GPT-4 family", r"\bgpt[\s-]*4[\w.-]*"),
    ("o-series", r"\bo[34](?:-mini|-pro)?\b"),
    ("ChatGPT", r"\bchatgpt\b"),
    ("Gemini", r"\bgemini[\s-]*[\d.]*\w*"),
    ("DeepSeek", r"\bdeepseek[\w.-]*"),
    ("Llama", r"\bllama[\s-]*[\d.]*"),
    ("Qwen", r"\bqwen[\w.-]*"),
    ("Mistral", r"\bmistral\w*"),
    ("Grok", r"\bgrok[\w.-]*"),
    ("Codex", r"\bcodex\b"),
    ("Cursor", r"\bcursor\b"),
    ("Cline", r"\bcline\b"),
    ("Copilot", r"\bcopilot\b"),
    ("Aider", r"\baider\b"),
    ("Devin", r"\bdevin\b"),
]

_AI_AGENCY = re.compile(
    r"\b(ai|agent|agents|llm|model|claude|gpt|codex|gemini|cursor|cline|copilot)\b"
    r"[^.\n]{0,90}?\b(wrote|generated|designed|implemented|drafted|built|proposed|"
    r"conducted|ran|derived|discovered|authored|produced|executed|autonomously)\b",
    re.IGNORECASE,
)
_HUMAN_AGENCY = re.compile(
    r"\bhumans?\b[^.\n]{0,90}?\b(wrote|designed|implemented|drafted|built|proposed|"
    r"conducted|derived|specified|led|authored|decided|formulated|identified)\b",
    re.IGNORECASE,
)
_AUTONOMOUS = re.compile(
    r"\b(fully|entirely|completely|end[\s-]to[\s-]end)\s+(autonomous|ai[\s-]generated|"
    r"ai[\s-]driven|automated)\b|\bwithout human (intervention|involvement|input|editing)\b"
    r"|\bno human (intervention|involvement|edits?|authors?)\b|\bzero human\b",
    re.IGNORECASE,
)

# Section boundaries.
_ANCHORS = [
    re.compile(r"Research\s+Stage\s+Assessment", re.IGNORECASE),
    re.compile(r"AI\s+Involvement\s+Checklist", re.IGNORECASE),
]
_END = re.compile(
    r"Reproducibility\s+and\s+Responsibility|Reproducibility\s+Checklist|"
    r"Responsibility\s+Checklist|NeurIPS\s+Paper\s+Checklist",
    re.IGNORECASE,
)

# Answer forms, most explicit first.
_ANSWER = re.compile(
    r"(?:Answer|Rating|Score|Involvement)\s*[:\-]?\s*\[?\s*([A-D])\s*\]?(?=[\s.,)(]|$)",
    re.IGNORECASE)
# Some authors replace the letters with a word scale in a table.
_WORD_SCALE = {"none": "A", "minor": "B", "substantial": "C", "primary": "D"}
_WORD_ANSWER = re.compile(r"\b(None|Minor|Substantial|Primary)\b")
_EFFORT = re.compile(
    r"Iteration\s*Effort\s*[:\-]?\s*\[?\s*(Low|Medium|High|NA|N/A|Unclear)\s*\]?"
    r"(?=[\s.,)(]|$)",
    re.IGNORECASE)
# Fallback: "3. Some stage name ... [C]" (used by papers that compress the template).
_NUMBERED = re.compile(
    r"^[ \t]*(\d{1,2})[.)]\s+(?!\[)(.{0,140}?)\[\s*([A-D])\s*\]",
    re.MULTILINE | re.DOTALL)
# Legend lines to ignore: "• [A] Human-generated: ..." and friends.
_LEGEND = re.compile(
    r"[•\-\*]?\s*\[\s*[A-D]\s*\]\s*(Human-generated|Mostly human|Mostly AI|AI-generated)",
    re.IGNORECASE)


def _strip_line_numbers(text: str) -> str:
    """pdftotext -layout keeps LaTeX line numbers in the left margin."""
    return re.sub(r"^\s*\d{1,4}\s{3,}", "  ", text, flags=re.MULTILINE)


def extract_section(text: str) -> str:
    """Return the AI Involvement Checklist body, without the legend boilerplate."""
    best = ""
    for anchor in _ANCHORS:
        for match in reversed(list(anchor.finditer(text))):
            chunk = text[match.end(): match.end() + 20000]
            end = _END.search(chunk)
            if end:
                chunk = chunk[: end.start()]
            if (_ANSWER.search(chunk) or _NUMBERED.search(chunk)
                    or len(_WORD_ANSWER.findall(chunk)) >= 4):
                if len(chunk) > len(best):
                    best = chunk
        if best:
            break
    return best


def _strip_legend(section: str) -> str:
    return "\n".join(
        line for line in section.splitlines() if not _LEGEND.search(line)
    )


def parse_answers(section: str) -> tuple:
    """Return (letters, efforts) for the four research stages."""
    body = _strip_legend(section)

    letters = [m.group(1).upper() for m in _ANSWER.finditer(body)]
    efforts = [m.group(1).lower().replace("n/a", "na") for m in _EFFORT.finditer(body)]

    if not letters:
        seen = {}
        for match in _NUMBERED.finditer(body):
            idx = int(match.group(1))
            label = match.group(2)
            if _LEGEND.search(label):
                continue
            if 1 <= idx <= 8 and idx not in seen:
                seen[idx] = match.group(3).upper()
        letters = [seen[k] for k in sorted(seen)]
        efforts = [
            m.group(1).lower()
            for m in re.finditer(r"\[\s*(Low|Medium|High|Unclear)\s*\]", body, re.IGNORECASE)
        ]

    if not letters:
        # Word-scale table: "Hypothesis ideation | Substantial | notes".
        # Skip the legend line that enumerates the whole word scale at once.
        table = "\n".join(
            line for line in body.splitlines()
            if len(set(w.lower() for w in _WORD_ANSWER.findall(line))) < 3
        )
        words = _WORD_ANSWER.findall(table)
        if len(words) >= 4:
            letters = [_WORD_SCALE[w.lower()] for w in words]

    return letters[:8], efforts[:8]


def find_systems(section: str) -> list:
    found = []
    for name, pattern in _SYSTEMS:
        if re.search(pattern, section, re.IGNORECASE):
            found.append(name)
    if "Claude (other)" in found and any(
            n in found for n in ("Claude Opus", "Claude Sonnet", "Claude Code")):
        found.remove("Claude (other)")
    return found


def analyze(section: str) -> dict:
    letters, efforts = parse_answers(section)
    scored = [LETTER_SCORE[c] for c in letters if c in LETTER_SCORE]
    effort_vals = [EFFORT_SCORE[e] for e in efforts if e in EFFORT_SCORE]

    mean_letter = statistics.mean(scored) if scored else None
    mean_effort = statistics.mean(effort_vals) if effort_vals else None

    ai_hits = len(_AI_AGENCY.findall(section))
    human_hits = len(_HUMAN_AGENCY.findall(section))

    # Composite: declared involvement dominates, iteration effort breaks ties.
    composite = ""
    if mean_letter is not None:
        composite = round(mean_letter + 0.5 * (mean_effort or 0.0), 3)

    inverted = False
    if mean_letter is not None and (ai_hits + human_hits) >= 4:
        ratio = ai_hits / (ai_hits + human_hits)
        if mean_letter <= 0.5 and ratio >= 0.8:
            inverted = True
        if mean_letter >= 2.5 and ratio <= 0.2:
            inverted = True

    stage_map = {}
    for i, letter in enumerate(letters[:4]):
        stage_map[STAGE_NAMES[i]] = letter

    return {
        "found_checklist": bool(section.strip()) and bool(letters),
        "num_answers": len(letters),
        "letters": "".join(letters),
        "stages": stage_map,
        "efforts": ",".join(efforts),
        "letter_counts": {c: letters.count(c) for c in ["A", "B", "C", "D"]},
        "mean_letter_score": round(mean_letter, 3) if mean_letter is not None else "",
        "mean_effort_score": round(mean_effort, 3) if mean_effort is not None else "",
        "composite_ai_score": composite,
        "high_effort_stages": efforts.count("high"),
        "ai_systems": find_systems(section),
        "ai_agency_mentions": ai_hits,
        "human_agency_mentions": human_hits,
        "claims_fully_autonomous": bool(_AUTONOMOUS.search(section)),
        "scale_inversion_suspected": inverted,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract CAISc AI Involvement Checklists.")
    parser.add_argument("--venue-dir", required=True)
    parser.add_argument("--track", default=None,
                        help="Only papers whose submission_track contains this substring")
    parser.add_argument("--out-prefix", default="ai_involvement")
    args = parser.parse_args()

    venue_dir = Path(args.venue_dir).resolve()
    summary = json.loads((venue_dir / "venue_summary.json").read_text(encoding="utf-8"))

    papers = summary["papers"]
    if args.track:
        papers = [p for p in papers
                  if args.track.lower() in str(p.get("submission_track", "")).lower()]
        print(f"Track filter '{args.track}': {len(papers)} of {len(summary['papers'])} papers")

    rows = []
    for paper in papers:
        paper_dir = Path(paper["paper_dir"])
        record = {
            "number": paper["number"],
            "title": paper["title"],
            "track": paper.get("submission_track", ""),
            "type": paper.get("submission_type", ""),
            "dir": paper_dir.name,
        }
        txt_path = paper_dir / "paper.txt"
        if not txt_path.exists():
            record.update(analyze(""))
            rows.append(record)
            continue

        text = _strip_line_numbers(txt_path.read_text(encoding="utf-8", errors="ignore"))
        section = extract_section(text)
        record.update(analyze(section))
        (paper_dir / "ai_involvement_section.txt").write_text(section, encoding="utf-8")
        rows.append(record)

    rows.sort(
        key=lambda r: (
            r["composite_ai_score"] if r["composite_ai_score"] != "" else -1,
            r["ai_agency_mentions"],
        ),
        reverse=True,
    )

    out_json = venue_dir / f"{args.out_prefix}.json"
    out_json.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")

    out_csv = venue_dir / f"{args.out_prefix}.csv"
    fields = ["number", "title", "track", "type", "found_checklist", "letters",
              "efforts", "mean_letter_score", "mean_effort_score", "composite_ai_score",
              "high_effort_stages", "ai_systems", "ai_agency_mentions",
              "human_agency_mentions", "claims_fully_autonomous",
              "scale_inversion_suspected", "dir"]
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["ai_systems"] = "; ".join(row["ai_systems"])
            writer.writerow(flat)

    missing = [r["number"] for r in rows if not r["found_checklist"]]
    flagged = [r["number"] for r in rows if r["scale_inversion_suspected"]]
    print(f"Wrote {out_json}")
    print(f"Wrote {out_csv}")
    print(f"Parsed checklist for {len(rows) - len(missing)}/{len(rows)} papers")
    print(f"No parsable checklist: {missing}")
    print(f"Possible scale inversion: {flagged}")


if __name__ == "__main__":
    main()
