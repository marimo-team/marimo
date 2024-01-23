/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Table of contents outline.
 */
export interface OutlineItem {
  name: string;
  id: string;
  level: number;
}

export interface Outline {
  items: OutlineItem[];
}
