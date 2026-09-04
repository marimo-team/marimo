/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import type { ActionButton } from "../types";
import { flattenActions } from "../types";

const handle = vi.fn();

describe("flattenActions", () => {
  it("inherits and deduplicates parent search keywords", () => {
    const actions: ActionButton[] = [
      {
        label: "Add remote storage",
        handle,
        additionalKeywords: ["s3", "gcs"],
        dropdown: [
          {
            label: "Browse all connections",
            handle,
            additionalKeywords: ["gcs", "drive"],
          },
        ],
      },
    ];

    expect(flattenActions(actions)).toEqual([
      expect.objectContaining({
        label: "Add remote storage > Browse all connections",
        additionalKeywords: ["s3", "gcs", "drive"],
      }),
    ]);
  });

  it("does not add an empty keyword array", () => {
    const actions: ActionButton[] = [{ label: "Run", handle }];

    expect(flattenActions(actions)).toEqual([
      expect.objectContaining({
        label: "Run",
        additionalKeywords: undefined,
      }),
    ]);
  });
});
