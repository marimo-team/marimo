/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it } from "vitest";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import {
  getDefaultExportFilename,
  getDefaultMarkdownExportFilename,
} from "../export-filename";

describe("default export filenames", () => {
  beforeEach(() => {
    store.set(filenameAtom, "folder/my_notebook.py");
  });

  it("derives filenames from the notebook name", () => {
    expect(getDefaultExportFilename("html")).toBe("my_notebook.html");
    expect(getDefaultExportFilename("pdf")).toBe("my_notebook.pdf");
  });

  it("derives markdown filenames from the selected flavor", () => {
    expect(getDefaultMarkdownExportFilename("qmd")).toBe("my_notebook.qmd");
    expect(getDefaultMarkdownExportFilename("mystmd")).toBe(
      "my_notebook.myst.md",
    );
  });

  it("derives script export filenames from the notebook name", () => {
    expect(getDefaultExportFilename("script.py")).toBe("my_notebook.script.py");
  });

  it("falls back to download.* when the notebook is unnamed", () => {
    store.set(filenameAtom, null);
    expect(getDefaultExportFilename("html")).toBe("download.html");
    expect(getDefaultMarkdownExportFilename("qmd")).toBe("download.qmd");
    expect(getDefaultExportFilename("script.py")).toBe("download.script.py");
  });
});
