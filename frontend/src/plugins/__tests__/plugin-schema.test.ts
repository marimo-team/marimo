/* Copyright 2026 Marimo. All rights reserved. */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { parse, stringify } from "yaml";
import { z } from "zod";
import { LAYOUT_PLUGINS, UI_PLUGINS } from "../plugins";
import {
  buildPluginSpec,
  type BuildPluginSpecOptions,
  type PluginContract,
  type PluginOpenAPIDocument,
} from "./plugin-schema";

const SCHEMA_PATH = resolve(process.cwd(), "plugins.openapi.yaml");
const REGENERATE_COMMAND =
  "pnpm --filter @marimo-team/frontend plugins:generate-schema";

// Keep this aggregation test-only: production initialization consumes the two
// registries directly and should not allocate or import schema-generation code.
const ALL_PLUGINS = [...UI_PLUGINS, ...LAYOUT_PLUGINS];

const livePluginOverrides: BuildPluginSpecOptions = {
  unrepresentableSchemaOverride: ({ componentName, path, type }) => {
    const pathText = path.map(String).join(".");

    // These validators accept values that JSON cannot encode directly. Their
    // explicit wire representations live here to avoid adding schema metadata
    // or allocations to production plugin initialization.
    if (
      componentName === "marimo-anywidget.data" &&
      type === "custom" &&
      pathText.includes("modelId")
    ) {
      return { type: "string", minLength: 1 };
    }
    if (
      (componentName === "marimo-table.get_column_summaries.output" ||
        componentName === "marimo-table.preview_column.output") &&
      type === "nan"
    ) {
      return { type: "number" };
    }
    if (
      componentName === "marimo-table.get_column_summaries.output" &&
      type === "custom" &&
      (pathText.includes("bin_start") || pathText.includes("bin_end"))
    ) {
      return { type: "string", format: "date-time" };
    }
    return undefined;
  },
};

const document = buildPluginSpec(ALL_PLUGINS, livePluginOverrides);

if (process.env.UPDATE_PLUGIN_SCHEMA) {
  writeFileSync(
    SCHEMA_PATH,
    stringify(document, { aliasDuplicateObjects: false }),
  );
  process.stdout.write(`Updated ${SCHEMA_PATH}\n`);
}

function plugin(tagName: string, validator: z.ZodType): PluginContract {
  return { tagName, validator };
}

function contractRefs(
  doc: PluginOpenAPIDocument,
  path: string,
): { read: string; write: string } {
  const contract = doc.paths[path] as {
    get: {
      responses: {
        "200": {
          content: { "application/json": { schema: { $ref: string } } };
        };
      };
    };
    put: {
      requestBody: {
        content: { "application/json": { schema: { $ref: string } } };
      };
    };
  };
  return {
    read: contract.get.responses["200"].content["application/json"].schema.$ref,
    write: contract.put.requestBody.content["application/json"].schema.$ref,
  };
}

