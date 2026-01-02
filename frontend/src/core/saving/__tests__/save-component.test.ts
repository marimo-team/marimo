/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { isNamedPersistentFile } from "../save-component";

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
