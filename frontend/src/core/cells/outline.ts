/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Table of contents outline.
 */
export interface OutlineItem {
  /**
   * The human-readable heading name (plain text).
   */
  name: string;
  /**
   * The heading's inner HTML, preserving rich content like LaTeX.
   * When present and different from `name`, the outline should
   * render this instead of the plain-text `name`.
   */
  html?: string;
  /**
   * Locator of the item.
   *
   * If `id` is provided, the item is located by #id.
   *
   * If `path` is provided, the item is located by xpath.
   */
  by: { id: string } | { path: string };
  /**
   * The level of the item.
   * h1 -> 1
   * h2 -> 2
   * etc.
   */
  level: number;
}

export interface Outline {
  items: OutlineItem[];
}
