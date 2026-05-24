#!/usr/bin/env python3
"""
hallucination_check.py -- Check paper references for hallucinated citations.

Uses the hallucinator package to extract references from a PDF and validate
them against offline databases (DBLP, ACL, OpenAlex, IACR). Falls back to
remote APIs for any references not matched locally.

Usage:
    python hallucination_check.py --pdf-path PAPER.pdf --out-dir OUT_DIR
"""

import argparse
import os
import sys
from pathlib import Path

from hallucinator import (
    PdfExtractor,
    Validator,
    ValidatorConfig,
    CheckStats,
)

HALLUCINATOR_DATA_DIR = Path.home() / ".local" / "share" / "hallucinator"

OFFLINE_DBS = {
    "dblp_offline_path": "dblp.db",
    "acl_offline_path": "acl.db",
    "openalex_offline_path": "openalex.idx",
    "iacr_eprint_offline_path": "iacr.db",
    "arxiv_offline_path": "arxiv.db",
}


def _db_is_ready(db_path: Path) -> bool:
    """Check that a SQLite database is not being actively written to."""
    if not db_path.exists():
        return False
    wal = db_path.with_name(db_path.name + "-wal")
    if wal.exists() and wal.stat().st_size > 0:
        return False
    if db_path.stat().st_size < 1024:
        return False
    return True


