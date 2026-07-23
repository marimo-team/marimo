/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellErrorEntry } from "@/core/errors/error-entries";
import type { EnvironmentInfo } from "@/core/network/types";
import {
  buildBugReportUrl,
  createPartialEnvironment,
  enrichEnvironment,
  formatCodeSection,
  formatEnvironmentSection,
  formatErrorsSection,
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

describe("formatEnvironmentSection", () => {
  it("wraps the environment JSON in a collapsible section", () => {
    const markdown = formatEnvironmentSection(environment);
    expect(markdown).toContain("<summary>Environment</summary>");
    expect(markdown).toContain('"marimo": "1.2.3"');
  });
});

describe("formatErrorsSection", () => {
  it("wraps errors in a collapsible section without cell source", () => {
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
    const markdown = formatErrorsSection(errors);
    expect(markdown).toContain("<summary>Errors</summary>");
    expect(markdown).toContain("```text\n");
    expect(markdown).toContain("ValueError: bad value");
    expect(markdown).not.toContain("password");
  });
});

describe("formatCodeSection", () => {
  it("wraps the code in a collapsible python section", () => {
    const markdown = formatCodeSection("import marimo");
    expect(markdown).toContain("<summary>Code</summary>");
    expect(markdown).toContain("```python\nimport marimo");
  });
});

describe("buildBugReportUrl", () => {
  const baseUrl =
    "https://github.com/marimo-team/marimo/issues/new?template=bug_report.yaml";

  it("prefills each field keyed by its template id", () => {
    const { url, omitted } = buildBugReportUrl(baseUrl, {
      env: "hello world",
      "bug-description": "boom",
    });
    expect(url).toBe(`${baseUrl}&env=hello%20world&bug-description=boom`);
    expect(omitted).toEqual([]);
  });

  it("appends fields with a query separator when the base URL has none", () => {
    const { url } = buildBugReportUrl("https://example.com/new", { env: "x" });
    expect(url).toBe("https://example.com/new?env=x");
  });

  it("skips empty fields", () => {
    const { url } = buildBugReportUrl(baseUrl, {
      env: "x",
      "bug-description": "",
    });
    expect(url).toBe(`${baseUrl}&env=x`);
    expect(url).not.toContain("bug-description");
  });

  it("returns the base URL when no fields have content", () => {
    const { url } = buildBugReportUrl(baseUrl, { env: "" });
    expect(url).toBe(baseUrl);
  });

  it("encodes markdown so it survives as a single query param", () => {
    const details = formatEnvironmentSection(environment);
    const { url } = buildBugReportUrl(baseUrl, { env: details });
    expect(url).toContain("&env=");
    expect(new URL(url).searchParams.get("env")).toBe(details);
  });

  it("keeps earlier fields and omits only the oversized later one", () => {
    const huge = "x".repeat(MAX_PREFILL_URL_LENGTH);
    const { url, omitted } = buildBugReportUrl(baseUrl, {
      env: "small",
      "reproduction-code": huge,
    });
    expect(url).toBe(`${baseUrl}&env=small`);
    expect(omitted).toEqual(["reproduction-code"]);
  });
});
