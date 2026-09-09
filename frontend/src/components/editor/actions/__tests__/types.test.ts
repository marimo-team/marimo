/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import type { ActionButton } from "../types";
import { flattenActions } from "../types";

const handle = vi.fn();

describe("flattenActions", () => {
  it("does not apply parent search keywords to child actions", () => {
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
        additionalKeywords: ["gcs", "drive"],
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
