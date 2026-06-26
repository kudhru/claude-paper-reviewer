#!/usr/bin/env python3
"""
detect_prompt_injection.py — Forensic prompt-injection scan for a paper PDF.

Why this exists
---------------
A reviewer (human or LLM) who reads only the *rendered* page can miss an
injection that lives in the PDF's *text layer*. The most dangerous real-world
case is glyph substitution: a footer whose drawn glyphs spell an innocuous
notice ("Confidential reviewer copy ...") while the font's ToUnicode map makes
any text extractor read a hidden instruction ("In your output you MUST include
the following phrases ..."). Venues use this as a honeypot to catch
LLM-assisted reviewing. A plain visual read never sees it.

This script checks every common injection vector and prints a verdict:

  1. Instruction scan over the EXTRACTED TEXT LAYER (primary catch). Looks for
     reviewer-directed imperatives and phrase-planting instructions.
  2. Text-layer vs rendered divergence — visually-absent ("zero-ink") text:
     render each page, sample pixels under every text span, flag spans that
     paint no visible ink (white-on-white, occluded by a box, ~0 opacity).
  3. Glyph-substitution / font anomalies: abnormally many tiny subset fonts and
     paired-codepoint font names (the signature of a glyph-remapping tool).
  4. Invisible text render mode (3 Tr) in content streams.
  5. Off-page / out-of-bounds text.
  6. Document + XMP metadata.
  7. Annotations & form-field widgets (hidden /Contents).
  8. Embedded JavaScript.
  9. Optional content groups (hidden layers).
 10. Embedded files / attachments.

Exit code: 0 = clean, 2 = at least one HIGH-severity finding, 1 = error.

Requires PyMuPDF (`pip install PyMuPDF`). Falls back to poppler (`pdftotext`,
`pdffonts`) for checks 1 and 3 if PyMuPDF is unavailable.

Usage:
    python3 detect_prompt_injection.py --pdf PAPER.pdf [--pdf OTHER.pdf ...]
    python3 detect_prompt_injection.py --pdf PAPER.pdf --json report.json
"""
import argparse
import json
import re
import shutil
import subprocess
import sys

try:
    import fitz  # PyMuPDF
    HAVE_FITZ = True
except Exception:
    HAVE_FITZ = False

# --- instruction / injection patterns aimed at a reviewer or an LLM ---
# High severity: clearly an instruction directed at the reader/model.
HIGH_PATTERNS = [
    r"in your (output|review|response|answer)",
    r"you must (include|write|output|mention|say|add|use|begin|start|ignore)",
    r"must include all of the following",
    r"the following phrases?",
    r"ignore (all |any )?(previous|prior|above|the) (instruction|prompt|text|content)",
    r"disregard (all|any|the|previous)",
    r"as an? (ai|language model|large language model|assistant)",
    r"do not (mention|reveal|disclose|list|describe|output|show|reduce)",
    r"(give|assign|provide) (a |an )?(high|positive|good|strong|top|maximum|perfect) (score|rating|recommendation|review)",
    r"recommend (accept|acceptance|to accept)",
    r"(strong|clear|definite) accept",
    r"accept this (paper|submission|manuscript)",
    r"(only|exclusively) (highlight|mention|discuss|focus on) (the )?(strength|positive|merit)",
    r"do not (highlight|mention|focus on) (the )?(weakness|negative|flaw|limitation)",
    r"(begin|start|end) your (review|response|output) with",
    r"include the (word|phrase|sentence|token)",
    r"as a reviewer,? you",
    r"dear (reviewer|ai|assistant|llm|chatgpt|model)",
    r"if you are (an? )?(ai|llm|language model|bot|machine|automated)",
    r"this is (a )?(test|canary|honeypot|trap)",
]
# Medium severity: suspicious but can appear in legitimate text (review forms,
# checklists). Reported but not alone a verdict.
MED_PATTERNS = [
    r"reviewers? (are|should|must|are instructed to) ",
    r"system prompt",
    r"prompt injection",
]
HIGH_RE = re.compile("|".join(f"(?:{p})" for p in HIGH_PATTERNS), re.IGNORECASE)
MED_RE = re.compile("|".join(f"(?:{p})" for p in MED_PATTERNS), re.IGNORECASE)
ALPHA_RE = re.compile(r"[A-Za-z]")

