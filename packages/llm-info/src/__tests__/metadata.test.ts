/* Copyright 2026 Marimo. All rights reserved. */

import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import nodePath from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { parse, parseDocument } from "yaml";
import { parseCliArgs } from "../cli.ts";
import { ModelsByProviderSchema } from "../generate.ts";
import { ModelLimitsSchema, ReasoningOptionSchema } from "../metadata.ts";
import { mergeModels } from "../sources/merge.ts";
import { parseModelsDev } from "../sources/models-dev.ts";
import { syncModels } from "../sync-models.ts";

const reasoningOptions = [
  { type: "toggle" },
  { type: "effort", values: [null, "default", "none", "low", "high", "max"] },
  { type: "budget_tokens", min: -1, max: 8192 },
];
const upstream = parseModelsDev({
  google: {
    models: {
      model: {
        id: "model",
        name: "Upstream name",
        reasoning: true,
        reasoning_options: reasoningOptions,
        limit: { context: 128000, output: 8192 },
      },
      new: { id: "new", name: "New model", reasoning: false },
    },
  },
  "google-vertex": {
    models: {
      model: {
        id: "model",
        name: "Vertex name",
        reasoning: true,
        reasoning_options: [{ type: "effort", values: ["medium"] }],
        limit: { context: 64000 },
      },
    },
  },
});
const curated = `# Keep this comment
google:
  - name: Curated name
    model: model
    description: Curated description
    roles: [chat, edit]
    capabilities: [thinking]
    input_types: [text]
    output_types: [text]
    release_date: 2026-01-01
    limits: {context: 1000}

azure:
  - name: Same id, different provider
    model: model
    description: Preserve provider differences
    roles: [chat]
    capabilities: []
    input_types: [text]
    output_types: [text]
    release_date: 2026-01-01
`;

describe("model metadata", () => {
  it("retains provider options and limits through parsing, merging, and generation", () => {
    const summary = mergeModels({}, upstream);
    const generated = ModelsByProviderSchema.parse(summary.newEntries);
    expect(
      generated["google"].find((model) => model.model === "model"),
    ).toMatchObject({
      reasoning_options: reasoningOptions,
      limits: { context: 128000, output: 8192 },
    });
    const withoutMetadata = generated["google"].find(
      (model) => model.model === "new",
    )!;
    expect(withoutMetadata).not.toHaveProperty("reasoning_options");
    expect(withoutMetadata).not.toHaveProperty("limits");
  });

  it.each([
    { type: "effort", values: ["unsupported"] },
    { type: "budget_tokens", min: -2 },
    { type: "budget_tokens", max: -1 },
    { type: "budget_tokens", min: 1024, max: 512 },
    { type: "budget_tokens", min: 1.5 },
  ])("rejects invalid reasoning controls: %j", (option) => {
    expect(ReasoningOptionSchema.safeParse(option).success).toBe(false);
  });

  it("preserves zero limits from upstream and rejects negative or fractional limits", () => {
    expect(ModelLimitsSchema.parse({ context: 0, output: 0 })).toEqual({
      context: 0,
      output: 0,
    });
    expect(ModelLimitsSchema.safeParse({ context: -1 }).success).toBe(false);
    expect(ModelLimitsSchema.safeParse({ output: 1.5 }).success).toBe(false);
  });
});

