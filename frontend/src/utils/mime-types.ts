/* Copyright 2026 Marimo. All rights reserved. */

import type { MimeType } from "@/components/editor/Output";
import { once } from "./once";

/**
 * Configuration for mime type precedence and filtering.
 * Uses Map/Set for O(1) lookups at runtime.
 */
export interface MimeTypeConfig {
  /**
   * Pre-computed precedence map: mime type -> sort index.
   * Lower index = higher priority. Types not in the map are placed at the end.
   */
  precedence: ReadonlyMap<MimeType, number>;

  /**
   * Hiding rules: trigger mime type -> set of mime types to hide.
   * When the key mime type is present, all mime types in the value set are hidden.
   */
  hidingRules: ReadonlyMap<MimeType, ReadonlySet<MimeType>>;
}

/**
 * Result of processing mime types through the filtering and sorting pipeline.
 */
export interface ProcessedMimeTypes<T> {
  /** The filtered and sorted mime entries */
  entries: Array<[MimeType, T]>;
  /** Mime types that were hidden by rules */
  hidden: MimeType[];
}

/**
 * Creates a compiled MimeTypeConfig from readable arrays.
 *
 * @example
 * ```ts
 * const config = createMimeConfig({
 *   precedence: ["text/html", "image/png", "text/plain"],
 *   hidingRules: {
 *     "text/html": ["image/png", "image/jpeg"],
 *   },
 * });
 * ```
 */
export function createMimeConfig(input: {
  precedence: MimeType[];
  hidingRules: Record<string, MimeType[]>;
}): MimeTypeConfig {
  const precedence = new Map<MimeType, number>();
  for (let i = 0; i < input.precedence.length; i++) {
    precedence.set(input.precedence[i], i);
  }

  const hidingRules = new Map<MimeType, ReadonlySet<MimeType>>();
  for (const [trigger, toHide] of Object.entries(input.hidingRules)) {
    hidingRules.set(trigger as MimeType, new Set(toHide));
  }

  return { precedence, hidingRules };
}

/**
 * Default configuration for mime type handling.
 * Lazily compiled on first access.
 *
 * Design rationale:
 * - text/html typically contains rich rendered output and should take precedence
 * - When text/html is present, image fallbacks (png, jpeg, etc.) are often redundant
 *   static renders and should be hidden to reduce UI clutter
 * - text/markdown should NOT be hidden by text/html as they serve different purposes
 * - Vega charts should remain visible as they provide interactivity
 */
export const getDefaultMimeConfig = once((): MimeTypeConfig => {
  const IMAGE_FALLBACKS: MimeType[] = ["image/png", "image/jpeg", "image/gif"];

  return createMimeConfig({
    precedence: [
      "text/html",
      "application/vnd.vegalite.v6+json",
      "application/vnd.vegalite.v5+json",
      "application/vnd.vega.v6+json",
      "application/vnd.vega.v5+json",
      "image/svg+xml",
      "image/png",
      "image/jpeg",
      "image/gif",
      "text/markdown",
      "text/latex",
      "text/csv",
      "application/json",
      "text/plain",
      "video/mp4",
      "video/mpeg",
    ],
    hidingRules: {
      // When HTML is present, hide static image fallbacks
      "text/html": [
        ...IMAGE_FALLBACKS,
        "image/avif",
        "image/bmp",
        "image/tiff",
      ],
      // When Vega charts are present, hide image fallbacks
      "application/vnd.vegalite.v6+json": IMAGE_FALLBACKS,
      "application/vnd.vegalite.v5+json": IMAGE_FALLBACKS,
      "application/vnd.vega.v6+json": IMAGE_FALLBACKS,
      "application/vnd.vega.v5+json": IMAGE_FALLBACKS,
    },
  });
});

/**
 * Filters mime types based on hiding rules.
 */
export function applyHidingRules(
  mimeTypes: ReadonlySet<MimeType>,
  rules: ReadonlyMap<MimeType, ReadonlySet<MimeType>>,
): { visible: Set<MimeType>; hidden: Set<MimeType> } {
  const hidden = new Set<MimeType>();

  for (const mime of mimeTypes) {
    const toHide = rules.get(mime);
    if (toHide) {
      for (const hideType of toHide) {
        if (mimeTypes.has(hideType)) {
          hidden.add(hideType);
        }
      }
    }
  }

  const visible = new Set<MimeType>();
  for (const mime of mimeTypes) {
    if (!hidden.has(mime)) {
      visible.add(mime);
    }
  }

  return { visible, hidden };
}

/**
 * Sorts mime entries according to a precedence map.
 * Mime types not in the map are placed at the end, preserving their original order.
 */
export function sortByPrecedence<T>(
  entries: Array<[MimeType, T]>,
  precedence: ReadonlyMap<MimeType, number>,
): Array<[MimeType, T]> {
  const unknownPrecedence = precedence.size;

  return [...entries].sort((a, b) => {
    const indexA = precedence.get(a[0]) ?? unknownPrecedence;
    const indexB = precedence.get(b[0]) ?? unknownPrecedence;
    return indexA - indexB;
  });
}

/**
 * Main entry point: processes mime entries by applying hiding rules and sorting.
 */
export function processMimeBundle<T>(
  entries: Array<[MimeType, T]>,
  config: MimeTypeConfig = getDefaultMimeConfig(),
): ProcessedMimeTypes<T> {
  if (entries.length === 0) {
    return { entries: [], hidden: [] };
  }

  const mimeTypes = new Set(entries.map(([mime]) => mime));
  const { visible, hidden } = applyHidingRules(mimeTypes, config.hidingRules);
  const filteredEntries = entries.filter(([mime]) => visible.has(mime));
  const sortedEntries = sortByPrecedence(filteredEntries, config.precedence);

  return {
    entries: sortedEntries,
    hidden: Array.from(hidden),
  };
}
