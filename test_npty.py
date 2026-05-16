#!/usr/bin/env python3
"""
test_npty.py — Test the no-PTY interactive Claude approach.

Run from a real terminal:
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
print(f"Command              : {' '.join(cmd[:2])} ...")
print("-" * 60)

t0 = time.time()

proc = subprocess.Popen(
    cmd,
    stdout=sys.stdout,
    stderr=sys.stderr,
    stdin=subprocess.DEVNULL,
)

pid = proc.pid
print(f"Claude PID: {pid}")

# Step 1: wait for session file to appear
print("Waiting for session file ...")
session_file = SESSIONS_DIR / f"{pid}.json"
deadline = time.time() + 30
while time.time() < deadline:
    if session_file.exists():
        d = json.loads(session_file.read_text())
        session_id = d.get("sessionId")
        if session_id:
            print(f"Session ID : {session_id}")
            print(f"Kind       : {d.get('kind')}")
            break
    time.sleep(0.3)
else:
    print("ERROR: session file never appeared")
    proc.kill(); proc.wait()
    sys.exit(1)

# Step 2: wait for non-idle (Claude starts processing)
print("Waiting for Claude to start processing ...")
deadline = time.time() + 60
while time.time() < deadline:
    time.sleep(1)
    status = json.loads(session_file.read_text()).get("status")
    if status is not None and status != "idle":
        print(f"Status: {status}")
        break

# Step 3: wait for idle (Claude done)
print("Waiting for Claude to finish ...")
deadline = time.time() + 120
while time.time() < deadline:
    time.sleep(1)
    try:
        status = json.loads(session_file.read_text()).get("status")
    except Exception:
        continue
    if status == "idle":
        print(f"Status: idle — done in {time.time()-t0:.1f}s")
        break
else:
    print("ERROR: timeout waiting for idle")
    proc.kill(); proc.wait()
    sys.exit(1)

time.sleep(2)  # let JSONL flush

# Step 4: read response from JSONL
jsonl = PROJECTS_DIR / f"{session_id}.jsonl"
texts = []
if jsonl.exists():
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
            if obj.get("type") == "assistant":
                for block in obj.get("message", {}).get("content", []):
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block["text"].strip())
        except json.JSONDecodeError:
            pass

# Step 5: kill Claude and restore terminal
proc.kill()
proc.wait()
os.system("stty sane")
print("\nClaude process killed.")

print("-" * 60)
if texts:
    print(f"Response from JSONL:\n  {texts[-1][:300]}")
else:
    print("No text response found in JSONL.")
