/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SentinelCell, WhitespaceMarkers } from "../sentinel-cell";
import type { CellValueSentinel } from "../types";

function renderSentinel(sentinel: CellValueSentinel) {
  const { container } = render(<SentinelCell sentinel={sentinel} />);
  return container.querySelector("span")!;
}

function renderMarkers(value: string) {
  return render(<WhitespaceMarkers value={value} />);
}

describe("SentinelCell", () => {
  it("renders null as None", () => {
    const span = renderSentinel({ type: "null", value: null });
    expect(span.textContent).toBe("None");
    expect(span.getAttribute("aria-label")).toBe("None");
    expect(span.className).toContain("italic");
    expect(span.className).toContain("bg-muted");
  });

  it("renders empty string as <empty>", () => {
    const span = renderSentinel({ type: "empty-string", value: "" });
    expect(span.textContent).toBe("<empty>");
    expect(span.getAttribute("aria-label")).toBe("empty string");
  });

  it("renders single space", () => {
    const span = renderSentinel({ type: "whitespace", value: " " });
    expect(span.textContent).toBe("\u2423");
    expect(span.getAttribute("aria-label")).toBe("1 space");
  });

  it("renders multiple spaces", () => {
    const span = renderSentinel({ type: "whitespace", value: "   " });
    expect(span.textContent).toBe("\u2423\u2423\u2423");
    expect(span.getAttribute("aria-label")).toBe("3 spaces");
  });

  it("renders tab", () => {
    const span = renderSentinel({ type: "whitespace", value: "\t" });
    expect(span.textContent).toBe("\\t");
    expect(span.getAttribute("aria-label")).toBe("1 tab");
  });

  it("renders newline", () => {
    const span = renderSentinel({ type: "whitespace", value: "\n" });
    expect(span.textContent).toBe("\\n");
    expect(span.getAttribute("aria-label")).toBe("1 newline");
  });

  it("renders mixed whitespace", () => {
    const span = renderSentinel({ type: "whitespace", value: "\t \n" });
    expect(span.textContent).toBe("\\t\u2423\\n");
    expect(span.getAttribute("aria-label")).toBe("1 tab, 1 space, 1 newline");
  });

  it("renders NaN", () => {
    const span = renderSentinel({ type: "nan", value: Number.NaN });
    expect(span.textContent).toBe("NaN");
  });

  it("renders inf", () => {
    const span = renderSentinel({ type: "positive-infinity", value: Infinity });
    expect(span.textContent).toBe("inf");
    expect(span.getAttribute("title")).toBe("Infinity");
  });

  it("renders -inf", () => {
    const span = renderSentinel({
      type: "negative-infinity",
      value: -Infinity,
    });
    expect(span.textContent).toBe("-inf");
    expect(span.getAttribute("title")).toBe("-Infinity");
  });

  it("renders NaT", () => {
    const span = renderSentinel({ type: "nat", value: "NaT" });
    expect(span.textContent).toBe("NaT");
    expect(span.getAttribute("title")).toBe("NaT (Not a Time)");
  });
});

describe("WhitespaceMarkers", () => {
  it("renders nothing for empty string", () => {
    const { container } = renderMarkers("");
    expect(container.firstChild).toBeNull();
  });

  it("renders a single space as open box", () => {
    const { container } = renderMarkers(" ");
    const outer = container.querySelector("span")!;
    expect(outer.textContent).toBe("\u2423");
    expect(outer.getAttribute("aria-label")).toBe("1 space");
  });

  it("renders multiple spaces as multiple open boxes", () => {
    const { container } = renderMarkers("   ");
    const outer = container.querySelector("span")!;
    expect(outer.textContent).toBe("\u2423\u2423\u2423");
    expect(outer.getAttribute("aria-label")).toBe("3 spaces");
  });

  it("renders tab, newline, CR with escape labels", () => {
    const { container } = renderMarkers("\t\n\r");
    const outer = container.querySelector("span")!;
    expect(outer.textContent).toBe("\\t\\n\\r");
  });

  it("renders each char in its own span for CSS spacing", () => {
    const { container } = renderMarkers("   ");
    const outer = container.querySelector("span")!;
    // Outer wrapper + three inner spans (one per char)
    expect(outer.querySelectorAll("span")).toHaveLength(3);
  });

  it("renders unknown whitespace (NBSP) as \\uXXXX escape", () => {
    const { container } = renderMarkers("\u00a0");
    const outer = container.querySelector("span")!;
    expect(outer.textContent).toBe("\\u00a0");
  });

  it("renders BOM as \\ufeff", () => {
    const { container } = renderMarkers("\ufeff");
    const outer = container.querySelector("span")!;
    expect(outer.textContent).toBe("\\ufeff");
  });

  it("renders en space and em space as escapes", () => {
    const { container } = renderMarkers("\u2002\u2003");
    const outer = container.querySelector("span")!;
    expect(outer.textContent).toBe("\\u2002\\u2003");
  });

  it("mixes known glyphs and unknown escapes correctly", () => {
    const { container } = renderMarkers(" \t\u00a0");
    const outer = container.querySelector("span")!;
    expect(outer.textContent).toBe("\u2423\\t\\u00a0");
  });

  it("describes mixed whitespace in aria-label", () => {
    const { container } = renderMarkers(" \t\n");
    const outer = container.querySelector("span")!;
    expect(outer.getAttribute("aria-label")).toBe("1 space, 1 tab, 1 newline");
  });
});
