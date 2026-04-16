/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SentinelCell } from "../sentinel-cell";
import type { CellValueSentinel } from "../types";

function renderSentinel(sentinel: CellValueSentinel) {
  const { container } = render(<SentinelCell sentinel={sentinel} />);
  return container.querySelector("span")!;
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
    expect(span.textContent).toBe("\u2192");
    expect(span.getAttribute("aria-label")).toBe("1 tab");
  });

  it("renders newline", () => {
    const span = renderSentinel({ type: "whitespace", value: "\n" });
    expect(span.textContent).toBe("\u21B5");
    expect(span.getAttribute("aria-label")).toBe("1 newline");
  });

  it("renders mixed whitespace", () => {
    const span = renderSentinel({ type: "whitespace", value: "\t \n" });
    expect(span.textContent).toBe("\u2192\u2423\u21B5");
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
});
