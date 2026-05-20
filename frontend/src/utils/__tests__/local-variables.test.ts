/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  containsMangledLocal,
  splitMangledLocals,
  unmangleLocal,
} from "../local-variables";

describe("unmangleLocal", () => {
  it("extracts the cell id and original name", () => {
    expect(unmangleLocal("_cell_Hbol_a")).toEqual({
      cellId: "Hbol",
      name: "_a",
    });
  });

  it("handles names with multiple underscore segments", () => {
    expect(unmangleLocal("_cell_Hbol_a_b")).toEqual({
      cellId: "Hbol",
      name: "_a_b",
    });
  });

  it("returns null for non-mangled strings", () => {
    expect(unmangleLocal("just_a_variable")).toBeNull();
    expect(unmangleLocal("_private")).toBeNull();
    expect(unmangleLocal("_cell_Hbol_")).toBeNull();
  });

  it("does not match marimo cell file paths", () => {
    // The compiled cell file is `__marimo__cell_<id>_.py` (two leading
    // underscores, trailing `_` with no name); it must not be confused with a
    // mangled local.
    expect(unmangleLocal("__marimo__cell_Hbol_.py")).toBeNull();
    expect(
      unmangleLocal("/tmp/marimo_42/__marimo__cell_Hbol_.py"),
    ).toBeNull();
  });
});

describe("splitMangledLocals", () => {
  it("returns a single text segment when nothing matches", () => {
    expect(splitMangledLocals("plain text")).toEqual(["plain text"]);
  });

  it("splits a NameError message", () => {
    expect(
      splitMangledLocals("name '_cell_Hbol_a' is not defined"),
    ).toEqual([
      "name '",
      { cellId: "Hbol", name: "_a" },
      "' is not defined",
    ]);
  });

  it("handles multiple mangled names in one string", () => {
    expect(
      splitMangledLocals("_cell_AAAA_x and _cell_BBBB_y"),
    ).toEqual([
      { cellId: "AAAA", name: "_x" },
      " and ",
      { cellId: "BBBB", name: "_y" },
    ]);
  });

  it("leaves the cell file path alone", () => {
    const path = "/tmp/marimo_42/__marimo__cell_Hbol_.py";
    expect(splitMangledLocals(path)).toEqual([path]);
  });
});

describe("containsMangledLocal", () => {
  it("detects mangled names", () => {
    expect(containsMangledLocal("name '_cell_Hbol_a' is not defined")).toBe(
      true,
    );
  });

  it("ignores the cell file path", () => {
    expect(
      containsMangledLocal("/tmp/marimo_42/__marimo__cell_Hbol_.py"),
    ).toBe(false);
  });
});
