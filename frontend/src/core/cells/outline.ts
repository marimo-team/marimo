/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Table of contents outline.
 */
export interface OutlineItem {
  /**
   * The human-readable heading name.
   */
  name: string;
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
