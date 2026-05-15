# Cowork Paper Reviewer

Review academic papers with Claude via **Cowork** — no `claude -p`, no API billing, same 6-step pipeline.

---

## How It Works

Claude reads `CLAUDE.md` and `review_prompts.json` for its exact operating instructions and verbatim prompts. All file operations go through `review_helpers.py`. Claude handles the reasoning and orchestration.

| Step | What Claude does | Session type |
|------|-----------------|--------------|
| 0 | Prompt injection check | Main chain (starts context) |
| 1 | Detailed paper explanation | Isolated sub-agent |
| 2 | Readability and presentation review | Main chain (continues step 0) |
| 3 | Consistency and completeness check | Main chain (continues step 2) |
| 4 | Novelty + live web search for related work | Isolated sub-agent |
| 5 | Conference-style review + revision plan | Main chain (injects step 4 synthesis) |

Steps 1 and 4 run as parallel isolated sub-agents — their long outputs and raw web content never enter the main chain's context.

---

## Setup on Any Machine

### 1. Clone the repo
```bash
git clone https://github.com/kudhru/claude-paper-reviewer.git
cd claude-paper-reviewer
```

### 2. Point your Cowork working folder to `cowork/`
In the Claude desktop app, click the folder icon and select the `cowork/` directory inside the cloned repo.

### 3. Optional: install PDF dependency
```bash
pip install markdown --break-system-packages
```
PDF conversion also works automatically if Google Chrome is installed.

---

## Reviewing Papers

Drop PDFs into `cowork/papers/`, then start a Cowork session and ask:

```
Review the papers in the papers/ folder for ACL 2026.
```
or
```
Review papers/my_paper.pdf for EMNLP 2025.
```

Claude reads `CLAUDE.md` first, follows the exact step order, uses verbatim prompts from `review_prompts.json`, and saves everything via `review_helpers.py`.

---

## Output

```
cowork/reviews/
└── my_paper_20260515_143022/
    ├── 00_prompt_injection_check.md
    ├── 01_paper_explanation.md
    ├── 02_readability_and_presentation.md
    ├── 03_consistency_and_completeness.md
    ├── 04_novelty_and_related_work.md
    ├── 05_conference_review___acl_2026.md
    ├── full_review.md
    ├── full_review.pdf        ← if Chrome or weasyprint available
    └── my_paper.pdf
```

---

## Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Step-by-step instructions Claude follows exactly |
| `review_prompts.json` | Verbatim prompt strings for all 6 steps |
| `review_helpers.py` | Python helpers for file I/O, PDF conversion, state |
| `review_config.json` | Default settings (model, dirs) |
| `papers/` | Drop PDFs here |
| `reviews/` | Output folder (git-ignored) |

---

## Resuming Interrupted Reviews

State is saved after every step. If a review is interrupted, just ask Claude to review the same paper again — it detects the in-progress state and asks whether to resume.

---

## Customising Prompts

Edit `review_prompts.json` to change any prompt text. Changes take effect immediately — no code edits needed.
