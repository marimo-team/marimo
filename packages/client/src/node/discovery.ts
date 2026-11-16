/* Copyright 2026 Marimo. All rights reserved. */

import { execFile } from "node:child_process";
import { constants, type Stats } from "node:fs";
import { lstat, open, readdir } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import process from "node:process";
import { promisify } from "node:util";
import { HostRecord, type HostRecordOutput } from "../protocol.ts";

const exec = promisify(execFile);

export interface DiscoverHostsOptions {
  /** The marimo state directory containing `hosts-v1`. Defaults to
   * `$XDG_STATE_HOME/marimo`, or `~/.local/state/marimo` when unset. */
  stateDir?: string;
}

/**
 * Discover running hosts on this machine with a single scan of their records.
 *
 * Yields records with a private directory and file owned by the current user,
 * a loopback URL, and a matching live process. Invalid, inaccessible, and stale
 * records are skipped without removing them. A missing directory yields nothing.
 * No HTTP requests are made; a host can stop after it has been discovered.
 *
 * Supports macOS and Linux, using `/bin/ps` to verify process start times.
 * Linux requires procps; BusyBox ps is not supported.
 * Throws on unsupported platforms or if process inspection fails.
 */
export async function* discoverHosts(
  options: DiscoverHostsOptions = {},
): AsyncGenerator<HostRecordOutput> {
  if (process.platform !== "darwin" && process.platform !== "linux") {
    throw new Error("discoverHosts() supports macOS and Linux.");
  }
  const stateHome = process.env.XDG_STATE_HOME;
  const directory = join(
    options.stateDir ??
      join(
        stateHome?.trim() ? stateHome : join(homedir(), ".local", "state"),
        "marimo",
      ),
    "hosts-v1",
  );
  const uid = process.getuid!();
  let entries;
  let directoryStat: Stats;
  try {
    directoryStat = await lstat(directory);
    if (!directoryStat.isDirectory() || !isPrivate(directoryStat, uid)) return;
    entries = await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if (isUnavailable(error)) return;
    throw error;
  }

  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith(".json")) continue;
    const record = await readRecord(join(directory, entry.name), uid);
    if (!record) continue;
    // Do not trust records if the directory was replaced during the scan.
    try {
      const current = await lstat(directory);
      if (
        current.dev !== directoryStat.dev ||
        current.ino !== directoryStat.ino ||
        !isPrivate(current, uid)
      )
        return;
    } catch (error) {
      if (isUnavailable(error)) return;
      throw error;
    }
    if (await isRunning(record.process)) yield record;
  }
}

function isPrivate(stat: Stats, uid: number): boolean {
  return stat.uid === uid && (stat.mode & 0o077) === 0;
}

function isUnavailable(error: unknown): boolean {
  return (
    error instanceof Error &&
    "code" in error &&
    ["ENOENT", "ENOTDIR", "EACCES", "EPERM", "ELOOP"].includes(
      String(error.code),
    )
  );
}

async function readRecord(
  path: string,
  uid: number,
): Promise<HostRecordOutput | undefined> {
  try {
    // Check the opened file, and never follow a symlink substituted for it.
    // NONBLOCK also prevents a substituted FIFO from hanging discovery.
    const file = await open(
      path,
      constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK,
    );
    try {
      const stat = await file.stat();
      if (!stat.isFile() || !isPrivate(stat, uid)) return;
      const result = HostRecord.safeParse(
        JSON.parse(await file.readFile("utf8")),
      );
      if (result.success && isLoopback(result.data.url)) return result.data;
    } finally {
      await file.close();
    }
  } catch (error) {
    if (error instanceof SyntaxError || isUnavailable(error)) return;
    throw error;
  }
}

function isLoopback(value: string): boolean {
  // Match the literal authority before URL parsing can normalize other IPv4
  // spellings (e.g. 127.1) or resolve backslashes into a different URL.
  if (!/^http:\/\/(127\.0\.0\.1|\[::1\])(?::[0-9]+)?(?:\/|$)/.test(value)) {
    return false;
  }
  try {
    const url = new URL(value);
    return (
      (url.hostname === "127.0.0.1" || url.hostname === "[::1]") &&
      !url.username &&
      !url.password &&
      !url.search &&
      !url.hash &&
      !/[\\\s?#]/.test(value)
    );
  } catch {
    return false;
  }
}

async function isRunning(
  identity: HostRecordOutput["process"],
): Promise<boolean> {
  let stdout: string;
  try {
    ({ stdout } = await exec(
      "/bin/ps",
      ["-p", String(identity.pid), "-o", "lstart=", "-o", "stat="],
      {
        env: { ...process.env, LC_ALL: "C", TZ: "UTC" },
        timeout: 1000,
        maxBuffer: 4096,
      },
    ));
  } catch (error) {
    // An empty result exits with status 1. Diagnostics indicate an inspection
    // failure (for example, unsupported ps options), not a dead process.
    if (
      error instanceof Error &&
      "code" in error &&
      error.code === 1 &&
      "stdout" in error &&
      error.stdout === "" &&
      "stderr" in error &&
      error.stderr === ""
    ) {
      return false;
    }
    throw error;
  }
  const match = /^(.*?)\s+(\S+)\s*$/.exec(stdout.trim());
  if (!match || /^[ZX]/.test(match[2])) return false;
  // ps reports whole seconds. Match the protocol's subsecond timestamp with
  // the same tolerance as the host conformance suite.
  const started = Date.parse(`${match[1]} UTC`);
  return Math.abs(started - Date.parse(identity.started_at)) < 1000;
}
