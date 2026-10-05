/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { enqueueNotebookSave, isNamedPersistentFile } from "../save-component";

describe("isNamedPersistentFile", () => {
  it.each([
    [null, false],
    // Temp paths should return false
    ["/tmp/notebook.py", false],
    ["/var/folders/ab/cd/T/notebook.py", false],
    ["C:\\Users\\user\\AppData\\Local\\Temp\\notebook.py", false],
    // /tmp_mnt is a mount point, not a temp directory (bug fix)
    ["/tmp_mnt/notebook.py", true],
    // Normal paths should return true
    ["/home/user/project/notebook.py", true],
  ])("isNamedPersistentFile(%s) => %s", (filename, expected) => {
    expect(isNamedPersistentFile(filename)).toBe(expected);
  });
});

describe("enqueueNotebookSave", () => {
  it("serializes snapshots across callers and continues after a failure", async () => {
    const firstStarted = new Deferred<void>();
    const releaseFirst = new Deferred<void>();
    const snapshots: string[] = [];
    let current = "first";

    const first = enqueueNotebookSave(async () => {
      snapshots.push(current);
      firstStarted.resolve();
      await releaseFirst.promise;
      throw new Error("save failed");
    });
    await firstStarted.promise;

    current = "queued";
    const second = enqueueNotebookSave(async () => {
      snapshots.push(current);
    });
    current = "latest";

    expect(snapshots).toEqual(["first"]);
    releaseFirst.resolve();
    await expect(first).rejects.toThrow("save failed");
    await second;
    expect(snapshots).toEqual(["first", "latest"]);
  });
});
