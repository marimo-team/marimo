/* Copyright 2026 Marimo. All rights reserved. */

import {
  type CellErrorEntry,
  formatCellError,
} from "@/core/errors/error-entries";
import type { EnvironmentInfo } from "@/core/network/types";
import { Paths } from "@/utils/paths";

/**
 * Environment information augmented with a client-side collection error, used
 * when the server environment request fails and only partial data is available.
 */
export type EnvironmentDiagnostics = EnvironmentInfo & {
  "Environment Collection Error"?: string;
};

export interface NotebookSource {
  filename: string;
  contents: string;
}

export interface IssueDetailsInput {
  environment: EnvironmentDiagnostics;
  errors: CellErrorEntry[];
  notebook?: NotebookSource;
}

/**
 * Replace the server-detected browser with the active browser's user agent.
 *
 * The server cannot know which browser is driving the UI, so diagnostics
 * generated from the modal reflect the live `navigator.userAgent` instead.
 */
export function enrichEnvironment(
  environment: EnvironmentInfo,
  userAgent: string,
): EnvironmentInfo {
  return {
    ...environment,
    Binaries: {
      ...environment.Binaries,
      Browser: userAgent,
    },
  };
}

export function createPartialEnvironment(
  marimoVersion: string,
  userAgent: string,
  locale: string,
  message: string,
): EnvironmentDiagnostics {
  return {
    marimo: marimoVersion,
    editable: false,
    location: "--",
    OS: "--",
    "OS Version": "--",
    Processor: "--",
    "Python Version": "--",
    Locale: locale || "--",
    Binaries: { Browser: userAgent, Node: "--", uv: "--" },
    Dependencies: {},
    "Optional Dependencies": {},
    "Experimental Flags": {},
    "Environment Collection Error": message,
  };
}

/**
 * Wrap `contents` in a Markdown code fence long enough to survive backtick runs
 * inside it, so pasted diagnostics render as a single block on GitHub.
 */
export function markdownCodeFence(language: string, contents: string): string {
  const longest = Math.max(
    2,
    ...Array.from(contents.matchAll(/`+/g), (match) => match[0].length),
  );
  const fence = "`".repeat(longest + 1);
  return `${fence}${language}\n${contents}\n${fence}`;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function detailsSection(summary: string, body: string): string {
  return [
    "<details>",
    `<summary>${escapeHtml(summary)}</summary>`,
    "",
    body,
    "",
    "</details>",
  ].join("\n");
}

export function buildIssueDetails(input: IssueDetailsInput): string {
  const sections = [
    detailsSection(
      "Environment",
      markdownCodeFence("json", JSON.stringify(input.environment, null, 2)),
    ),
  ];

  if (input.errors.length > 0) {
    sections.push(
      detailsSection(
        "Current errors",
        markdownCodeFence(
          "text",
          input.errors.map(formatCellError).join("\n\n---\n\n"),
        ),
      ),
    );
  }

  if (input.notebook) {
    sections.push(
      detailsSection(
        `Notebook source: ${Paths.basename(input.notebook.filename)}`,
        markdownCodeFence("python", input.notebook.contents),
      ),
    );
  }

  return sections.join("\n\n");
}