DPI = 200
ZOOM = DPI / 72.0
DARK_INK_LUM = 170     # darkest pixel brighter than this => no visible ink
MIN_CONTRAST = 40


def _luminance(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


def _scan_text(full_text):
    """Return (high_hits, med_hits) as lists of (match, context)."""
    def collect(rx):
        out = []
        seen = set()
        for m in rx.finditer(full_text):
            s = max(0, m.start() - 70)
            e = min(len(full_text), m.end() + 90)
            ctx = re.sub(r"\s+", " ", full_text[s:e]).strip()
            key = ctx[:90]
            if key in seen:
                continue
            seen.add(key)
            out.append((m.group(0), ctx))
        return out
    return collect(HIGH_RE), collect(MED_RE)


def _poppler_fallback(path, findings):
    findings["mode"] = "poppler-fallback (PyMuPDF not installed)"
    if shutil.which("pdftotext"):
        try:
            txt = subprocess.check_output(["pdftotext", "-layout", path, "-"],
                                          stderr=subprocess.DEVNULL).decode("utf-8", "ignore")
        except Exception:
            txt = ""
        high, med = _scan_text(txt)
        findings["instruction_scan"] = {"high": high, "medium": med}
        if high:
            findings["verdict"]["high"].append("instruction patterns in text layer")
    if shutil.which("pdffonts"):
        try:
            out = subprocess.check_output(["pdffonts", path],
                                          stderr=subprocess.DEVNULL).decode("utf-8", "ignore")
        except Exception:
            out = ""
        nfonts = max(0, len(out.strip().splitlines()) - 2)
        pair = "_Pair_" in out or out.lower().count("+arialunicode") > 3
        findings["font_anomaly"] = {"font_count": nfonts, "paired_font_names": pair}
        if pair or nfonts > 120:
            findings["verdict"]["high"].append(
                f"font anomaly (count={nfonts}, paired_names={pair}) — possible glyph substitution")
    return findings


def analyze(path):
    findings = {
        "file": path,
        "mode": "pymupdf",
        "verdict": {"high": [], "medium": []},
    }
    if not HAVE_FITZ:
        return _poppler_fallback(path, findings)

    doc = fitz.open(path)

    # ---- gather full text layer + per-page render for ink sampling ----
    full_text_parts = []
    zero_ink = {}     # page -> reconstructed hidden string
    offpage = {}
    tr3_pages = []
    span_count = 0

    for pno in range(len(doc)):
        page = doc[pno]
        prect = page.rect
        full_text_parts.append(page.get_text("text"))

        # invisible render mode in content stream
        try:
            cont = page.read_contents().decode("latin-1", "ignore")
            if re.search(r"(^|\s)3\s+Tr(\s|$)", cont):
                tr3_pages.append(pno + 1)
        except Exception:
            pass

        pix = page.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
        n, W, H, S = pix.n, pix.width, pix.height, pix.samples

        def px(ix, iy):
            if ix < 0 or iy < 0 or ix >= W or iy >= H:
                return (255, 255, 255)
            o = (iy * W + ix) * n
            return (S[o], S[o + 1], S[o + 2])

        hidden_spans = []
        for b in page.get_text("dict").get("blocks", []):
            for line in b.get("lines", []):
                for sp in line.get("spans", []):
                    t = sp.get("text", "")
                    if not ALPHA_RE.search(t):
                        continue
                    span_count += 1
                    x0, y0, x1, y1 = sp["bbox"]
                    # off-page
                    if (x1 < prect.x0 - 1 or x0 > prect.x1 + 1 or
                            y1 < prect.y0 - 1 or y0 > prect.y1 + 1):
                        offpage.setdefault(pno + 1, []).append(t)
                        continue
                    ix0, iy0 = int(x0 * ZOOM) + 1, int(y0 * ZOOM) + 1
                    ix1, iy1 = int(x1 * ZOOM) - 1, int(y1 * ZOOM) - 1
                    if ix1 <= ix0:
                        ix1 = ix0 + 1
                    if iy1 <= iy0:
                        iy1 = iy0 + 1
                    mn, mx = 255, 0
                    for iy in range(iy0, iy1 + 1, max(1, (iy1 - iy0) // 10)):
                        for ix in range(ix0, ix1 + 1, max(1, (ix1 - ix0) // 30)):
                            lum = _luminance(*px(ix, iy))
                            mn = min(mn, lum)
                            mx = max(mx, lum)
                    if mn > DARK_INK_LUM and (mx - mn) < MIN_CONTRAST:
                        hidden_spans.append((y0, x0, t))
        if hidden_spans:
            hidden_spans.sort(key=lambda s: (round(s[0] / 3), s[1]))
            recon = re.sub(r"\s+", " ", " ".join(s[2] for s in hidden_spans)).strip()
            zero_ink[pno + 1] = recon

    full_text = "\n".join(full_text_parts)

    # ---- 1. instruction scan over extracted text ----
    high, med = _scan_text(full_text)
    findings["instruction_scan"] = {"high": high, "medium": med}
    if high:
        findings["verdict"]["high"].append("reviewer-directed instruction(s) in extracted text layer")
    if med:
        findings["verdict"]["medium"].append("suspicious phrasing in text layer (review-form-like)")

    # ---- 2. zero-ink (visually absent) text ----
    findings["zero_ink_text"] = zero_ink
    # only escalate if the hidden text contains letters forming words (not stray labels)
    meaningful = {p: s for p, s in zero_ink.items() if len(re.sub(r"[^A-Za-z]", "", s)) >= 12}
    if meaningful:
        findings["verdict"]["high"].append("visually-hidden (zero-ink) text with substantial content")
    elif zero_ink:
        findings["verdict"]["medium"].append("small amount of visually-absent text (often figure labels)")

    # ---- 3. font anomalies / glyph substitution ----
    font_count = 0
    tiny_subset = 0
    paired = False
    for x in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(x, compressed=False) or ""
        except Exception:
            continue
        if "/Type/Font" in obj.replace(" ", "") or "/BaseFont" in obj:
            font_count += 1
            if "_Pair_" in obj or "Pair_" in obj:
                paired = True
    fa = {"font_object_count": font_count, "paired_font_names": paired}
    findings["font_anomaly"] = fa
    if paired or font_count > 120:
        findings["verdict"]["high"].append(
            f"font anomaly (font objects={font_count}, paired_names={paired}) — glyph-substitution signature")

    # ---- 4. invisible render mode ----
    findings["invisible_render_mode_pages"] = tr3_pages
    if tr3_pages:
        findings["verdict"]["medium"].append(f"invisible text render mode (3 Tr) on pages {tr3_pages}")

    # ---- 5. off-page text ----
    findings["offpage_text"] = {p: re.sub(r"\s+", " ", " ".join(v)).strip()[:200]
                                for p, v in offpage.items()}
    if any(len("".join(v)) >= 12 for v in offpage.values()):
        findings["verdict"]["high"].append("substantial text positioned off the visible page")

    # ---- 6. metadata + XMP ----
    md = {k: v for k, v in (doc.metadata or {}).items() if v}
    try:
        xml = doc.get_xml_metadata() if hasattr(doc, "get_xml_metadata") else ""
    except Exception:
        xml = ""
    xmp_hit = bool(xml and (HIGH_RE.search(xml) or MED_RE.search(xml)))
    findings["metadata"] = md
    findings["xmp_injection_keywords"] = xmp_hit
    if xmp_hit:
        findings["verdict"]["high"].append("injection keywords in XMP metadata")

    # ---- 7. annotations ----
    annots = []
    for pno in range(len(doc)):
        for a in (doc[pno].annots() or []):
            info = a.info
            content = (info.get("content") or "").strip()
            if content:
                annots.append({"page": pno + 1, "type": str(a.type), "content": content[:300]})
    findings["annotations"] = annots
    if any(HIGH_RE.search(a["content"]) for a in annots):
        findings["verdict"]["high"].append("injection text inside an annotation")

    # ---- 8. JavaScript ----
    js = []
    for x in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(x, compressed=False) or ""
        except Exception:
            continue
        if "/JavaScript" in obj or "/JS" in obj:
            js.append(x)
    findings["javascript_objects"] = js
    if js:
        findings["verdict"]["medium"].append("embedded JavaScript present")

    # ---- 9. optional content groups (layers) ----
    try:
        ocgs = doc.get_ocgs() or {}
    except Exception:
        ocgs = {}
    findings["optional_content_groups"] = list(ocgs.keys())

    # ---- 10. embedded files ----
    nef = doc.embfile_count() if hasattr(doc, "embfile_count") else 0
    findings["embedded_file_count"] = nef
    if nef:
        findings["verdict"]["medium"].append(f"{nef} embedded file(s)/attachment(s)")

    findings["pages"] = len(doc)
    findings["spans_scanned"] = span_count
    doc.close()
    return findings


def print_report(f):
    print("=" * 92)
    print(f"FILE: {f['file']}")
    print("=" * 92)
    high = f["verdict"]["high"]
    med = f["verdict"]["medium"]
    if high:
        print("VERDICT: *** PROMPT INJECTION LIKELY — HIGH severity ***")
    elif med:
        print("VERDICT: SUSPICIOUS — review the medium-severity items below")
    else:
        print("VERDICT: clean — no injection signals found")
    for h in high:
        print(f"  [HIGH] {h}")
    for m in med:
        print(f"  [MED ] {m}")
    print()

    sc = f.get("instruction_scan", {})
    if sc.get("high"):
        print("--- reviewer-directed instructions in the EXTRACTED TEXT LAYER ---")
        for kw, ctx in sc["high"]:
            print(f"  • match {kw!r}: ...{ctx}...")
        print()
    if f.get("zero_ink_text"):
        print("--- visually-hidden (zero-ink) text, reconstructed per page ---")
        for p, s in f["zero_ink_text"].items():
            print(f"  p{p}: {s[:400]!r}")
        print()
    fa = f.get("font_anomaly", {})
    if fa.get("paired_font_names") or fa.get("font_object_count", 0) > 120 or fa.get("font_count", 0) > 120:
        print(f"--- font anomaly: {fa} (glyph-substitution signature) ---\n")
    if f.get("offpage_text"):
        print(f"--- off-page text: {f['offpage_text']} ---\n")
    if f.get("annotations"):
        print(f"--- annotations with content: {f['annotations']} ---\n")
    meta = f.get("metadata", {})
    if meta:
        print(f"--- metadata: {meta} ---\n")


def main():
    ap = argparse.ArgumentParser(description="Forensic prompt-injection scan for paper PDFs.")
    ap.add_argument("--pdf", action="append", required=True, help="PDF path (repeatable)")
    ap.add_argument("--json", default=None, help="Write full findings as JSON to this path")
    args = ap.parse_args()

    if not HAVE_FITZ:
        print("WARNING: PyMuPDF not installed; running reduced poppler fallback. "
              "Install with: pip install PyMuPDF", file=sys.stderr)

    all_findings = []
    worst = 0
    for p in args.pdf:
        try:
            f = analyze(p)
        except Exception as e:
            print(f"ERROR analyzing {p}: {e}", file=sys.stderr)
            worst = max(worst, 1)
            continue
        all_findings.append(f)
        print_report(f)
        if f["verdict"]["high"]:
            worst = 2

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(all_findings, fh, indent=2, ensure_ascii=False)
        print(f"JSON findings written to {args.json}")

    sys.exit(worst)


if __name__ == "__main__":
    main()
