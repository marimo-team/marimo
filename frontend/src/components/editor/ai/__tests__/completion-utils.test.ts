/* Copyright 2026 Marimo. All rights reserved. */
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  type Mock,
  vi,
} from "vitest";
import { variableName } from "@/__tests__/branded";
import * as aiContext from "@/core/ai/context/context";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { dataSourceConnectionsAtom } from "@/core/datasets/data-source-connections";
import { DUCKDB_ENGINE } from "@/core/datasets/engines";
import { datasetsAtom } from "@/core/datasets/state";
import type { DatasetsState } from "@/core/datasets/types";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import type { FileUIPart, UIMessage } from "ai";
import {
  getAICompletionBody,
  getAICompletionBodyWithAttachments,
  isContextAttachment,
  MARIMO_CONTEXT_PART_TYPE,
  resolveChatContext,
} from "../completion-utils";

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
    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map(),
    });
    store.set(variablesAtom, {});
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

    const input = "Use @data://dataset1 and @data://dataset2 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="dataset1" source="unknown">Columns:
        col1 (number)
        col2 (string)</data>

      <data name="dataset2" source="unknown">Columns:
        col3 (boolean)
        col4 (date)</data>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
  });

  it("should handle input with no mentioned datasets", () => {
    const input = "Perform some analysis without mentioning @data://datasets";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
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

    const input =
      "Use @data://existingDataset and @data://nonExistentDataset for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="existingDataset" source="unknown">Columns:
        col1 (number)
        col2 (string)</data>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
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

    const input =
      "Use @data://dataset.with.dots and @data://regular_dataset for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="dataset.with.dots" source="unknown">Columns:
        col1 (number)
        col2 (string)</data>

      <data name="regular_dataset" source="unknown">Columns:
        col3 (boolean)</data>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
  });

  it("should handle connections", () => {
    // Set up test data in the Jotai store
    const testConnection = {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_schema: "default_schema",
      databases: [
        {
          name: "db1",
          schemas: [
            {
              name: "default_schema",
              tables: [
                { name: "table1", columns: [{ name: "col1", type: "number" }] },
                { name: "table2", columns: [] },
              ],
            },
            {
              name: "other_schema",
              tables: [{ name: "table3", columns: [] }],
            },
          ],
        },
      ],
    };
    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map().set(DUCKDB_ENGINE, testConnection),
    });

    const input = "Use @data://table1 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="table1" source="unknown">Columns:
        col1 (number)</data>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
  });

  it("should return the correct completion body with mentioned variables", () => {
    // Set up test data in the Jotai store
    const testVariables = {
      [variableName("var1")]: {
        name: variableName("var1"),
        value: "string value",
        dataType: "string",
        declaredBy: [],
        usedBy: [],
      },
      [variableName("var2")]: {
        name: variableName("var2"),
        value: "42",
        dataType: "number",
        declaredBy: [],
        usedBy: [],
      },
    };
    store.set(variablesAtom, testVariables);

    const input = "Use @variable://var1 and @variable://var2 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<variable name="var1" dataType="string">"string value"</variable>

      <variable name="var2" dataType="number">"42"</variable>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
  });

  it("should handle input with both datasets and variables", () => {
    // Set up test data in the Jotai store
    const testDatasets = [
      {
        name: "dataset1",
        columns: [
          { name: "col1", type: "number" },
          { name: "col2", type: "string" },
        ],
      },
    ];
    store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const testVariables = {
      [variableName("var1")]: {
        name: variableName("var1"),
        value: "string value",
        dataType: "string",
        declaredBy: [],
        usedBy: [],
      },
    };
    store.set(variablesAtom, testVariables);

    const input = "Use @data://dataset1 and @variable://var1 for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="dataset1" source="unknown">Columns:
        col1 (number)
        col2 (string)</data>

      <variable name="var1" dataType="string">"string value"</variable>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
  });

  it("should handle non-existent variables", () => {
    // Set up test data in the Jotai store
    const testVariables = {
      [variableName("existingVar")]: {
        name: variableName("existingVar"),
        value: "string value",
        dataType: "string",
        declaredBy: [],
        usedBy: [],
      },
    };
    store.set(variablesAtom, testVariables);

    const input =
      "Use @variable://existingVar and @variable://nonExistentVar for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<variable name="existingVar" dataType="string">"string value"</variable>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
  });

  it("should prioritize datasets over variables when there's a name conflict", () => {
    // Set up test data in the Jotai store with a name conflict
    const testDatasets = [
      {
        name: "conflict",
        columns: [{ name: "col1", type: "number" }],
      },
    ];
    store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    const testVariables = {
      [variableName("conflict")]: {
        name: variableName("conflict"),
        value: "string value",
        dataType: "string",
        declaredBy: [],
        usedBy: [],
      },
    };
    store.set(variablesAtom, testVariables);

    const input = "Use @data://conflict for analysis";
    const result = getAICompletionBody({ input });

    expect(result).toMatchInlineSnapshot(`
      {
        "context": {
          "plainText": "<data name="conflict" source="unknown">Columns:
        col1 (number)</data>",
          "schema": [],
          "variables": [],
        },
        "includeOtherCode": "// Some other code",
      }
    `);
  });
});

