/* Copyright 2026 Marimo. All rights reserved. */

import {
  type CellErrorEntry,
  formatCellError,
} from "@/core/errors/error-entries";
import type { EnvironmentInfo } from "@/core/network/types";
import { Strings } from "@/utils/strings";

/**
 * Environment information augmented with a client-side collection error, used
 * when the server environment request fails and only partial data is available.
 * Fields are optional because a partial environment only carries what the
 * client could determine without the server.
 */
export type EnvironmentDiagnostics = Partial<EnvironmentInfo> & {
  "Environment Collection Error"?: string;
};

export interface NotebookSource {
  filename: string;
  contents: string;
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
    Locale: locale || undefined,
    Binaries: { Browser: userAgent },
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

/**
 * GitHub returns HTTP 414 for issue-form URLs beyond roughly 8 KB, so prefill is
 * skipped once the encoded body would push the URL past this conservative cap.
 */
export const MAX_PREFILL_URL_LENGTH = 6000;

/**
 * Build a bug-report URL with `fields` prefilled into the issue form, keyed by
 * each field's template `id`. Fields are added greedily in order; any that
 * would push the URL past `MAX_PREFILL_URL_LENGTH` are skipped and returned in
 * `omitted`, so an oversized later field never discards the ones before it.
 */
export function buildBugReportUrl(
  baseUrl: string,
  fields: Record<string, string>,
): { url: string; omitted: string[] } {
  const separator = baseUrl.includes("?") ? "&" : "?";
  const omitted: string[] = [];
  let url = baseUrl;
  let added = 0;

  for (const [key, value] of Object.entries(fields)) {
    if (value.length === 0) {
      continue;
    }
    const param = `${key}=${encodeURIComponent(value)}`;
    const candidate = `${url}${added === 0 ? separator : "&"}${param}`;
    if (candidate.length > MAX_PREFILL_URL_LENGTH) {
      omitted.push(key);
      continue;
    }
    url = candidate;
    added += 1;
  }

  return { url, omitted };
}

function detailsSection(summary: string, body: string): string {
  return [
    "<details>",
    `<summary>${Strings.htmlEscape(summary) ?? ""}</summary>`,
    "",
    body,
    "",
    "</details>",
  ].join("\n");
}

/**
 * Format the environment as a collapsible section for the issue form's
 * `env` field.
 */
export function formatEnvironmentSection(
  environment: EnvironmentDiagnostics,
): string {
  return detailsSection(
    "Environment",
    markdownCodeFence("json", JSON.stringify(environment, null, 2)),
  );
}

/**
 * Format cell errors as a collapsible section for the issue form's
 * `bug-description` field.
 */
export function formatErrorsSection(errors: CellErrorEntry[]): string {
  return detailsSection(
    "Errors",
    markdownCodeFence("text", errors.map(formatCellError).join("\n\n---\n\n")),
  );
}

/**
 * Format notebook source as a collapsible section for the issue form's
 * `reproduction-code` field.
 */
export function formatCodeSection(contents: string): string {
  return detailsSection("Code", markdownCodeFence("python", contents));
}
