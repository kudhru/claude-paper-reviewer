# Claude Paper Reviewer

A command-line tool that reviews academic papers using the **Claude Code CLI** through a structured, multi-round analysis pipeline — exactly as you would do it manually in the Claude web interface, but automated.

Each paper gets its own persistent Claude session. The 7 prompts are sent one at a time, and each response informs the next, producing richer and more thorough output than sending everything at once.

---

## How it works

| Step | What Claude does |
|------|-----------------|
| 0 | Reads the paper, checks for injected/adversarial prompts |
| 1 | Explains the paper in detail with intuition |
| 2 | Reviews readability and presentation, section by section |
| 3 | Checks for inconsistencies, contradictions, and gaps |
| 4 | Reviews novelty — performs a live web search for related work |
| 5 | Writes a revision plan for your target conference |
| 6 | Compiles everything into a single structured markdown document → PDF |

---

## Requirements

- **Claude Code CLI** installed and authenticated (`claude` must be on your PATH)
- **Python 3.9+** — no `pip install` needed, stdlib only
- **pandoc** (optional) — for PDF output: `brew install pandoc`

---

## Setup

```bash
git clone https://github.com/kudhru/claude-paper-reviewer.git
cd claude-paper-reviewer
```

Drop your PDFs into the `papers/` folder:

```bash
cp /path/to/my_paper.pdf papers/
```

---

## Usage

### Interactive mode (no arguments)

```bash
python paper_reviewer.py
```

You will be prompted to choose the papers directory, select which papers to review, and enter the conference name.

### Review all PDFs in a folder

```bash
python paper_reviewer.py --papers-dir ./papers --conference "ACL 2026"
```

### Review a single paper

```bash
python paper_reviewer.py --paper ./papers/my_paper.pdf --conference "EMNLP 2025"
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--paper FILE` | — | Single PDF to review |
| `--papers-dir DIR` | — | Directory of PDFs (all PDFs reviewed) |
| `--conference NAME` | — | Target conference / workshop / journal |
| `--reviews-dir DIR` | `./reviews` | Where to save output |
| `--model MODEL` | `claude-sonnet-4-6` | Claude model to use |

---

## Output

One timestamped sub-folder is created per paper:

```
reviews/
└── my_paper_20260508_143022/
    ├── 00_prompt_injection_check.md
    ├── 01_paper_explanation.md
    ├── 02_readability_and_presentation.md
    ├── 03_consistency_and_completeness.md
    ├── 04_novelty_and_related_work.md
    ├── 05_conference_review___acl_2026.md
    ├── 06_full_review_compilation.md
    └── 06_full_review_compilation.pdf   ← if pandoc is available
```

---

## Running with tmux (recommended)

Each step can take several minutes. If you close your laptop lid, macOS puts the machine to sleep and the script pauses. Running inside a **tmux** session protects against this: when the Mac wakes up, the session is still there and the script continues.

### Install tmux

```bash
brew install tmux
```

### Start a review session

```bash
# Create a named tmux session and start the review inside it
tmux new -s review
python paper_reviewer.py --papers-dir ./papers --conference "ACL 2026"
```

You can now close the lid. When you open it again, reattach to the session:

```bash
tmux attach -t review
```

### Useful tmux commands

| Command | What it does |
|---------|-------------|
| `tmux new -s review` | Start a new session named `review` |
| `tmux attach -t review` | Reattach to an existing session |
| `tmux ls` | List all active sessions |
| `Ctrl-b d` | Detach from session (leaves it running) |
| `Ctrl-b [` | Scroll through output (q to quit scroll mode) |

### If the script was killed during sleep

The script saves progress after every step. If the subprocess was killed rather than paused, just re-run the same command and enter `y` when asked to resume:

```
  Found incomplete review started at 2026-05-09 14:32:11
  Steps already done: [0, 1, 2]
  Resume from where it stopped? [y/n]: y
```

---

## Notes

- **Web search** is enabled only for step 4 (novelty review). Claude performs live searches to find related work not cited in the paper.
- The script runs Claude in read-only mode — it cannot modify your files.
- Each step can take 1–3 minutes depending on paper length and model load.
- You can change the target conference per run without re-running earlier steps.
