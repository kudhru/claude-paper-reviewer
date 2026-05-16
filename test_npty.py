#!/usr/bin/env python3
"""
test_npty.py — Test whether Claude runs interactively (subscription billing)
without PTY, by inheriting the parent terminal's stdout.

Run this directly from your terminal:
    python3 test_npty.py
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

SESSIONS_DIR = Path.home() / ".claude" / "sessions"
PROJECTS_DIR = Path.home() / ".claude" / "projects" / Path.cwd().as_posix().replace("/", "-")

prompt = "What is 2+2? Answer in one sentence."
model  = "claude-sonnet-4-6"
cmd    = ["claude", prompt, "--model", model, "--dangerously-skip-permissions"]

print(f"Parent stdout isatty : {os.isatty(sys.stdout.fileno())}")
print(f"Parent stdin  isatty : {os.isatty(sys.stdin.fileno())}")
print(f"Command              : {' '.join(cmd[:2])} ...")
print("-" * 60)

t0 = time.time()

proc = subprocess.Popen(
    cmd,
    stdout=sys.stdout,        # inherit parent terminal — isatty should stay True
    stderr=sys.stderr,
    stdin=subprocess.DEVNULL, # no interactive input
)

print(f"Claude PID: {proc.pid}")
print("Waiting for Claude to exit on its own ...")

try:
    ret = proc.wait(timeout=120)
    elapsed = time.time() - t0
    print(f"\nClaude exited (code={ret}) in {elapsed:.1f}s")
except subprocess.TimeoutExpired:
    print("\nTIMEOUT — Claude did not exit. Killing.")
    proc.kill()

print("-" * 60)

# Check session file
session_file = SESSIONS_DIR / f"{proc.pid}.json"
if session_file.exists():
    with open(session_file) as f:
        d = json.load(f)
    print(f"Session file found   : {session_file.name}")
    print(f"  kind               : {d.get('kind')}")
    print(f"  status             : {d.get('status')}")
    session_id = d.get("sessionId")
    print(f"  sessionId          : {session_id}")

    # Try to read response from JSONL
    jsonl = PROJECTS_DIR / f"{session_id}.jsonl"
    if jsonl.exists():
        print(f"\nJSONL file found     : {jsonl.name}")
        texts = []
        with open(jsonl) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if obj.get("type") == "assistant":
                        for block in obj.get("message", {}).get("content", []):
                            if isinstance(block, dict) and block.get("type") == "text":
                                texts.append(block["text"].strip())
                except json.JSONDecodeError:
                    pass
        if texts:
            print(f"\nResponse from JSONL  :\n  {texts[-1][:300]}")
        else:
            print("No text blocks found in JSONL.")
    else:
        print(f"\nNo JSONL file at     : {jsonl}")
else:
    print(f"No session file at   : {session_file}")
    print("(This means Claude ran non-interactively — no subscription billing)")
