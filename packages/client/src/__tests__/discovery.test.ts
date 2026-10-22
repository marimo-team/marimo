/* Copyright 2026 Marimo. All rights reserved. */

import {
  chmod,
  mkdir,
  mkdtemp,
  readdir,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import process from "node:process";
import { promisify } from "node:util";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Client } from "../index.ts";
import { discoverHosts, type DiscoverHostsOptions } from "../node.ts";
import type { HostRecordOutput } from "../protocol.ts";

const runPs = vi.hoisted(() => vi.fn());
vi.mock("node:child_process", () => ({
  execFile: Object.assign(vi.fn(), {
    [Symbol.for("nodejs.util.promisify.custom")]: runPs,
  }),
}));

const record: HostRecordOutput = {
  version: 1,
  name: "marimo",
  url: "http://127.0.0.1:2718/prefix/api/marimo/v1",
  token: "secret",
  process: { pid: 123, started_at: "2026-10-21T12:34:56.123Z" },
};

describe.skipIf(!["darwin", "linux"].includes(process.platform))(
  "discoverHosts",
  () => {
    let stateDir: string;
    let directory: string;

    beforeEach(async () => {
      stateDir = await mkdtemp(join(tmpdir(), "marimo-discovery-"));
      directory = join(stateDir, "hosts-v1");
      await mkdir(directory, { mode: 0o700 });
      runPs.mockReset();
      runPs.mockResolvedValue({
        stdout: "Wed Oct 21 12:34:56 2026 S+\n",
        stderr: "",
      });
    });

    afterEach(async () => {
      vi.restoreAllMocks();
      vi.unstubAllEnvs();
      await rm(stateDir, { recursive: true, force: true });
    });

    const collect = async (options: DiscoverHostsOptions = { stateDir }) => {
      const records = [];
      for await (const host of discoverHosts(options)) records.push(host);
      return records;
    };

    const write = async (value: unknown = record, name = "host.json") => {
      const path = join(directory, name);
      await writeFile(path, JSON.stringify(value), { mode: 0o600 });
      return path;
    };

    it("yields records usable with the existing Client constructor", async () => {
      await write({ ...record, future_field: true });
      await write(
        { ...record, name: "VS Code", url: "http://[::1]:2719/api/marimo/v1" },
        "other.json",
      );
      const records = await collect();
      expect(records).toHaveLength(2);
      expect(records).toContainEqual(record);
      const fetch = vi.fn(
        async (_input: RequestInfo | URL, _init?: RequestInit) =>
          new Response(null, { status: 204 }),
      );
      const host = records.find((host) => host.name === "marimo")!;
      const client = new Client(host.url, { token: host.token, fetch });
      await client.notebook("n1").delete();
      const request = new Request(...fetch.mock.calls[0]);
      expect(request.url).toBe(`${record.url}/notebooks/n1`);
      expect(request.headers.get("Authorization")).toBe("Bearer secret");
      expect(runPs).toHaveBeenCalledWith(
        "/bin/ps",
        ["-p", "123", "-o", "lstart=", "-o", "stat="],
        expect.objectContaining({
          env: expect.objectContaining({ LC_ALL: "C", TZ: "UTC" }),
        }),
      );
    });

    it("uses the same XDG state directory as the host", async () => {
      vi.stubEnv("XDG_STATE_HOME", stateDir);
      directory = join(stateDir, "marimo", "hosts-v1");
      await mkdir(directory, { recursive: true, mode: 0o700 });
      await write();
      expect(await collect({})).toEqual([record]);
    });

    it("finishes when the directory is absent or empty", async () => {
      expect(await collect()).toEqual([]);
      await rm(directory, { recursive: true });
      expect(await collect()).toEqual([]);
      expect(runPs).not.toHaveBeenCalled();
    });

    it("skips malformed and unsupported records, directories, and temporary files", async () => {
      await write();
      await write({ ...record, version: 2 }, "future.json");
      await write({ ...record, token: "" }, "empty-token.json");
      await write(
        { ...record, process: { pid: 1.5, started_at: "invalid" } },
        "invalid.json",
      );
      await write(null, "null.json");
      await write(record, "pending.tmp");
      await mkdir(join(directory, "directory.json"));
      await writeFile(join(directory, "broken.json"), "{", { mode: 0o600 });
      expect(await collect()).toEqual([record]);
      expect(runPs).toHaveBeenCalledTimes(1);
    });

    it.each([
      "https://127.0.0.1/api",
      "http://localhost/api",
      "http://example.com/api",
      "http://127.1/api",
      "http://2130706433/api",
      "http://127.0.0.2/api",
      "http://[0:0:0:0:0:0:0:1]/api",
      "http://127.0.0.1.evil/api",
      "http://user:password@127.0.0.1/api",
      "http://127.0.0.1:99999/api",
      "http://127.0.0.1/api?token=secret",
      "http://127.0.0.1/api#fragment",
      "http://127.0.0.1/\\evil",
      "http://127.0.0.1/api\n",
      "not a URL",
    ])("skips an invalid host URL: %s", async (url) => {
      await write({ ...record, url });
      expect(await collect()).toEqual([]);
      expect(runPs).not.toHaveBeenCalled();
    });

    it.each([0o640, 0o604, 0o620])(
      "skips files with nonprivate mode %o",
      async (mode) => {
        await chmod(await write(), mode);
        expect(await collect()).toEqual([]);
      },
    );

    it("skips nonprivate directories", async () => {
      await write();
      await chmod(directory, 0o755);
      expect(await collect()).toEqual([]);
    });

    it("skips directories belonging to another user", async () => {
      await write();
      vi.spyOn(process, "getuid").mockReturnValue(process.getuid!() + 1);
      expect(await collect()).toEqual([]);
    });

    it("does not follow symlinks to records or the discovery directory", async () => {
      await write(record, "target.tmp");
      await symlink(
        join(directory, "target.tmp"),
        join(directory, "link.json"),
      );
      expect(await collect()).toEqual([]);
      await rm(directory, { recursive: true });
      const target = join(stateDir, "target");
      await mkdir(target, { mode: 0o700 });
      await writeFile(join(target, "host.json"), JSON.stringify(record), {
        mode: 0o600,
      });
      await symlink(target, directory);
      expect(await collect()).toEqual([]);
    });

    it("skips vanished records", async () => {
      await write();
      await write(record, "other.json");
      const hosts = discoverHosts({ stateDir });
      expect((await hosts.next()).value).toEqual(record);
      await rm(join(directory, "host.json"));
      await rm(join(directory, "other.json"));
      expect((await hosts.next()).done).toBe(true);
    });

    it.each([
      "Wed Oct 21 12:34:54 2026 S",
      "Wed Oct 21 12:34:56 2026 Z",
      "",
      "malformed",
    ])("skips stale, zombie, or unverifiable processes: %s", async (output) => {
      await write();
      runPs.mockResolvedValue({ stdout: output, stderr: "" });
      expect(await collect()).toEqual([]);
      expect(await readdir(directory)).toEqual(["host.json"]);
    });

    it("skips processes that have exited", async () => {
      await write();
      runPs.mockRejectedValue(
        Object.assign(new Error("exited"), {
          code: 1,
          stdout: "",
          stderr: "",
        }),
      );
      expect(await collect()).toEqual([]);
    });

    it.each([
      { code: "ENOENT", stdout: "", stderr: "" },
      { code: 1, stdout: "", stderr: "ps: invalid option -- 'p'\n" },
      { code: 1, stdout: "Usage: ps [-o COL1,COL2=HEADER]\n", stderr: "" },
      { code: 2, stdout: "", stderr: "" },
    ])("reports process inspection failures: %j", async (details) => {
      await write();
      const error = Object.assign(new Error("ps failed"), details);
      runPs.mockRejectedValue(error);
      await expect(collect()).rejects.toBe(error);
    });

    it("verifies a real running process", async () => {
      const { execFile } =
        await vi.importActual<typeof import("node:child_process")>(
          "node:child_process",
        );
      const exec = promisify(execFile);
      runPs.mockImplementation(exec);
      // Node's uptime starts after the OS process does. Use the OS start
      // time so that startup overhead cannot exceed the one-second tolerance.
      const { stdout } = await exec(
        "/bin/ps",
        ["-p", String(process.pid), "-o", "lstart="],
        { env: { ...process.env, LC_ALL: "C", TZ: "UTC" } },
      );
      const live = {
        ...record,
        process: {
          pid: process.pid,
          started_at: new Date(`${stdout.trim()} UTC`).toISOString(),
        },
      };
      await write(live);
      expect(await collect()).toEqual([live]);
    });
  },
);
