/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { EDGE_CASE_FILENAMES } from "../../../__tests__/mocks";
import { Paths } from "../../../utils/paths";

describe("filename handling logic", () => {
  it.each(
    EDGE_CASE_FILENAMES,
  )("should extract basename correctly for document title: %s", (filename) => {
    const basename = Paths.basename(filename);
    expect(basename).toBe(filename); // Since no path separator
  });

  it("should handle full paths with unicode filenames", () => {
    EDGE_CASE_FILENAMES.forEach((filename) => {
      const fullPath = `/path/to/${filename}`;

      const basename = Paths.basename(fullPath);
      expect(basename).toBe(filename);
    });
  });

  it("should handle document title setting with unicode", () => {
    EDGE_CASE_FILENAMES.forEach((filename) => {
      const originalTitle = document.title;

      // In case this does any conversions, we want to simulate reading/writing the title
      document.title = filename;
      expect(document.title).toBe(filename);

      // Restore
      document.title = originalTitle;
    });
  });
});
