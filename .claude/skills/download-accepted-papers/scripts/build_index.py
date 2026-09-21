#!/usr/bin/env python3
"""
build_index.py — Build an index of downloaded papers from venue_summary.json.

Writes index.md (markdown table, sorted by mean rating descending) and
index.csv (same data, one row per paper) into the venue directory.

Usage:
    python build_index.py --venue-dir openreview-chair-data/caisc_2026_conference
"""

import argparse
import csv
import json
import statistics
from pathlib import Path


def _numeric(values: list) -> list:
    out = []
    for value in values or []:
        if value is None:
            continue
        try:
            out.append(float(str(value).split(":")[0].strip()))
        except ValueError:
            continue
    return out


def main():
    parser = argparse.ArgumentParser(description="Index downloaded venue papers.")
    parser.add_argument("--venue-dir", required=True)
    args = parser.parse_args()

    venue_dir = Path(args.venue_dir).resolve()
    summary = json.loads((venue_dir / "venue_summary.json").read_text(encoding="utf-8"))
    papers = summary["papers"]

    rows = []
    for paper in papers:
        ratings = _numeric(paper.get("ratings", []))
        rows.append({
            "number": paper["number"],
            "title": paper["title"],
            "track": paper.get("submission_track", ""),
            "type": paper.get("submission_type", ""),
            "decision": paper.get("decision", ""),
            "num_reviews": paper.get("num_official_reviews", 0),
            "mean_rating": round(statistics.mean(ratings), 2) if ratings else "",
            "min_rating": min(ratings) if ratings else "",
            "max_rating": max(ratings) if ratings else "",
            "ratings": ", ".join(str(r) for r in paper.get("ratings", []) if r is not None),
            "forum_url": paper.get("forum_url", ""),
            "dir": Path(paper["paper_dir"]).name,
        })

    rows.sort(key=lambda r: (r["mean_rating"] if r["mean_rating"] != "" else -1), reverse=True)

    csv_path = venue_dir / "index.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        f"# {summary['venue']} — downloaded papers ({summary['filter']})",
        "",
        f"Total: {summary['num_papers']} papers. Sorted by mean reviewer rating.",
        "",
        "| # | Mean | Ratings | Reviews | Title | Track | Type |",
        "|---|------|---------|---------|-------|-------|------|",
    ]
    for row in rows:
        title = row["title"].replace("|", "\\|")
        lines.append(
            f"| {row['number']} | {row['mean_rating']} | {row['ratings']} | "
            f"{row['num_reviews']} | [{title}]({row['forum_url']}) | "
            f"{row['track']} | {row['type']} |"
        )
    md_path = venue_dir / "index.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {md_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
