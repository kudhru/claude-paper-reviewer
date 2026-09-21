#!/usr/bin/env python3
"""
split_paper.py -- Split a paper into per-section files and a shared context pack, so the
section-wise de-slop rewrite (see paper_rewrite_workflow.md) can hand one section to each
agent while keeping them consistent.

It does NOT edit prose. It only splits, and it deliberately excludes the bibliography and
appendix from the rewritable set so those are never touched.

Modes:
  latex  -- split on \\section{...}; front matter (preamble, title, abstract) and the
            bibliography/appendix tail are preserved verbatim as non-rewritable files.
  text   -- best-effort split of PDF-extracted text on heading lines. Formatting is already
            lost, so this is for a best-effort draft, never a final submission.

Usage:
  python3 split_paper.py --input paper.tex --format latex --out OUTDIR
  python3 split_paper.py --input paper.txt --format text  --out OUTDIR
  python3 split_paper.py --input paper.tex --out OUTDIR         # auto-detect by extension

Outputs in OUTDIR:
  00_front.<ext>          front matter, NOT rewritten (preamble/title/abstract, or text head)
  NN_<slug>.<ext>         one rewritable section each
  zz_tail.<ext>           bibliography + appendix + closing, NOT rewritten (latex only)
  context_pack.md         title, abstract, section map, best-effort defined terms
  manifest.json           machine-readable index of the above

Stdlib only.
"""

import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Optional

CANON_HEADINGS = (
    "abstract", "introduction", "related work", "background", "preliminaries",
    "method", "methods", "methodology", "approach", "model", "system",
    "experiment", "experiments", "experimental setup", "setup", "results",
    "evaluation", "analysis", "discussion", "conclusion", "conclusions",
    "limitations", "ethics statement", "broader impact", "acknowledgment",
    "acknowledgments", "acknowledgement", "acknowledgements",
)
STOP_HEADINGS = ("references", "bibliography", "appendix", "appendices")


