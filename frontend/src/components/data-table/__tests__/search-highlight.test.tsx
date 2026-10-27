/* Copyright 2026 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  buildHighlightPattern,
  findMatchRanges,
  highlightMatches,
  highlightRanges,
} from "../search-highlight";

function highlight(text: string, query: string) {
  return highlightMatches(text, buildHighlightPattern(query));
}

function marksOf(node: React.ReactNode) {
  const { container } = render(<span>{node}</span>);
  return {
    container,
    marks: [...container.querySelectorAll("mark")].map((m) => m.textContent),
  };
}

describe("buildHighlightPattern", () => {
  it("returns undefined for an empty or missing query", () => {
    expect(buildHighlightPattern("")).toBeUndefined();
    expect(buildHighlightPattern(undefined)).toBeUndefined();
  });

  it("escapes regex metacharacters so the query matches literally", () => {
    const { marks } = marksOf(highlight("a.b a-b (x)", ".b"));
    expect(marks).toEqual([".b"]);
    expect(marksOf(highlight("f(x)", "(x)")).marks).toEqual(["(x)"]);
    expect(marksOf(highlight("C and C++", "c++")).marks).toEqual(["C++"]);
  });
});

describe("highlightMatches", () => {
  it("returns the input unchanged without a pattern", () => {
    expect(highlightMatches("Alice Smith", undefined)).toBe("Alice Smith");
  });

  it("returns the input unchanged when there is no match", () => {
    expect(highlight("Alice Smith", "zzz")).toBe("Alice Smith");
  });

  it("returns the input unchanged when the query is longer than the text", () => {
    expect(highlight("ab", "abc")).toBe("ab");
  });

  it("wraps a single match and keeps the surrounding text", () => {
    const { container, marks } = marksOf(highlight("Alice Smith", "ce S"));
    expect(marks).toEqual(["ce S"]);
    expect(container.textContent).toBe("Alice Smith");
  });

  it("matches case-insensitively and keeps the original casing", () => {
    const { marks } = marksOf(highlight("Alice Smith", "smi"));
    expect(marks).toEqual(["Smi"]);
  });

  it("wraps every occurrence", () => {
    const { container, marks } = marksOf(highlight("a-A-a", "a"));
    expect(marks).toEqual(["a", "A", "a"]);
    expect(container.textContent).toBe("a-A-a");
  });

  it("produces no empty segments for matches at the edges", () => {
    const segments = highlight("xax", "x") as React.ReactNode[];
    expect(Array.isArray(segments)).toBe(true);
    expect(segments).toHaveLength(3);
    expect(segments[1]).toBe("a");
  });

  it("is safe to reuse one global pattern across calls", () => {
    const pattern = buildHighlightPattern("a");
    expect(marksOf(highlightMatches("aa", pattern)).marks).toEqual(["a", "a"]);
    expect(marksOf(highlightMatches("aa", pattern)).marks).toEqual(["a", "a"]);
  });
});

describe("Unicode case folding", () => {
  it("folds the Kelvin sign to k like the backend engines", () => {
    expect(marksOf(highlight("K", "k")).marks).toEqual(["K"]);
  });

  it("folds every Greek sigma form", () => {
    expect(marksOf(highlight("ΟΣ ος οσ", "σ")).marks).toEqual(["Σ", "ς", "σ"]);
  });
});

describe("highlightRanges", () => {
  it("applies shared ranges to a segment at an offset", () => {
    const ranges = findMatchRanges(
      "see https://x",
      buildHighlightPattern("see https"),
    );
    expect(ranges).toEqual([[0, 9]]);
    const { marks: textMarks } = marksOf(highlightRanges("see ", ranges, 0));
    expect(textMarks).toEqual(["see "]);
    const { marks: linkMarks } = marksOf(
      highlightRanges("https://x", ranges, 4),
    );
    expect(linkMarks).toEqual(["https"]);
  });

  it("returns the segment unchanged when no range overlaps it", () => {
    expect(highlightRanges("zzz", [[10, 12]], 0)).toBe("zzz");
  });
});
