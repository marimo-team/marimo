/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { EDGE_CASE_FILENAMES } from "../../__tests__/mocks";
import { Filenames } from "../filenames";

describe("Filenames", () => {
  it("should convert filename to markdown", () => {
    expect(Filenames.toMarkdown("test")).toEqual("test.md");
    expect(Filenames.toMarkdown("test.txt")).toEqual("test.md");
    expect(Filenames.toMarkdown("test.foo.py")).toEqual("test.foo.md");
  });

  it("should convert filename to HTML", () => {
    expect(Filenames.toHTML("test")).toEqual("test.html");
    expect(Filenames.toHTML("test.txt")).toEqual("test.html");
    expect(Filenames.toHTML("test.foo.py")).toEqual("test.foo.html");
  });

  it("should convert filename to PNG", () => {
    expect(Filenames.toPNG("test")).toEqual("test.png");
    expect(Filenames.toPNG("test.txt")).toEqual("test.png");
    expect(Filenames.toPNG("test.foo.py")).toEqual("test.foo.png");
  });

  it("should remove extension from filename", () => {
    expect(Filenames.withoutExtension("test")).toEqual("test");
    expect(Filenames.withoutExtension("test.txt")).toEqual("test");
    expect(Filenames.withoutExtension("test.foo.txt")).toEqual("test.foo");
  });

  it.each(
    EDGE_CASE_FILENAMES,
  )("should handle edge case filenames: %s", (filename) => {
    // Test all filename operations with edge cases
    const withoutExt = Filenames.withoutExtension(filename);

    expect(Filenames.toMarkdown(filename)).toEqual(`${withoutExt}.md`);
    expect(Filenames.toHTML(filename)).toEqual(`${withoutExt}.html`);
    expect(Filenames.toPNG(filename)).toEqual(`${withoutExt}.png`);
    expect(Filenames.toPY(filename)).toEqual(`${withoutExt}.py`);

    // Ensure operations preserve unicode and special characters in base name
    expect(withoutExt).not.toEqual("");
    expect(typeof withoutExt).toBe("string");
  });
});