describe("resolveChatContext", () => {
  beforeEach(() => {
    store.set(datasetsAtom, {
      tables: [],
    } as unknown as DatasetsState);
    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map(),
    });
    store.set(variablesAtom, {});
  });

  it("returns no context when the input has no @-mentions", async () => {
    const result = await resolveChatContext("just a plain question");
    expect(result).toEqual({ contextPart: null, attachments: [] });
  });

  it("returns no context part when @-mentions resolve to nothing", async () => {
    const result = await resolveChatContext("look at @variable://ghost");
    expect(result.contextPart).toBeNull();
    expect(result.attachments).toEqual([]);
  });

  it("captures resolved @-context into a data part", async () => {
    store.set(variablesAtom, {
      [variableName("var1")]: {
        name: variableName("var1"),
        value: "string value",
        dataType: "string",
        declaredBy: [],
        usedBy: [],
      },
    });

    const result = await resolveChatContext("inspect @variable://var1");

    expect(result.contextPart?.type).toBe(MARIMO_CONTEXT_PART_TYPE);
    expect(result.contextPart?.data.contextIds).toEqual(["variable://var1"]);
    expect(result.contextPart?.data.plainText).toMatchInlineSnapshot(
      `"<variable name="var1" dataType="string">"string value"</variable>"`,
    );
  });
});

describe("isContextAttachment", () => {
  type Part = UIMessage["parts"][number];

  it("is true for a file part tagged as context", () => {
    const part = {
      type: "file",
      mediaType: "image/png",
      url: "data:image/png;base64,abc",
      providerMetadata: { marimo: { source: "context" } },
    } as Part;
    expect(isContextAttachment(part)).toBe(true);
  });

  it("is false for a user-uploaded file part (no marker)", () => {
    const part = {
      type: "file",
      mediaType: "image/png",
      url: "data:image/png;base64,abc",
    } as Part;
    expect(isContextAttachment(part)).toBe(false);
  });

  it("is false for a file part with unrelated provider metadata", () => {
    const part = {
      type: "file",
      mediaType: "image/png",
      url: "data:image/png;base64,abc",
      providerMetadata: { openai: { foo: "bar" } },
    } as Part;
    expect(isContextAttachment(part)).toBe(false);
  });

  it("is false for non-file parts", () => {
    expect(isContextAttachment({ type: "text", text: "hi" } as Part)).toBe(
      false,
    );
  });
});

describe("context attachment stamping", () => {
  const rawAttachment: FileUIPart = {
    type: "file",
    mediaType: "image/png",
    url: "data:image/png;base64,abc",
  };

  beforeEach(() => {
    vi.spyOn(aiContext, "getAIContextRegistry").mockReturnValue({
      parseAllContextIds: () => ["data://t1"],
      formatContextForAI: () => '<data name="t1" />',
      getAttachmentsForContext: async () => [rawAttachment],
    } as unknown as ReturnType<typeof aiContext.getAIContextRegistry>);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("stamps chat attachments as context-derived", async () => {
    const { attachments } = await resolveChatContext("see @data://t1");
    expect(attachments).toHaveLength(1);
    expect(isContextAttachment(attachments[0])).toBe(true);
    // The original attachment is left untouched (we return a stamped copy).
    expect(rawAttachment.providerMetadata).toBeUndefined();
  });

  it("stamps completion attachments the same way as chat", async () => {
    const { attachments } = await getAICompletionBodyWithAttachments({
      input: "see @data://t1",
    });
    expect(attachments).toHaveLength(1);
    expect(isContextAttachment(attachments[0])).toBe(true);
  });
});