describe("metadata sync", () => {
  let directory: string;
  let path: string;
  beforeEach(() => {
    directory = mkdtempSync(nodePath.join(tmpdir(), "llm-metadata-"));
    path = nodePath.join(directory, "models.yml");
    writeFileSync(path, curated);
  });
  afterEach(() => rmSync(directory, { recursive: true, force: true }));

  it("refreshes existing metadata without adding models or overwriting curation", async () => {
    const result = await syncModels({
      modelsYamlPath: path,
      modelsDev: upstream,
      metadataOnly: true,
    });
    expect(result.added).toBe(0);
    expect(result.updated).toBe(1);
    expect(result.yaml).toContain("# Keep this comment");
    expect(result.yaml).toContain(
      "values: [null, default, none, low, high, max]",
    );
    const before = parse(curated);
    const after = ModelsByProviderSchema.parse(parse(result.yaml));
    const { limits, reasoning_options, ...rest } = after["google"][0];
    const { limits: _oldLimits, ...original } = before.google[0];
    expect(rest).toEqual(original);
    expect(limits).toEqual({ context: 128000, output: 8192 });
    expect(reasoning_options).toEqual(reasoningOptions);
    expect(after["azure"]).toEqual(before.azure);
    const repeated = await syncModels({
      modelsYamlPath: path,
      modelsDev: upstream,
      metadataOnly: true,
    });
    expect(repeated.updated).toBe(0);
    expect(repeated.yaml).toBe(result.yaml);
  });

  it("refreshes metadata during normal sync and writes compact options for new models", async () => {
    const refreshed = await syncModels({
      modelsYamlPath: path,
      modelsDev: upstream,
    });
    expect(refreshed.updated).toBe(1);
    expect(refreshed.added).toBe(1);
    writeFileSync(path, curated.replace("model: model", "model: existing"));
    const result = await syncModels({
      modelsYamlPath: path,
      modelsDev: upstream,
    });
    const data = ModelsByProviderSchema.parse(parse(result.yaml));
    expect(
      data["google"].find((model) => model.model === "model")
        ?.reasoning_options,
    ).toEqual(reasoningOptions);
    expect(result.yaml).toContain(
      "values: [null, default, none, low, high, max]",
    );
  });

  it("preserves metadata when the upstream field is unknown", async () => {
    const missing = parseModelsDev({
      google: { models: { model: { id: "model", name: "Model" } } },
    });
    const result = await syncModels({
      modelsYamlPath: path,
      modelsDev: missing,
      metadataOnly: true,
    });
    expect(result.updated).toBe(0);
    expect(result.yaml).toBe(curated);
  });

  it("preserves a known output limit when upstream only supplies context", async () => {
    writeFileSync(
      path,
      curated.replace(
        "limits: {context: 1000}",
        "limits: {context: 1000, output: 4096}",
      ),
    );
    const partial = parseModelsDev({
      google: {
        models: {
          model: { id: "model", name: "Model", limit: { context: 2000 } },
        },
      },
    });
    const result = await syncModels({
      modelsYamlPath: path,
      modelsDev: partial,
      metadataOnly: true,
    });
    expect(
      ModelsByProviderSchema.parse(parse(result.yaml))["google"][0].limits,
    ).toEqual({ context: 2000, output: 4096 });
  });

  it("refreshes all sourced fields while preserving identity, roles, and partial pricing", async () => {
    writeFileSync(
      path,
      curated.replace(
        "limits: {context: 1000}",
        "limits: {context: 1000, output: 4096}\n    cost: {input: 2, output: 10}\n    reasoning_options:\n      - type: effort\n        values: [high]",
      ),
    );
    const changed = parseModelsDev({
      google: {
        models: {
          model: {
            id: "model",
            name: "Changed upstream name",
            reasoning: false,
            tool_call: true,
            modalities: { input: ["text", "image", "audio"], output: [] },
            release_date: "2026-02",
            cost: { input: 0 },
            limit: { context: 2000 },
          },
        },
      },
    });
    const result = await syncModels({
      modelsYamlPath: path,
      modelsDev: changed,
      metadataOnly: true,
    });
    const model = ModelsByProviderSchema.parse(parse(result.yaml))["google"][0];
    expect(model).toEqual({
      name: "Curated name",
      model: "model",
      description: "Curated description",
      roles: ["chat", "edit"],
      capabilities: ["tool_calling"],
      input_types: ["text", "image"],
      output_types: [],
      release_date: "2026-02-01",
      cost: { input: 0, output: 10 },
      limits: { context: 2000, output: 4096 },
      reasoning_options: [],
    });
    const repeated = await syncModels({
      modelsYamlPath: path,
      modelsDev: changed,
      metadataOnly: true,
    });
    expect(repeated.updated).toBe(0);
    expect(repeated.yaml).toBe(result.yaml);
  });

  it("preserves unknown capability flags, modalities, and invalid release dates", async () => {
    const partial = parseModelsDev({
      google: {
        models: {
          model: {
            id: "model",
            name: "Model",
            tool_call: true,
            release_date: "invalid-date",
            modalities: { output: ["text", "pdf"] },
            cost: {},
          },
        },
      },
    });
    const result = await syncModels({
      modelsYamlPath: path,
      modelsDev: partial,
      metadataOnly: true,
    });
    const model = ModelsByProviderSchema.parse(parse(result.yaml))["google"][0];
    expect(model.capabilities).toEqual(["thinking", "tool_calling"]);
    expect(model.release_date).toBe("2026-01-01");
    expect(model.input_types).toEqual(["text"]);
    expect(model.output_types).toEqual(["text", "pdf"]);
    expect(model).not.toHaveProperty("cost");
  });

  it.each([true, false])(
    "preserves invalid entries and continues syncing (metadataOnly=%s)",
    async (metadataOnly) => {
      const invalid = `  - name: Legacy model
    model: model
    capabilities: [unknown-capability]
    cost: {input: unknown}
`;
      writeFileSync(path, curated.replace("google:\n", `google:\n${invalid}`));
      const result = await syncModels({
        modelsYamlPath: path,
        modelsDev: upstream,
        metadataOnly,
      });
      const models = parse(result.yaml).google;
      expect(
        models.find((model: { name: string }) => model.name === "Legacy model"),
      ).toEqual({
        name: "Legacy model",
        model: "model",
        capabilities: ["unknown-capability"],
        cost: { input: "unknown" },
      });
      expect(
        models.find((model: { name: string }) => model.name === "Curated name")
          .limits,
      ).toEqual({ context: 128000, output: 8192 });
      expect(result.updated).toBe(1);
      expect(result.added).toBe(metadataOnly ? 0 : 1);
    },
  );

  it("preserves comments on refreshed scalar and collection values", async () => {
    const annotated = curated
      .replace(
        "release_date: 2026-01-01",
        "release_date: 2026-01-01 # release note",
      )
      .replace(
        "limits: {context: 1000}",
        "limits: {context: 1000} # limit note",
      );
    const document = parseDocument(annotated);
    const changed = parseModelsDev({
      google: {
        models: {
          model: {
            id: "model",
            name: "Model",
            release_date: "2026-03-01",
            limit: { context: 2000 },
          },
        },
      },
    });
    // A comment between the key and its value belongs to the value node.
    const limits = document.getIn(
      ["google", 0, "limits"],
      true,
    ) as import("yaml").YAMLMap;
    limits.flow = true;
    limits.comment = " limit note";
    limits.commentBefore = " limit rationale";
    writeFileSync(
      path,
      document.toString({ lineWidth: 0, flowCollectionPadding: false }),
    );
    const result = await syncModels({
      modelsYamlPath: path,
      modelsDev: changed,
      metadataOnly: true,
    });
    const refreshed = parseDocument(result.yaml);
    const newLimits = refreshed.getIn(
      ["google", 0, "limits"],
      true,
    ) as import("yaml").YAMLMap;
    const release = refreshed.getIn(
      ["google", 0, "release_date"],
      true,
    ) as import("yaml").Scalar;
    expect(newLimits.comment).toBe(" limit note");
    expect(newLimits.commentBefore).toBe(" limit rationale");
    expect(release.comment).toBe(" release note");
    expect(newLimits.toJSON()).toEqual({ context: 2000 });
    expect(release.value).toBe("2026-03-01");
  });

  it("honors provider filters and dry runs", async () => {
    const filtered = await syncModels({
      modelsYamlPath: path,
      modelsDev: upstream,
      metadataOnly: true,
      providers: ["azure"],
    });
    expect(filtered.updated).toBe(0);
    const dry = await syncModels({
      modelsYamlPath: path,
      modelsDev: upstream,
      metadataOnly: true,
      write: false,
    });
    expect(dry.updated).toBe(1);
    expect(readFileSync(path, "utf8")).toBe(curated);
  });

  it("rejects destructive replacement in metadata-only mode", async () => {
    expect(parseCliArgs(["--metadata-only"]).metadataOnly).toBe(true);
    await expect(
      syncModels({
        modelsYamlPath: path,
        modelsDev: upstream,
        metadataOnly: true,
        mode: "replace",
      }),
    ).rejects.toThrow("cannot replace");
    expect(readFileSync(path, "utf8")).toBe(curated);
  });
});
