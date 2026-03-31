/* Copyright 2026 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as htmlUtils from "@/core/dom/htmlUtils";
import { store } from "@/core/state/jotai";
import { getLSPDocument, getLSPDocumentRootUri } from "../utils";

describe("utils", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Unix paths", () => {
    it("should calculate correct absolute paths when notebook is in root", () => {
      vi.spyOn(store, "get").mockReturnValue("/user/marimo/project");
      vi.spyOn(htmlUtils, "getFilenameFromDOM").mockReturnValue("notebook.py");

      expect(getLSPDocument()).toBe("file:///user/marimo/project/notebook.py");
      expect(getLSPDocumentRootUri()).toBe("file:///user/marimo/project");
    });

    it("should calculate correct absolute paths when notebook is in a subdirectory", () => {
      vi.spyOn(store, "get").mockReturnValue("/user/marimo/project/notebooks");
      vi.spyOn(htmlUtils, "getFilenameFromDOM").mockReturnValue(
        "notebooks/analysis.py",
      );

      expect(getLSPDocument()).toBe(
        "file:///user/marimo/project/notebooks/analysis.py",
      );
      expect(getLSPDocumentRootUri()).toBe("file:///user/marimo/project");
    });

    it("should calculate correct absolute paths when notebook is in a nested subdirectory", () => {
      vi.spyOn(store, "get").mockReturnValue(
        "/user/marimo/project/notebooks/subdir",
      );
      vi.spyOn(htmlUtils, "getFilenameFromDOM").mockReturnValue(
        "notebooks/subdir/analysis.py",
      );

      expect(getLSPDocument()).toBe(
        "file:///user/marimo/project/notebooks/subdir/analysis.py",
      );
      expect(getLSPDocumentRootUri()).toBe("file:///user/marimo/project");
    });
  });

  describe("Windows paths", () => {
    it("should calculate correct absolute paths with backslashes", () => {
      vi.spyOn(store, "get").mockReturnValue(
        "C:\\Users\\marimo\\project\\notebooks\\subdir",
      );
      vi.spyOn(htmlUtils, "getFilenameFromDOM").mockReturnValue(
        "notebooks\\subdir\\app.py",
      );

      expect(getLSPDocument()).toBe(
        "file:///C:/Users/marimo/project/notebooks/subdir/app.py",
      );
      expect(getLSPDocumentRootUri()).toBe("file:///C:/Users/marimo/project");
    });
  });

  describe("Fallback behavior", () => {
    it("should fallback to relative path if cwd is missing", () => {
      vi.spyOn(store, "get").mockReturnValue(null);
      vi.spyOn(htmlUtils, "getFilenameFromDOM").mockReturnValue("notebook.py");

      expect(getLSPDocument()).toBe("file://notebook.py");
      expect(getLSPDocumentRootUri()).toBe("file://.");
    });

    it("should fallback to default filename if both are missing", () => {
      vi.spyOn(store, "get").mockReturnValue(null);
      vi.spyOn(htmlUtils, "getFilenameFromDOM").mockReturnValue(null);

      expect(getLSPDocument()).toBe("file:///__marimo_notebook__.py");
      expect(getLSPDocumentRootUri()).toBe("file:///");
    });
  });
});
