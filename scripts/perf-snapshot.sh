#!/usr/bin/env bash
# Capture current frontend performance metrics and print a markdown table
# for pasting into a PR description. Informational only — never gates.
set -euo pipefail

cd "$(dirname "$0")/../frontend"

if [ ! -d ../marimo/_static ]; then
  echo "Warning: marimo/_static is not built. Run 'make fe' first." >&2
fi

OUTPUT=$(pnpm playwright test perf-measure.spec.ts --reporter=line 2>&1 || true)

RESULT=$(printf '%s\n' "$OUTPUT" | sed -n '/^PERF_RESULT /,/^}$/p' | sed '1s/^PERF_RESULT //')

if [ -z "$RESULT" ]; then
  echo "No PERF_RESULT found. Full output:" >&2
  printf '%s\n' "$OUTPUT" >&2
  exit 1
fi

python3 - "$RESULT" << 'EOF'
import json
import re
import sys

data = json.loads(sys.argv[1])

vitals = {}
for line in data.get("vitals", []):
    match = re.search(r"\[Metric (\w+)\] ([\d.]+)", line)
    if match:
        vitals[match.group(1)] = match.group(2)

rows = [
    ("Load time (100-cell notebook)", f"{data['loadMs']} ms"),
    ("Load scripting", f"{data['loadScriptingMs']} ms"),
    ("Load layout", f"{data['loadLayoutMs']} ms"),
    ("Scroll task time", f"{data['scrollTaskMs']} ms"),
    ("DOM nodes (100-cell notebook)", str(data["domCount"])),
    ("Main JS bundle", f"{data['chunkBytes'] / 1024 / 1024:.1f} MB"),
    ("LCP", f"{vitals.get('LCP', 'n/a')} ms"),
    ("INP", f"{vitals.get('INP', 'n/a')} ms"),
]

print("## Performance Snapshot")
print()
print("| Metric | Value |")
print("|---|---|")
for label, value in rows:
    print(f"| {label} | {value} |")
EOF
