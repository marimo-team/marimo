/* Copyright 2026 Marimo. All rights reserved. */

import { Logger } from "./simple_logger.ts";
import { PROVIDER_MAP } from "./sources/merge.ts";
import type { SyncMode } from "./sync-models.ts";

export interface CliArgs {
  mode: SyncMode;
  maxPerProvider?: number;
  providers?: string[];
}

/** Read `--name=value`, `--name value`, or any alias of those, from argv. */
function getFlag(
  argv: readonly string[],
  names: readonly string[],
): string | undefined {
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    for (const name of names) {
      if (arg.startsWith(`${name}=`)) {
        return arg.slice(name.length + 1);
      }
      if (arg === name && i + 1 < argv.length) {
        return argv[i + 1];
      }
    }
  }
  return undefined;
}

function parseMode(argv: readonly string[]): SyncMode {
  if (
    argv.includes("--replace") ||
    argv.includes("--mode=replace") ||
    argv.includes("-r")
  ) {
    return "replace";
  }
  return "append";
}

function parseMaxPerProvider(argv: readonly string[]): number | undefined {
  const raw = getFlag(argv, ["--max-per-provider", "--max", "-n"]);
  if (raw === undefined) {
    return undefined;
  }
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : undefined;
}

function parseProviders(argv: readonly string[]): string[] | undefined {
  const raw = getFlag(argv, ["--provider", "--providers", "-p"]);
  if (raw === undefined) {
    return undefined;
  }
  const known: ReadonlySet<string> = new Set(Object.values(PROVIDER_MAP));
  const requested = raw
    .split(",")
    .map((s) => s?.trim())
    .filter((s): s is string => Boolean(s));

  const valid: string[] = [];
  for (const id of requested) {
    if (known.has(id)) {
      valid.push(id);
    } else {
      Logger.warn(
        `Unknown provider "${id}" — known providers: ${[...known].sort().join(", ")}`,
      );
    }
  }
  return valid;
}

export function parseCliArgs(argv: readonly string[]): CliArgs {
  return {
    mode: parseMode(argv),
    maxPerProvider: parseMaxPerProvider(argv),
    providers: parseProviders(argv),
  };
}
