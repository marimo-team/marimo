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
  if (argv.includes("--replace") || argv.includes("-r")) {
    return "replace";
  }
  // Accept both `--mode=replace` and the spaced form `--mode replace`.
  const raw = getFlag(argv, ["--mode"]);
  if (raw === "replace") {
    return "replace";
  }
  if (raw !== undefined && raw !== "append") {
    throw new Error(
      `Unknown --mode value "${raw}" — expected "append" or "replace".`,
    );
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
  const knownList = [...known].sort().join(", ");
  const requested = raw
    .split(",")
    .map((s) => s?.trim())
    .filter((s): s is string => Boolean(s));

  if (requested.length === 0) {
    throw new Error(
      `--provider was given but no value parsed. Known providers: ${knownList}`,
    );
  }

  const valid: string[] = [];
  const invalid: string[] = [];
  for (const id of requested) {
    if (known.has(id)) {
      valid.push(id);
    } else {
      invalid.push(id);
    }
  }
  if (invalid.length > 0) {
    Logger.warn(
      `Unknown provider(s) ignored: ${invalid.join(", ")} — known providers: ${knownList}`,
    );
  }
  // Refuse to proceed with an empty filter — under --replace this would
  // silently wipe `models.yml`. Caller must pass at least one known provider.
  if (valid.length === 0) {
    throw new Error(
      `No known providers in --provider="${raw}". Known providers: ${knownList}`,
    );
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
