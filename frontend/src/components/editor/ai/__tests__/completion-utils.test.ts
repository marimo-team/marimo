/* Copyright 2024 Marimo. All rights reserved. */
import { describe, beforeEach, it, expect, vi, type Mock } from "vitest";
import { getAICompletionBody } from "../completion-utils";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { datasetsAtom } from "@/core/datasets/state";
import { store } from "@/core/state/jotai";
import type { DatasetsState } from "@/core/datasets/types";

// Mock getCodes function
vi.mock("@/core/codemirror/copilot/getCodes", () => ({
  getCodes: vi.fn(),
}));

describe("getAICompletionBody", () => {
  beforeEach(() => {
    // Reset the Jotai store before each test
    store.set(datasetsAtom, {
      tables: [],
    } as unknown as DatasetsState);
    (getCodes as Mock).mockReturnValue("// Some other code");
  });

  it("should return the correct completion body with mentioned datasets", () => {
    // Set up test data in the Jotai store
    const testDatasets = [
      {
        name: "dataset1",
        columns: [
          { name: "col1", type: "number" },
          { name: "col2", type: "string" },
        ],
      },
      {
        name: "dataset2",
        columns: [
          { name: "col3", type: "boolean" },
          { name: "col4", type: "date" },
        ],
      },
    ];
    store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const input = "Use @dataset1 and @dataset2 for analysis";
    const result = getAICompletionBody(input);

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [
          {
            name: "dataset1",
            columns: [
              { name: "col1", type: "number" },
              { name: "col2", type: "string" },
            ],
          },
          {
            name: "dataset2",
            columns: [
              { name: "col3", type: "boolean" },
              { name: "col4", type: "date" },
            ],
          },
        ],
      },
    });
  });

  it("should handle input with no mentioned datasets", () => {
    const input = "Perform some analysis without mentioning datasets";
    const result = getAICompletionBody(input);

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [],
      },
    });
  });

  it("should handle input with non-existent datasets", () => {
    // Set up test data in the Jotai store
    const testDatasets = [
      {
        name: "existingDataset",
        columns: [
          { name: "col1", type: "number" },
          { name: "col2", type: "string" },
        ],
      },
    ];
    store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const input = "Use @existingDataset and @nonExistentDataset for analysis";
    const result = getAICompletionBody(input);

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [
          {
            name: "existingDataset",
            columns: [
              { name: "col1", type: "number" },
              { name: "col2", type: "string" },
            ],
          },
        ],
      },
    });
  });

  it("should handle dataset names with dots", () => {
    // Set up test data in the Jotai store
    const testDatasets = [
      {
        name: "dataset.with.dots",
        columns: [
          { name: "col1", type: "number" },
          { name: "col2", type: "string" },
        ],
      },
      {
        name: "regular_dataset",
        columns: [{ name: "col3", type: "boolean" }],
      },
    ];
    store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const input = "Use @dataset.with.dots and @regular_dataset for analysis";
    const result = getAICompletionBody(input);

    expect(result).toEqual({
      includeOtherCode: "// Some other code",
      context: {
        schema: [
          {
            name: "dataset.with.dots",
            columns: [
              { name: "col1", type: "number" },
              { name: "col2", type: "string" },
            ],
          },
          {
            name: "regular_dataset",
            columns: [{ name: "col3", type: "boolean" }],
          },
        ],
      },
    });
  });
});
