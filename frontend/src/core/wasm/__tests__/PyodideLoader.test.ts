/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { shouldShowSpinner } from "../PyodideLoader";

describe("shouldShowSpinner", () => {
  it("shows the spinner when there are no cells yet (Pyodide hasn't parsed)", () => {
    expect(
      shouldShowSpinner({
        hasCells: false,
        hasOutput: false,
        mode: "read",
        codeHidden: false,
      }),
    ).toBe(true);

    expect(
      shouldShowSpinner({
        hasCells: false,
        hasOutput: true,
        mode: "edit",
        codeHidden: false,
      }),
    ).toBe(true);
  });

  it("renders children once cells exist with code visible", () => {
    // run mode, code visible, no outputs yet — the user can read the code
    expect(
      shouldShowSpinner({
        hasCells: true,
        hasOutput: false,
        mode: "read",
        codeHidden: false,
      }),
    ).toBe(false);
  });

  it("renders children once cells exist with cached outputs (snapshot case)", () => {
    expect(
      shouldShowSpinner({
        hasCells: true,
        hasOutput: true,
        mode: "read",
        codeHidden: true,
      }),
    ).toBe(false);
  });

  it("keeps the spinner up in headless run mode with no outputs", () => {
    // read mode + code hidden + no outputs = nothing visible to render
    expect(
      shouldShowSpinner({
        hasCells: true,
        hasOutput: false,
        mode: "read",
        codeHidden: true,
      }),
    ).toBe(true);
  });

  it("never blocks edit mode once cells exist", () => {
    expect(
      shouldShowSpinner({
        hasCells: true,
        hasOutput: false,
        mode: "edit",
        codeHidden: true,
      }),
    ).toBe(false);
  });
});