describe("frontend/plugins.openapi.yaml", () => {
  it(`is in sync with the registered plugin schemas (run \`${REGENERATE_COMMAND}\` to update)`, () => {
    if (!existsSync(SCHEMA_PATH)) {
      throw new Error(
        `Missing generated plugin schema at ${SCHEMA_PATH}. Run \`${REGENERATE_COMMAND}\` and commit the result.`,
      );
    }
    const committed = parse(readFileSync(SCHEMA_PATH, "utf8"));
    expect(
      committed,
      `The committed plugin schema is stale. Run \`${REGENERATE_COMMAND}\` and commit frontend/plugins.openapi.yaml.`,
    ).toEqual(document);
  });

  it("contains every plugin data and RPC schema", () => {
    const expectedContracts = ALL_PLUGINS.reduce(
      (count, registeredPlugin) =>
        count +
        1 +
        2 *
          Object.keys(
            "functions" in registeredPlugin
              ? (registeredPlugin.functions ?? {})
              : {},
          ).length,
      0,
    );
    expect(
      Object.keys(document.components.schemas).length,
    ).toBeGreaterThanOrEqual(expectedContracts);
    expect(Object.keys(document.paths)).toHaveLength(expectedContracts);

    for (const registeredPlugin of ALL_PLUGINS as PluginContract[]) {
      const dataName = `${registeredPlugin.tagName}.data`;
      expect(
        Object.hasOwn(document.components.schemas, dataName),
        `Missing data component ${dataName}`,
      ).toBe(true);
      expect(
        Object.hasOwn(
          document.paths,
          `/plugins/${registeredPlugin.tagName}/data`,
        ),
        `Missing data path for ${registeredPlugin.tagName}`,
      ).toBe(true);

      for (const functionName of Object.keys(
        registeredPlugin.functions ?? {},
      )) {
        for (const direction of ["input", "output"] as const) {
          const componentName = `${registeredPlugin.tagName}.${functionName}.${direction}`;
          expect(
            Object.hasOwn(document.components.schemas, componentName),
            `Missing RPC component ${componentName}`,
          ).toBe(true);
          expect(
            Object.hasOwn(
              document.paths,
              `/plugins/${registeredPlugin.tagName}/functions/${functionName}/${direction}`,
            ),
            `Missing RPC path for ${componentName}`,
          ).toBe(true);
        }
      }
    }
  });

  it("models representative data and RPC schemas bidirectionally", () => {
    expect(contractRefs(document, "/plugins/marimo-button/data")).toEqual({
      read: "#/components/schemas/marimo-button.data",
      write: "#/components/schemas/marimo-button.data",
    });
    expect(
      contractRefs(document, "/plugins/marimo-table/functions/search/input"),
    ).toEqual({
      read: "#/components/schemas/marimo-table.search.input",
      write: "#/components/schemas/marimo-table.search.input",
    });
    expect(
      contractRefs(document, "/plugins/marimo-table/functions/search/output"),
    ).toEqual({
      read: "#/components/schemas/marimo-table.search.output",
      write: "#/components/schemas/marimo-table.search.output",
    });
  });

  it("contains no dangling Zod definitions", () => {
    expect(JSON.stringify(document)).not.toContain("#/$defs");
  });
});

describe("buildPluginSpec", () => {
  it("emits accepted input shapes for defaults and transforms", () => {
    const doc = buildPluginSpec([
      plugin(
        "test-input",
        z.object({
          defaulted: z.string().default("default"),
          transformed: z.string().transform((value) => value.length),
        }),
      ),
    ]);
    const schema = doc.components.schemas["test-input.data"] as {
      properties: Record<string, { type: string }>;
      required?: string[];
    };

    expect(schema.properties.transformed.type).toBe("string");
    expect(schema.required).toEqual(["transformed"]);
  });

  it("resolves recursive schemas through their OpenAPI component", () => {
    interface RecursiveValue {
      children: RecursiveValue[];
    }
    const recursive: z.ZodType<RecursiveValue> = z.lazy(() =>
      z.object({ children: z.array(recursive) }),
    );
    const doc = buildPluginSpec([plugin("test-recursive", recursive)]);

    expect(
      JSON.stringify(doc.components.schemas["test-recursive.data"]),
    ).toContain('"$ref":"#/components/schemas/test-recursive.data"');
    expect(JSON.stringify(doc)).not.toContain("#/$defs");
  });

  it("uses explicit metadata for JSON-unrepresentable schemas", () => {
    const doc = buildPluginSpec([
      plugin(
        "test-date",
        z.instanceof(Date).meta({ type: "string", format: "date-time" }),
      ),
    ]);
    expect(doc.components.schemas["test-date.data"]).toEqual({
      type: "string",
      format: "date-time",
    });

    expect(() =>
      buildPluginSpec([
        plugin(
          "test-custom",
          z.custom(() => true),
        ),
      ]),
    ).toThrow(/explicit JSON Schema metadata.*test-only override/);
  });

  it("rejects duplicate tags and operation IDs", () => {
    expect(() =>
      buildPluginSpec([
        plugin("duplicate", z.string()),
        plugin("duplicate", z.number()),
      ]),
    ).toThrow("Duplicate plugin tag name duplicate");

    expect(() =>
      buildPluginSpec([
        plugin("operation-a-b", z.string()),
        plugin("operation-a_b", z.string()),
      ]),
    ).toThrow("Duplicate OpenAPI operationId");
  });

  it("rejects unresolved local component references", () => {
    expect(() =>
      buildPluginSpec([
        plugin(
          "test-missing-ref",
          z.string().meta({ $ref: "#/components/schemas/Missing" }),
        ),
      ]),
    ).toThrow("Unresolved OpenAPI component reference");
  });
});
