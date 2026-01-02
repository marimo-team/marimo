/* Copyright 2026 Marimo. All rights reserved. */

import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import type { Outline, OutlineItem } from "../cells/outline";
import type { OutputMessage } from "../kernel/messages";

// Tags that we don't want to include in the outline
const excludedTags = ["marimo-carousel", "marimo-tabs", "marimo-accordion"];

// We go up to h6. Previously we did h3 to match Google Docs and Notion, but users have requested more levels.
// This could be made configurable in the future.
const HEADER_TAGS = "h1, h2, h3, h4, h5, h6";

/**
 * Extracts a table of contents {@link Outline} from an HTML string.
 *
 * Each {@link OutlineItem} corresponds to a heading (h1–h6) found in the input.
 *
 * @param html - The HTML content to parse.
 * @returns An {@link Outline}, otherwise `null` if parsing via isn't supported in JS runtime (e.g., Node).
 */
function getOutline(html: string): Outline | null {
  // Some JS runtimes (e.g. Node.js for the VSCode extension) do not
  // expose DOMParser globally. In those environments parsing isn't
  // possible (without a polyfill), so return just return `null`.
  if (typeof DOMParser === "undefined") {
    return null;
  }

  const items: Outline["items"] = [];
  const parser = new DOMParser();
  const document = parser.parseFromString(html, "text/html");

  const headings = document.querySelectorAll(HEADER_TAGS);
  // eslint-disable-next-line unicorn/prefer-spread
  for (const heading of Array.from(headings)) {
    const name = heading.textContent;
    // Check if the heading is within any of the excluded tags
    if (excludedTags.some((tag) => heading.closest(tag))) {
      continue;
    }

    if (!name) {
      continue;
    }

    const level = Number.parseInt(heading.tagName[1], 10);
    items.push({ name, level, by: headingToIdentifier(heading) });
  }

  return { items };
}

export function headingToIdentifier(heading: Element): OutlineItem["by"] {
  const id = heading.id;
  if (id) {
    return { id };
  }
  const name = heading.textContent;
  return { path: `//${heading.tagName}[contains(., "${name}")]` };
}

export function mergeOutlines(outlines: (Outline | null)[]): Outline {
  return {
    items: outlines.filter(Boolean).flatMap((outline) => outline.items),
  };
}

export function parseOutline(output: OutputMessage | null): Outline | null {
  if (output == null) {
    return null;
  }

  if (output.mimetype !== "text/html" && output.mimetype !== "text/markdown") {
    return null;
  }

  if (output.data == null) {
    return null;
  }

  try {
    invariant(typeof output.data === "string", "expected string");
    return getOutline(output.data);
  } catch {
    Logger.error("Failed to parse outline");
    return null;
  }
}

/**
 * We can only collapse if it has an H1 or H2
 */
export function canCollapseOutline(outline: Outline | null): boolean {
  if (outline == null) {
    return false;
  }
  // Only can collapse if has items with a level 1 or 2 or 3
  return outline.items.some((item) => item.level <= 3);
}

/**
 * Find the range of cells to collapse in the outline
 * given the start index.
 *
 * End index is inclusive
 */
export function findCollapseRange(
  startIndex: number,
  outlines: (Outline | null)[],
): [number, number] | null {
  // Higher header is the lowest value
  const getHighestHeader = (outline: Outline) => {
    if (outline.items.length === 0) {
      return 7; // default to imaginary H7
    }
    return Math.min(...outline.items.map((item) => item.level));
  };

  // Get the start max heading
  const startOutline = outlines[startIndex];
  if (startOutline == null || startOutline.items.length === 0) {
    Logger.warn("Failed to find a starting outline");
    return null;
  }
  // Higher header has the lowest value
  const highestHeader = getHighestHeader(startOutline);

  // Find the next index where an equal or higher header (lower number) is found
  let endIndex = startIndex + 1;
  while (endIndex < outlines.length) {
    const outline = outlines[endIndex];
    if (outline && getHighestHeader(outline) <= highestHeader) {
      return [startIndex, endIndex - 1];
    }
    endIndex++;
  }

  return [startIndex, outlines.length - 1];
}
