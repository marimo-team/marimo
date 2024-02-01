/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { parseOutline } from "../outline";

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
            "id": "welcome-to-marimo",
            "level": 1,
            "name": "Welcome to marimo! 🌊🍃",
          },
          {
            "id": "what-is-marimo",
            "level": 2,
            "name": "What is marimo?",
          },
          {
            "id": "how-do-i-use-marimo",
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
            "id": "experiment-1",
            "level": 1,
            "name": "Experiment 1",
          },
          {
            "id": "setup",
            "level": 2,
            "name": "Setup",
          },
          {
            "id": "instructions",
            "level": 2,
            "name": "Instructions",
          },
          {
            "id": "experiment-2",
            "level": 1,
            "name": "Experiment 2",
          },
          {
            "id": "setup",
            "level": 2,
            "name": "Setup",
          },
          {
            "id": "instructions",
            "level": 2,
            "name": "Instructions",
          },
          {
            "id": "ack",
            "level": 1,
            "name": "Acknowledgements",
          },
          {
            "id": "marimo",
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
    expect(outline).toEqual({ items: [] });
  });
});
