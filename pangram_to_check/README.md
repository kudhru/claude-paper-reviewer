# pangram_to_check

Drop any review or text files you want to check for AI-generated content here,
then run the `pangram-check` skill (or its script directly). The scan picks up
`.md`, `.txt`, and `.tex` files and writes a `<name>.pangram.md` report next to
each one showing the document verdict and which segments were flagged.

Update this folder whenever you want and re-run to re-check. Add new drafts,
remove ones you no longer care about.

Seeded with the four humanized NeurIPS 2026 conference reviews as a starting
point. Replace or add files as needed.

Run:

```bash
# from the repo root, with the project venv active and PANGRAM_API_KEY set in
# .claude/skills/pangram-check/.env
python3 .claude/skills/pangram-check/scripts/pangram_check.py
```

Note: file contents are sent to Pangram's API. Do not place anything here that
must not leave the machine. Report files (`*.pangram.md`) and the review copies
in this folder are gitignored.