def _file_is_locked(lock_path: Path) -> bool:
    """Check if a lock file is held by another process (best-effort)."""
    import fcntl
    try:
        fd = os.open(str(lock_path), os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except (OSError, IOError):
            return True
        finally:
            os.close(fd)
    except OSError:
        return False


def _block_network():
    """Point HTTP(S) traffic at a dead proxy to make remote lookups fail fast."""
    os.environ.setdefault("http_proxy", "http://127.0.0.1:1")
    os.environ.setdefault("https_proxy", "http://127.0.0.1:1")


def build_config(offline_only: bool = True) -> ValidatorConfig:
    config = ValidatorConfig()
    for attr, filename in OFFLINE_DBS.items():
        db_path = HALLUCINATOR_DATA_DIR / filename
        if db_path.is_dir():
            writer_lock = db_path / ".tantivy-writer.lock"
            if writer_lock.exists() and _file_is_locked(writer_lock):
                continue
            setattr(config, attr, str(db_path))
        elif _db_is_ready(db_path):
            setattr(config, attr, str(db_path))

    cache_path = HALLUCINATOR_DATA_DIR / "cache.db"
    config.cache_path = str(cache_path)

    # Backends with offline DBs (dblp, acl, arxiv, openalex) must stay enabled
    # because disabled_dbs disables both remote AND offline lookups.
    remote_only = [
        "crossref", "semantic_scholar",
        "neurips", "ssrn", "europe_pmc", "pubmed",
    ]
    config.disabled_dbs = remote_only

    if offline_only:
        config.db_timeout_secs = 1
        config.db_timeout_short_secs = 1
        config.max_rate_limit_retries = 0
        config.num_workers = 16

    return config


def status_icon(status: str) -> str:
    return {
        "verified": "VERIFIED",
        "not_found": "NOT FOUND",
        "author_mismatch": "AUTHOR MISMATCH",
    }.get(status, status.upper())


def write_report(results, refs, out_path: Path) -> None:
    stats = Validator.stats(results)

    lines = ["# Hallucination Check\n"]

    lines.append("## Summary\n")
    lines.append(f"- **Total references extracted:** {stats.total}")
    lines.append(f"- **Verified:** {stats.verified}")
    lines.append(f"- **Not found (potential hallucinations):** {stats.not_found}")
    lines.append(f"- **Author mismatch:** {stats.author_mismatch}")
    lines.append(f"- **Retracted:** {stats.retracted}")
    lines.append("")

    if stats.not_found == 0 and stats.author_mismatch == 0 and stats.retracted == 0:
        lines.append(
            "All extracted references were verified against academic databases. "
            "No hallucinated citations detected.\n"
        )
    else:
        if stats.not_found > 0:
            lines.append(
                f"**{stats.not_found} reference(s) could not be found** in any "
                "academic database. These may be hallucinated citations, or they may "
                "be very recent, obscure, or from non-indexed venues.\n"
            )
        if stats.author_mismatch > 0:
            lines.append(
                f"**{stats.author_mismatch} reference(s) had author mismatches.** "
                "The title was found but the listed authors do not match the "
                "database record.\n"
            )
        if stats.retracted > 0:
            lines.append(
                f"**{stats.retracted} reference(s) have been retracted.**\n"
            )

    lines.append("## Detailed Results\n")
    lines.append("| # | Status | Title | Source |")
    lines.append("|---|--------|-------|--------|")

    for i, r in enumerate(results, 1):
        title = r.title.replace("|", "\\|") if r.title else "(unknown)"
        source = r.source or "-"
        lines.append(f"| {i} | {status_icon(r.status)} | {title} | {source} |")

    lines.append("")

    flagged = [r for r in results if r.status in ("not_found", "author_mismatch")]
    if flagged:
        lines.append("## Flagged References\n")
        for r in flagged:
            lines.append(f"### {status_icon(r.status)}: {r.title}\n")
            if r.raw_citation:
                lines.append(f"**Raw citation:** {r.raw_citation[:300]}\n")
            if r.ref_authors:
                lines.append(f"**Listed authors:** {', '.join(r.ref_authors)}\n")
            if r.status == "author_mismatch" and r.found_authors:
                lines.append(
                    f"**Database authors:** {', '.join(r.found_authors)}\n"
                )
            if r.failed_dbs:
                lines.append(
                    f"**Checked databases:** {', '.join(r.failed_dbs)}\n"
                )
            lines.append("")

    retracted = [r for r in results if r.retraction_info]
    if retracted:
        lines.append("## Retracted References\n")
        for r in retracted:
            lines.append(f"- **{r.title}**")
            if r.retraction_info:
                lines.append(f"  Retraction info available at: {r.paper_url or 'see database'}\n")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check paper references for hallucinated citations."
    )
    parser.add_argument("--pdf-path", required=True, help="Path to the paper PDF")
    parser.add_argument("--out-dir", required=True, help="Output directory for the report")
    parser.add_argument("--allow-remote", action="store_true",
                        help="Allow remote API fallback for unmatched references")
    args = parser.parse_args()

    sys.stdout.reconfigure(line_buffering=True)

    pdf_path = Path(args.pdf_path).resolve()
    out_dir = Path(args.out_dir).resolve()

    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Extracting references from {pdf_path.name} ...")
    extractor = PdfExtractor()
    extraction = extractor.extract(str(pdf_path))
    refs = extraction.references

    if not refs:
        report_path = out_dir / "06_hallucination_check.md"
        report_path.write_text(
            "# Hallucination Check\n\n"
            "No references could be extracted from this paper. "
            "The reference section may use a format that the extractor cannot parse.\n",
            encoding="utf-8",
        )
        print("No references extracted. Report written.")
        return

    print(f"Extracted {len(refs)} references. Validating against offline databases ...")

    offline_only = not args.allow_remote
    if offline_only:
        _block_network()
    config = build_config(offline_only=offline_only)

    active_dbs = []
    for attr, filename in OFFLINE_DBS.items():
        if getattr(config, attr, None):
            active_dbs.append(filename)
    if active_dbs:
        print(f"  Offline databases: {', '.join(active_dbs)}")
    else:
        print("  Warning: no offline databases found. Remote APIs will be used.")

    def on_progress(event):
        if event.event_type == "checking":
            print(f"  [{event.index + 1}/{event.total}] Checking: {event.title[:80]}")
        elif event.event_type == "result":
            r = event.result
            icon = {"verified": "+", "not_found": "?", "author_mismatch": "~"}.get(
                r.status, "!"
            )
            print(f"  [{icon}] {r.title[:80]}")

    try:
        validator = Validator(config)
    except RuntimeError as e:
        msg = str(e)
        print(f"  Warning: {msg}")
        print("  Retrying with problematic offline databases removed ...")
        for attr, filename in OFFLINE_DBS.items():
            if filename in msg:
                setattr(config, attr, None)
                print(f"  Disabled: {filename}")
        validator = Validator(config)

    results = validator.check(refs, progress=on_progress)

    report_path = out_dir / "06_hallucination_check.md"
    write_report(results, refs, report_path)

    stats = Validator.stats(results)
    print(f"\nDone. Verified: {stats.verified}/{stats.total}, "
          f"Not found: {stats.not_found}, "
          f"Author mismatch: {stats.author_mismatch}, "
          f"Retracted: {stats.retracted}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