def _slug(s: str, n: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return (s or "section")[:n]


# ---------------------------------------------------------------------------
# LaTeX
# ---------------------------------------------------------------------------

def split_latex(text: str) -> Dict:
    # Find where the rewritable body starts. Prefer the first \section; everything before it
    # (preamble, \maketitle, abstract) is front matter kept verbatim.
    sec_re = re.compile(r"(?m)^[^%]*\\section\*?\{")
    stop_re = re.compile(r"(?m)^[^%]*\\(appendix|bibliography\b|begin\{thebibliography\})")

    first_sec = sec_re.search(text)
    if not first_sec:
        # No sections found. Treat the whole thing as one rewritable block after \begin{document}.
        doc = re.search(r"(?m)^[^%]*\\begin\{document\}", text)
        cut = doc.end() if doc else 0
        return {
            "front": text[:cut],
            "sections": [{"heading": "Body", "text": text[cut:]}],
            "tail": "",
        }

    front = text[:first_sec.start()]
    body_and_tail = text[first_sec.start():]

    # Where does the non-rewritable tail (appendix/bibliography) begin?
    stop = stop_re.search(body_and_tail)
    if stop:
        body = body_and_tail[:stop.start()]
        tail = body_and_tail[stop.start():]
    else:
        # keep \end{document} out of the last section
        end = re.search(r"(?m)^[^%]*\\end\{document\}", body_and_tail)
        if end:
            body = body_and_tail[:end.start()]
            tail = body_and_tail[end.start():]
        else:
            body, tail = body_and_tail, ""

    # Split body on each \section boundary.
    heads = list(re.finditer(r"(?m)^([^%]*\\section\*?\{(.+?)\})", body))
    sections = []
    for i, h in enumerate(heads):
        start = h.start()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        heading = re.sub(r"\\[a-zA-Z]+|[{}]", "", h.group(2)).strip()
        sections.append({"heading": heading, "text": body[start:end]})
    return {"front": front, "sections": sections, "tail": tail}


def latex_context(text: str) -> Dict:
    title_m = re.search(r"\\title\{(.+?)\}", text, re.DOTALL)
    title = re.sub(r"\s+", " ", re.sub(r"\\[a-zA-Z]+|[{}]", "", title_m.group(1))).strip() if title_m else ""
    abs_m = re.search(r"\\begin\{abstract\}(.+?)\\end\{abstract\}", text, re.DOTALL)
    abstract = abs_m.group(1).strip() if abs_m else ""
    # best-effort defined terms: \newcommand names and "Full Name (ACRO)" acronyms
    cmds = re.findall(r"\\newcommand\*?\{(\\[a-zA-Z]+)\}", text)
    acros = re.findall(r"\b([A-Z][A-Za-z0-9\- ]{2,40}?)\s\(([A-Z]{2,6})\)", text)
    terms = sorted(set([a[1] for a in acros])) + sorted(set(cmds))
    return {"title": title, "abstract": abstract, "terms": terms[:40]}


# ---------------------------------------------------------------------------
# Text (PDF-extracted, best-effort)
# ---------------------------------------------------------------------------

def _is_heading(line: str) -> Optional[str]:
    s = line.strip()
    if not s or len(s) > 70 or s.endswith((".", ",", ";", ":")):
        return None
    low = s.lower()
    # numbered heading, e.g. "3 Related Work" or "3.1 Setup"
    m = re.match(r"^(\d+(?:\.\d+)*)\.?\s+([A-Z][\w].{1,50})$", s)
    if m:
        return s
    # bare canonical heading
    key = re.sub(r"^\d+(\.\d+)*\.?\s*", "", low).strip()
    if key in CANON_HEADINGS or key in STOP_HEADINGS:
        return s
    return None


def split_text(text: str) -> Dict:
    lines = text.split("\n")
    heads = []  # (line_index, heading_text, is_stop)
    for i, ln in enumerate(lines):
        h = _is_heading(ln)
        if h:
            key = re.sub(r"^\d+(\.\d+)*\.?\s*", "", h.lower()).strip()
            heads.append((i, h, key in STOP_HEADINGS))
    if not heads:
        return {"front": "", "sections": [{"heading": "Body", "text": text}], "tail": ""}

    # front = everything before the first heading
    front = "\n".join(lines[: heads[0][0]])
    # find the first stop heading to cut the tail
    stop_idx = next((h[0] for h in heads if h[2]), len(lines))
    tail = "\n".join(lines[stop_idx:]) if stop_idx < len(lines) else ""

    sections = []
    body_heads = [h for h in heads if h[0] < stop_idx]
    for j, (li, htext, _) in enumerate(body_heads):
        start = li
        end = body_heads[j + 1][0] if j + 1 < len(body_heads) else stop_idx
        sections.append({"heading": htext.strip(), "text": "\n".join(lines[start:end])})
    return {"front": front, "sections": sections, "tail": tail}


def text_context(text: str) -> Dict:
    lines = [l.strip() for l in text.split("\n")]
    title = next((l for l in lines if l), "")
    ai = next((i for i, l in enumerate(lines) if l.lower() == "abstract"), None)
    abstract = ""
    if ai is not None:
        chunk = []
        for l in lines[ai + 1: ai + 40]:
            if _is_heading(l):
                break
            chunk.append(l)
        abstract = " ".join(chunk).strip()
    acros = re.findall(r"\b([A-Z][A-Za-z0-9\- ]{2,40}?)\s\(([A-Z]{2,6})\)", text)
    return {"title": title, "abstract": abstract, "terms": sorted(set(a[1] for a in acros))[:40]}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Split a paper into sections + a context pack.")
    ap.add_argument("--input", required=True, help="Path to a .tex or .txt file")
    ap.add_argument("--format", choices=["latex", "text", "auto"], default="auto")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    src = Path(args.input)
    text = src.read_text(encoding="utf-8", errors="replace")
    fmt = args.format
    if fmt == "auto":
        fmt = "latex" if src.suffix.lower() in (".tex", ".latex") else "text"
    ext = "tex" if fmt == "latex" else "txt"

    if fmt == "latex":
        parts = split_latex(text)
        ctx = latex_context(text)
        if re.search(r"(?m)^[^%]*\\(input|include)\{", text):
            print("WARNING: \\input/\\include found. Only the main file is split; included "
                  "files are not handled. Inline them first for a complete rewrite.")
    else:
        parts = split_text(text)
        ctx = text_context(text)
        print("NOTE: text mode is best-effort. Section boundaries are heuristic and formatting "
              "was already lost in PDF extraction. Do not use the result as a final submission.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    manifest = {"format": fmt, "title": ctx["title"], "front": None, "tail": None, "sections": []}

    if parts["front"].strip():
        fp = out / f"00_front.{ext}"
        fp.write_text(parts["front"], encoding="utf-8")
        manifest["front"] = fp.name
    for i, sec in enumerate(parts["sections"], start=1):
        fp = out / f"{i:02d}_{_slug(sec['heading'])}.{ext}"
        fp.write_text(sec["text"], encoding="utf-8")
        manifest["sections"].append({"index": i, "file": fp.name,
                                     "heading": sec["heading"], "rewrite": True})
    if parts["tail"].strip():
        tp = out / f"zz_tail.{ext}"
        tp.write_text(parts["tail"], encoding="utf-8")
        manifest["tail"] = tp.name

    # Context pack
    terms = "\n".join(f"- {t}" for t in ctx["terms"]) or "- (none auto-detected)"
    secmap = "\n".join(f"{s['index']}. {s['heading']} ({s['file']})" for s in manifest["sections"])
    (out / "context_pack.md").write_text(
        f"# Context pack\n\n"
        f"Shared brief for every section rewrite agent. Keep terminology and claims consistent "
        f"with this. Do not contradict the abstract or restate it.\n\n"
        f"## Title\n{ctx['title'] or '(not detected)'}\n\n"
        f"## Abstract\n{ctx['abstract'] or '(not detected)'}\n\n"
        f"## Section map (rewritable)\n{secmap}\n\n"
        f"## Defined terms and notation (best-effort, keep verbatim)\n{terms}\n",
        encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"format: {fmt}")
    print(f"front: {manifest['front']}   tail: {manifest['tail']}")
    print(f"rewritable sections: {len(manifest['sections'])}")
    for s in manifest["sections"]:
        print(f"  {s['index']:02d}  {s['heading']}  ->  {s['file']}")
    print(f"context pack: {out / 'context_pack.md'}")
    print(f"manifest: {out / 'manifest.json'}")


if __name__ == "__main__":
    main()
