/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  canCollapseOutline,
  findCollapseRange,
  mergeOutlines,
  parseOutline,
} from "../outline";
import type { Outline } from "@/core/cells/outline";

describe("parseOutline", () => {
  it("can parse html outline", () => {
    const html = `
    <span class="markdown">
      <h1 id="welcome-to-marimo">Welcome to marimo! 🌊🍃</h1>
      <h2 id="what-is-marimo">What is <b>marimo</b>?</h2>
      <span class="paragraph">marimo is a Python library for creating reactive and interactive notebooks</span>
      <h2 id="how-do-i-use-marimo">How do I use marimo?</h2>
      <span class="paragraph">pip install marimo</span>
    </span>
    `;
    const outline = parseOutline({
      mimetype: "text/html",
      timestamp: 0,
      channel: "output",
      data: html,
    });
    expect(outline).toMatchInlineSnapshot(`
      {
        "items": [
          {
            "by": {
              "id": "welcome-to-marimo",
            },
            "level": 1,
            "name": "Welcome to marimo! 🌊🍃",
          },
          {
            "by": {
              "id": "what-is-marimo",
            },
            "level": 2,
            "name": "What is marimo?",
          },
          {
            "by": {
              "id": "how-do-i-use-marimo",
            },
            "level": 2,
            "name": "How do I use marimo?",
          },
        ],
      }
    `);
  });

  it("can parse html outline with duplicate nested headings", () => {
    const html = `
    <span class="markdown">
      <h1 id="experiment-1">Experiment 1</h1>
      <h2 id="setup">Setup</h2>
      <h2 id="instructions">Instructions</h2>
      <h1 id="experiment-2">Experiment 2</h1>
      <h2 id="setup">Setup</h2>
      <h2 id="instructions">Instructions</h2>
      <h1 id="ack">Acknowledgements</h1>
      <h3 id="marimo">marimo</h1>
    </span>
    `;
    const outline = parseOutline({
      mimetype: "text/html",
      timestamp: 0,
      channel: "output",
      data: html,
    });
    expect(outline).toMatchInlineSnapshot(`
      {
        "items": [
          {
            "by": {
              "id": "experiment-1",
            },
            "level": 1,
            "name": "Experiment 1",
          },
          {
            "by": {
              "id": "setup",
            },
            "level": 2,
            "name": "Setup",
          },
          {
            "by": {
              "id": "instructions",
            },
            "level": 2,
            "name": "Instructions",
          },
          {
            "by": {
              "id": "experiment-2",
            },
            "level": 1,
            "name": "Experiment 2",
          },
          {
            "by": {
              "id": "setup",
            },
            "level": 2,
            "name": "Setup",
          },
          {
            "by": {
              "id": "instructions",
            },
            "level": 2,
            "name": "Instructions",
          },
          {
            "by": {
              "id": "ack",
            },
            "level": 1,
            "name": "Acknowledgements",
          },
          {
            "by": {
              "id": "marimo",
            },
            "level": 3,
            "name": "marimo",
          },
        ],
      }
    `);
  });

  it("can handle non-html outline", () => {
    const html = "foo";
    const outline = parseOutline({
      mimetype: "text/plain",
      timestamp: 0,
      channel: "output",
      data: html,
    });
    expect(outline).toEqual(null);
  });

  it("can handle empty/null outline", () => {
    expect(parseOutline(null)).toEqual(null);
    expect(parseOutline(undefined!)).toEqual(null);

    const html = "";
    expect(
      parseOutline({
        mimetype: "text/html",
        timestamp: 0,
        channel: "output",
        data: html,
      }),
    ).toEqual({ items: [] });
  });

  it("can handle invalid outline", () => {
    const html = "<h1>foo</h1><h2>bar</h2><h3>baz</h3>";
    const outline = parseOutline({
      mimetype: "text/html",
      timestamp: 0,
      channel: "output",
      data: html,
    });
    expect(outline).toMatchInlineSnapshot(`
      {
        "items": [
          {
            "by": {
              "path": "//H1[contains(., "foo")]",
            },
            "level": 1,
            "name": "foo",
          },
          {
            "by": {
              "path": "//H2[contains(., "bar")]",
            },
            "level": 2,
            "name": "bar",
          },
          {
            "by": {
              "path": "//H3[contains(., "baz")]",
            },
            "level": 3,
            "name": "baz",
          },
        ],
      }
    `);
  });
});

const OUTLINE_1: Outline = {
  items: [
    {
      name: "h1",
      level: 1,
      by: { id: "h1" },
    },
    {
      name: "h2",
      level: 2,
      by: { id: "h2" },
    },
    {
      name: "h3",
      level: 3,
      by: { id: "h3" },
    },
  ],
};

const OUTLINE_2: Outline = {
  items: [
    {
      name: "other-h1",
      level: 1,
      by: { path: "other-h1" },
    },
    {
      name: "other-h2",
      level: 2,
      by: { path: "other-h2" },
    },
  ],
};

it("mergeOutlines", () => {
  expect(
    mergeOutlines([OUTLINE_1, null, OUTLINE_2, null]),
  ).toMatchInlineSnapshot(`
    {
      "items": [
        {
          "by": {
            "id": "h1",
          },
          "level": 1,
          "name": "h1",
        },
        {
          "by": {
            "id": "h2",
          },
          "level": 2,
          "name": "h2",
        },
        {
          "by": {
            "id": "h3",
          },
          "level": 3,
          "name": "h3",
        },
        {
          "by": {
            "path": "other-h1",
          },
          "level": 1,
          "name": "other-h1",
        },
        {
          "by": {
            "path": "other-h2",
          },
          "level": 2,
          "name": "other-h2",
        },
      ],
    }
  `);
});

it("canCollapseOutline", () => {
  expect(canCollapseOutline(null)).toBe(false);
  expect(canCollapseOutline(OUTLINE_1)).toBe(true);
  expect(canCollapseOutline(OUTLINE_2)).toBe(true);
  expect(canCollapseOutline({ items: [] })).toBe(false);
  expect(
    canCollapseOutline({
      items: [
        {
          name: "h3",
          level: 3,
          by: { id: "h3" },
        },
      ],
    }),
  ).toBe(false);
});

describe("findCollapseRange", () => {
  const makeOutline = (levels: number[]) => {
    return {
      items: levels.map((level) => ({
        name: `h${level}`,
        level,
        by: { id: `h${level}` },
      })),
    };
  };

  it("can collapse range", () => {
    expect(findCollapseRange(0, [makeOutline([1, 2, 3, 4])])).toEqual([0, 0]);
  });

  it("can collapse range with gaps", () => {
    const outlines = [
      makeOutline([1, 2, 3, 4]),
      makeOutline([2, 3, 4]),
      null,
      makeOutline([2]),
      makeOutline([1]),
      makeOutline([2]),
    ];
    expect(findCollapseRange(0, outlines)).toEqual([0, 3]);
    expect(findCollapseRange(1, outlines)).toEqual([1, 2]);
    expect(findCollapseRange(4, outlines)).toEqual([4, 5]);
    expect(findCollapseRange(5, outlines)).toEqual([5, 5]);
    // bad ranges
    expect(findCollapseRange(10, outlines)).toEqual(null);
    expect(findCollapseRange(2, outlines)).toEqual(null);
  });
});
