#!/usr/bin/env bash
# Fail when the stable host protocol differs from a base revision.
#
# Prints the difference and exits 1 when the OpenAPI document that
# packages/host-protocol prints without --experimental has changed. Exits 2
# when the comparison could not run.
set -euo pipefail
trap 'exit 2' ERR

base=${1:?usage: check-stable.sh <base-revision>}
script=packages/host-protocol/scripts/openapi.ts
work=$(mktemp -d)
trap 'git worktree remove --force "$work/base" 2>/dev/null || true; rm -rf "$work"' EXIT

git worktree add --quiet --detach "$work/base" "$base"
if [ ! -f "$work/base/$script" ]; then
  echo "The base revision has no host protocol package, so there is nothing to compare."
  exit 0
fi
(cd "$work/base" && pnpm install --filter @marimo-team/host-protocol --prod --frozen-lockfile --ignore-scripts --silent)

node "$work/base/$script" > "$work/base.json"
node "$script" > "$work/head.json"
if diff -u --label base --label head "$work/base.json" "$work/head.json"; then
  echo "The stable host protocol is unchanged."
else
  exit 1
fi
