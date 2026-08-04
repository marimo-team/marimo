/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { parseOutline } from "@/core/dom/outline";
import { findOutlineElements } from "../useActiveOutline";

describe("findOutlineElements", () => {
  it.each([
    "Design from the portfolio",
    'Decorative Art of "Spanish California"',
    `The painter's "Study"`,
  ])("finds an id-less heading named %s", (name) => {
    const html = `<h3>${name}</h3>`;
    document.body.innerHTML = html;

    const outline = parseOutline({
      mimetype: "text/html",
      timestamp: 0,
      channel: "output",
      data: html,
    });

    expect(
      findOutlineElements(outline?.items ?? []).map(([element]) => element),
    ).toEqual([document.querySelector("h3")]);
  });
});
