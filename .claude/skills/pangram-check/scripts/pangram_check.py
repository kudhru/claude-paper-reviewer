#!/usr/bin/env python3
"""
pangram_check.py — Flag which portions of a review (or any text file) read as
AI-generated, using the Pangram Python SDK.

For each input file it calls Pangram's per-segment ("windows") detector and
reports the document-level verdict plus every flagged segment, mapped back to
the nearest Markdown heading so you can see exactly which part of the review
tripped the detector.

API key: read from PANGRAM_API_KEY, or from a `.env` file in the skill folder
(one line: PANGRAM_API_KEY=sk-...). The .env is loaded automatically.

Usage:
    python3 pangram_check.py                          # scan the default folder
    python3 pangram_check.py --input-dir DIR
    python3 pangram_check.py --file a.md --file b.md
    python3 pangram_check.py --threshold 0.5 --out-dir reports/

Install once:  pip install pangram-sdk
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent          # .../skills/pangram-check
REPO_ROOT = Path(__file__).resolve().parents[4]             # repo root
DEFAULT_INPUT_DIR = REPO_ROOT / "pangram_to_check"
DEFAULT_EXTS = [".md", ".txt", ".tex"]

# Pangram labels that count as "not clean human".
FLAG_LABELS = {"AI", "AI-Assisted", "Mixed"}


def load_env():
    """Load PANGRAM_API_KEY from the skill-folder .env if not already set."""
    if os.environ.get("PANGRAM_API_KEY"):
        return
    env_path = SKILL_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def get_client():
    try:
        from pangram import Pangram  # primary SDK entrypoint
        return Pangram()
    except ImportError:
        try:
            from pangram.text_classifier import PangramText
            return PangramText()
        except Exception as e:
            print("ERROR: Pangram SDK not installed. Run: pip install pangram-sdk",
                  file=sys.stderr)
            raise SystemExit(1) from e
    except ValueError as e:
        print("ERROR: no API key. Set PANGRAM_API_KEY or add it to "
              f"{SKILL_DIR / '.env'} as  PANGRAM_API_KEY=...", file=sys.stderr)
        raise SystemExit(1) from e


def heading_map(text):
    """Return a sorted list of (char_offset, heading_text) for Markdown headings."""
    out = []
    for m in re.finditer(r"(?m)^(#{1,6})\s+(.*)$", text):
        out.append((m.start(), m.group(2).strip()))
    return out


def heading_for(offset, headings):
    cur = "(top of document)"
    for off, h in headings:
        if off <= offset:
            cur = h
        else:
            break
    return cur


def resolve_files(args):
    files = []
    if args.file:
        files = [Path(f).resolve() for f in args.file]
    else:
        d = Path(args.input_dir).resolve()
        if not d.exists():
            print(f"ERROR: input dir not found: {d}", file=sys.stderr)
            raise SystemExit(1)
        exts = [e if e.startswith(".") else "." + e for e in args.ext]
        files = sorted(p for p in d.rglob("*") if p.is_file()
                       and p.suffix.lower() in exts
                       and not p.name.endswith(".pangram.md")
                       and p.name.lower() != "readme.md")
    missing = [f for f in files if not f.exists()]
    if missing:
        print(f"ERROR: file(s) not found: {missing}", file=sys.stderr)
        raise SystemExit(1)
    return files


def analyze_file(client, path, threshold):
    text = path.read_text(encoding="utf-8")
    result = client.predict(text)
    headings = heading_map(text)

    windows = result.get("windows", []) or []
    flagged = []
    for w in windows:
        label = w.get("label", "")
        score = float(w.get("ai_assistance_score", 0) or 0)
        if label in FLAG_LABELS or score >= threshold:
            seg = (w.get("text", "") or "").strip().replace("\n", " ")
            flagged.append({
                "label": label,
                "ai_assistance_score": score,
                "confidence": w.get("confidence", ""),
                "section": heading_for(w.get("start_index", 0) or 0, headings),
                "start_index": w.get("start_index"),
                "end_index": w.get("end_index"),
                "word_count": w.get("word_count"),
                "excerpt": seg[:240] + ("..." if len(seg) > 240 else ""),
            })

    return {
        "file": str(path),
        "prediction_short": result.get("prediction_short", result.get("prediction", "")),
        "fraction_ai": result.get("fraction_ai"),
        "fraction_ai_assisted": result.get("fraction_ai_assisted"),
        "fraction_human": result.get("fraction_human"),
        "num_ai_segments": result.get("num_ai_segments"),
        "num_ai_assisted_segments": result.get("num_ai_assisted_segments"),
        "num_human_segments": result.get("num_human_segments"),
        "num_windows": len(windows),
        "num_flagged": len(flagged),
        "flagged": flagged,
        "headline": result.get("headline", ""),
        "_raw": result,
    }


def write_report(rep, out_path):
    lines = [f"# Pangram AI-detection report", "",
             f"**File:** `{rep['file']}`", "",
             f"- Verdict: **{rep['prediction_short']}**",
             f"- Fraction AI: {rep['fraction_ai']}",
             f"- Fraction AI-assisted: {rep['fraction_ai_assisted']}",
             f"- Fraction human: {rep['fraction_human']}",
             f"- Segments: {rep['num_windows']} total, {rep['num_flagged']} flagged "
             f"(AI: {rep['num_ai_segments']}, AI-assisted: {rep['num_ai_assisted_segments']}, "
             f"human: {rep['num_human_segments']})", ""]
    if rep["flagged"]:
        lines += ["## Flagged segments", ""]
        for i, f in enumerate(rep["flagged"], 1):
            lines += [
                f"### {i}. [{f['label']}] score {f['ai_assistance_score']:.2f} "
                f"({f['confidence']}) — under \"{f['section']}\"",
                f"chars {f['start_index']}–{f['end_index']}, {f['word_count']} words",
                "",
                f"> {f['excerpt']}", ""]
    else:
        lines += ["No segments flagged. The document reads as human across all windows.", ""]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Flag AI-generated portions of review files via Pangram.")
    ap.add_argument("--file", action="append", help="Specific file to check (repeatable)")
    ap.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR),
                    help=f"Folder to scan when no --file is given (default: {DEFAULT_INPUT_DIR})")
    ap.add_argument("--ext", action="append", default=None,
                    help=f"Extensions to include in --input-dir scan (default: {DEFAULT_EXTS})")
    ap.add_argument("--threshold", type=float, default=0.5,
                    help="Flag a segment if ai_assistance_score >= this (default: 0.5)")
    ap.add_argument("--out-dir", default=None,
                    help="Where to write <name>.pangram.md reports (default: next to each input)")
    ap.add_argument("--json", default=None, help="Also write all findings to this JSON path")
    args = ap.parse_args()
    if args.ext is None:
        args.ext = DEFAULT_EXTS

    load_env()
    if not os.environ.get("PANGRAM_API_KEY"):
        print("ERROR: PANGRAM_API_KEY not set. Add it to "
              f"{SKILL_DIR / '.env'} as  PANGRAM_API_KEY=your_key  (or export it).",
              file=sys.stderr)
        raise SystemExit(1)

    files = resolve_files(args)
    if not files:
        print(f"No files to check in {args.input_dir} "
              f"(extensions {args.ext}). Drop review files there and re-run.")
        return

    client = get_client()
    all_reps = []
    print(f"Checking {len(files)} file(s) with Pangram...\n")
    print(f"{'verdict':<14}{'AI%':>6}{'AIasst%':>9}{'human%':>8}  {'flagged':>8}  file")
    print("-" * 92)
    for path in files:
        try:
            rep = analyze_file(client, path, args.threshold)
        except Exception as e:
            print(f"ERROR checking {path}: {e}", file=sys.stderr)
            continue
        all_reps.append(rep)

        def pct(x):
            return f"{100*x:.0f}" if isinstance(x, (int, float)) else "?"
        print(f"{str(rep['prediction_short']):<14}"
              f"{pct(rep['fraction_ai']):>6}{pct(rep['fraction_ai_assisted']):>9}"
              f"{pct(rep['fraction_human']):>8}  {rep['num_flagged']:>3}/{rep['num_windows']:<4}  "
              f"{Path(rep['file']).name}")

        out_dir = Path(args.out_dir).resolve() if args.out_dir else path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        write_report(rep, out_dir / (path.stem + ".pangram.md"))

    if args.json and all_reps:
        clean = [{k: v for k, v in r.items() if k != "_raw"} for r in all_reps]
        Path(args.json).write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON findings: {args.json}")

    print(f"\nPer-file reports written next to each input as <name>.pangram.md"
          if not args.out_dir else f"\nReports in {args.out_dir}")


if __name__ == "__main__":
    main()
