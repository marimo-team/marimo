/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Table of contents outline.
 */
export interface OutlineItem {
  name: string;
  by:
    | {
        id: string;
      }
    | {
        path: string;
      };
  level: number;
}

export interface Outline {
  items: OutlineItem[];
}
