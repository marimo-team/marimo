/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellErrorEntry } from "@/core/errors/error-entries";
import type { EnvironmentInfo } from "@/core/network/types";
import {
  buildBugReportUrl,
  buildIssueDetails,
  createPartialEnvironment,
  enrichEnvironment,
  markdownCodeFence,
  MAX_PREFILL_URL_LENGTH,
} from "../issue-details";

const environment: EnvironmentInfo = {
  marimo: "1.2.3",
  editable: false,
  location: "~/.venv/site-packages/marimo",
  OS: "Darwin",
  "OS Version": "25.0",
  Processor: "arm",
  "Python Version": "3.12.9",
  Locale: "en_US",
  Binaries: { Browser: "chrome 140", Node: "v22", uv: "0.11" },
  Dependencies: { click: "8.4.2" },
  "Optional Dependencies": { pandas: "3.0.0" },
  "Experimental Flags": {},
};

describe("enrichEnvironment", () => {
  it("replaces server Chrome detection with the active browser", () => {
    const result = enrichEnvironment(environment, "Firefox/140");
    expect(result.Binaries.Browser).toBe("Firefox/140");
    expect(result.Binaries.Node).toBe("v22");
  });

  it("does not mutate the input", () => {
    enrichEnvironment(environment, "Firefox/140");
    expect(environment.Binaries.Browser).toBe("chrome 140");
  });
});

describe("createPartialEnvironment", () => {
  it("records the collection error and keeps the active browser", () => {
    const partial = createPartialEnvironment(
      "1.2.3",
      "Firefox/140",
      "en_US",
      "Server environment information unavailable",
    );
    expect(partial.marimo).toBe("1.2.3");
    expect(partial.Binaries?.Browser).toBe("Firefox/140");
    expect(partial.Locale).toBe("en_US");
    expect(partial["Environment Collection Error"]).toBe(
      "Server environment information unavailable",
    );
  });

  it("omits empty fields rather than filling placeholders", () => {
    const partial = createPartialEnvironment(
      "1.2.3",
      "Firefox/140",
      "",
      "boom",
    );
    expect(partial.Locale).toBeUndefined();
    expect(partial.location).toBeUndefined();
    expect(partial.OS).toBeUndefined();
    expect(partial.Dependencies).toBeUndefined();
  });
});

describe("markdownCodeFence", () => {
  it("uses a fence longer than any backtick run in the content", () => {
    const block = markdownCodeFence("python", 'text = "```"');
    expect(block.startsWith("````python\n")).toBe(true);
    expect(block.endsWith("\n````")).toBe(true);
    expect(block).toContain('text = "```"');
  });

  it("uses a minimum fence of three backticks", () => {
    const block = markdownCodeFence("json", "{}");
    expect(block.startsWith("```json\n")).toBe(true);
    expect(block.endsWith("\n```")).toBe(true);
  });
});

describe("buildIssueDetails", () => {
  it("includes the environment and omits notebook source unless provided", () => {
    const markdown = buildIssueDetails({
      environment,
      errors: [],
      notebook: undefined,
    });
    expect(markdown).toContain("<summary>Environment</summary>");
    expect(markdown).toContain('"marimo": "1.2.3"');
    expect(markdown).not.toContain("Notebook source");
    expect(markdown).not.toContain("Current errors");
  });

  it("includes current errors as plain text without notebook source", () => {
    const errors: CellErrorEntry[] = [
      {
        cellId: cellId("cell-1"),
        cellName: "Cell 1",
        cellCode: "password = 'private'",
        errorData: [],
        tracebackHtml:
          '<span class="gr">ValueError</span>: <span class="n">bad value</span>',
      },
    ];
    const markdown = buildIssueDetails({ environment, errors });
    expect(markdown).toContain("<summary>Current errors</summary>");
    expect(markdown).toContain("ValueError: bad value");
    expect(markdown).not.toContain("password");
  });

  it("includes notebook source under its basename when provided", () => {
    const markdown = buildIssueDetails({
      environment,
      errors: [],
      notebook: {
        filename: "/project/example.py",
        contents: "x = 1",
      },
    });
    expect(markdown).toContain(
      "<summary>Notebook source: example.py</summary>",
    );
    expect(markdown).toContain("x = 1");
  });

  it("escapes the summary label as text", () => {
    const markdown = buildIssueDetails({
      environment,
      errors: [],
      notebook: {
        filename: "/project/<script>.py",
        contents: "x = 1",
      },
    });
    expect(markdown).toContain("&lt;script&gt;.py");
    expect(markdown).not.toContain("<script>.py");
  });
});

describe("buildBugReportUrl", () => {
  const baseUrl =
    "https://github.com/marimo-team/marimo/issues/new?template=bug_report.yaml";

  it("prefills the env field with the encoded issue details", () => {
    const url = buildBugReportUrl(baseUrl, "hello world");
    expect(url).toBe(`${baseUrl}&env=hello%20world`);
  });

  it("appends env with a query separator when the base URL has none", () => {
    const url = buildBugReportUrl("https://example.com/new", "x");
    expect(url).toBe("https://example.com/new?env=x");
  });

  it("encodes markdown so it survives as a single query param", () => {
    const details = buildIssueDetails({ environment, errors: [] });
    const url = buildBugReportUrl(baseUrl, details);
    expect(url).toContain("&env=");
    expect(new URL(url).searchParams.get("env")).toBe(details);
  });

  it("falls back to the plain base URL when the prefill exceeds the cap", () => {
    const huge = "x".repeat(MAX_PREFILL_URL_LENGTH);
    expect(buildBugReportUrl(baseUrl, huge)).toBe(baseUrl);
  });
});
