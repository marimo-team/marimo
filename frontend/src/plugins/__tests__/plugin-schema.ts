/* Copyright 2026 Marimo. All rights reserved. */

import { z, type ZodType } from "zod";

interface FunctionContract {
  input: ZodType;
  output: ZodType;
}

export interface PluginContract {
  tagName: string;
  validator: ZodType;
  functions?: Record<string, FunctionContract>;
}

export interface PluginOpenAPIDocument {
  openapi: "3.1.0";
  info: {
    title: string;
    version: string;
    description: string;
  };
  tags: Array<{ name: string; description: string }>;
  paths: Record<string, Record<string, unknown>>;
  components: {
    schemas: Record<string, Record<string, unknown>>;
  };
}

export interface UnrepresentableSchemaContext {
  componentName: string;
  path: PropertyKey[];
  type: string;
}

export interface BuildPluginSpecOptions {
  unrepresentableSchemaOverride?: (
    context: UnrepresentableSchemaContext,
  ) => Record<string, unknown> | undefined;
}

const IDENTIFIER = /^[A-Za-z0-9._-]+$/;
const UNREPRESENTABLE_ZOD_TYPES = new Set([
  "bigint",
  "custom",
  "date",
  "function",
  "map",
  "nan",
  "set",
  "symbol",
  "transform",
  "undefined",
  "void",
]);
const JSON_SCHEMA_SHAPE_KEYS = [
  "$ref",
  "allOf",
  "anyOf",
  "const",
  "enum",
  "not",
  "oneOf",
  "type",
] as const;

function assertIdentifier(value: string, kind: string): void {
  if (!IDENTIFIER.test(value)) {
    throw new Error(
      `${kind} ${JSON.stringify(value)} must match ${IDENTIFIER.source}`,
    );
  }
}

function hasJSONSchemaShape(metadata: Record<string, unknown>): boolean {
  return JSON_SCHEMA_SHAPE_KEYS.some((key) => key in metadata);
}

function rewriteSharedReferences(
  value: unknown,
  componentName: string,
): unknown {
  if (typeof value === "string") {
    const prefix = "#/components/schemas/__shared#/$defs/";
    return value.startsWith(prefix)
      ? `#/components/schemas/${componentName}.def.${value.slice(prefix.length)}`
      : value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => rewriteSharedReferences(item, componentName));
  }
  if (value === null || typeof value !== "object") {
    return value;
  }
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      rewriteSharedReferences(item, componentName),
    ]),
  );
}

function withoutDocumentMetadata(
  schema: Record<string, unknown>,
): Record<string, unknown> {
  const { $id: _id, $schema: _schema, ...component } = schema;
  return component;
}

function toComponentSchemas(
  componentName: string,
  schema: ZodType,
  options: BuildPluginSpecOptions,
): Record<string, Record<string, unknown>> {
  const registry = z.registry<{ id: string }>();
  registry.add(schema, { id: componentName });
  const unrepresentablePaths = new Set<string>();
  const representedPaths = new Set<string>();

  const result = z.toJSONSchema(registry, {
    io: "input",
    unrepresentable: "any",
    uri: (id) => `#/components/schemas/${id}`,
    override: ({ jsonSchema, path, zodSchema }) => {
      const type = (zodSchema._zod.def as { type: string }).type;
      if (!UNREPRESENTABLE_ZOD_TYPES.has(type)) {
        return;
      }

      const pathKey = JSON.stringify(path);
      const metadata = z.globalRegistry.get(zodSchema) ?? {};
      if (hasJSONSchemaShape(metadata)) {
        representedPaths.add(pathKey);
        return;
      }

      const override = options.unrepresentableSchemaOverride?.({
        componentName,
        path,
        type,
      });
      if (override && hasJSONSchemaShape(override)) {
        Object.assign(jsonSchema, override);
        representedPaths.add(pathKey);
      } else {
        unrepresentablePaths.add(pathKey);
      }
    },
  });
  for (const path of unrepresentablePaths) {
    if (!representedPaths.has(path)) {
      throw new Error(
        `Zod schema at ${path} in ${componentName} is not representable in JSON Schema; add explicit JSON Schema metadata with .meta(...) or a narrowly scoped test-only override`,
      );
    }
  }
  const generated = result.schemas[componentName];
  if (!generated) {
    throw new Error(`Zod did not generate component ${componentName}`);
  }

  const components: Record<string, Record<string, unknown>> = {
    [componentName]: withoutDocumentMetadata(
      rewriteSharedReferences(generated, componentName) as Record<
        string,
        unknown
      >,
    ),
  };
  const shared = result.schemas.__shared as
    | { $defs?: Record<string, Record<string, unknown>> }
    | undefined;
  for (const [definitionName, definition] of Object.entries(
    shared?.$defs ?? {},
  )) {
    const name = `${componentName}.def.${definitionName}`;
    assertIdentifier(name, "Generated definition name");
    components[name] = withoutDocumentMetadata(
      rewriteSharedReferences(definition, componentName) as Record<
        string,
        unknown
      >,
    );
  }
  return components;
}

function operationSuffix(componentName: string): string {
  return componentName.replaceAll(/[^A-Za-z0-9]+/g, "_");
}

function addBidirectionalContract({
  paths,
  operationIds,
  path,
  componentName,
  summary,
  tag,
}: {
  paths: Record<string, Record<string, unknown>>;
  operationIds: Set<string>;
  path: string;
  componentName: string;
  summary: string;
  tag: string;
}): void {
  if (paths[path]) {
    throw new Error(`Duplicate OpenAPI path ${path}`);
  }

  const suffix = operationSuffix(componentName);
  const readOperationId = `read_${suffix}`;
  const writeOperationId = `write_${suffix}`;
  for (const operationId of [readOperationId, writeOperationId]) {
    if (operationIds.has(operationId)) {
      throw new Error(`Duplicate OpenAPI operationId ${operationId}`);
    }
    operationIds.add(operationId);
  }

  const ref = { $ref: `#/components/schemas/${componentName}` };
  paths[path] = {
    summary,
    get: {
      operationId: readOperationId,
      summary: `Read ${summary}`,
      tags: [tag],
      responses: {
        "200": {
          description: `${summary} accepted by a plugin consumer.`,
          content: { "application/json": { schema: ref } },
        },
      },
    },
    put: {
      operationId: writeOperationId,
      summary: `Write ${summary}`,
      tags: [tag],
      requestBody: {
        required: true,
        content: { "application/json": { schema: ref } },
      },
      responses: { "204": { description: "Accepted." } },
    },
  };
}

function assertLocalReferencesResolve(document: PluginOpenAPIDocument): void {
  const visit = (value: unknown): void => {
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (value === null || typeof value !== "object") {
      return;
    }

    const record = value as Record<string, unknown>;
    const ref = record.$ref;
    if (typeof ref === "string") {
      if (ref.startsWith("#/$defs")) {
        throw new Error(`Dangling document-root Zod reference ${ref}`);
      }
      const prefix = "#/components/schemas/";
      if (
        ref.startsWith(prefix) &&
        !document.components.schemas[ref.slice(prefix.length)]
      ) {
        throw new Error(`Unresolved OpenAPI component reference ${ref}`);
      }
    }
    Object.values(record).forEach(visit);
  };

  visit(document);
}

/**
 * Build a synthetic OpenAPI document for the Zod-backed plugin contracts.
 *
 * Each schema is exposed as both a response and request so compatibility
 * checks catch narrowing/removals as well as newly required fields. The paths
 * describe internal frontend/kernel contracts; they are not HTTP endpoints.
 */
export function buildPluginSpec(
  plugins: readonly PluginContract[],
  options: BuildPluginSpecOptions = {},
): PluginOpenAPIDocument {
  const paths: Record<string, Record<string, unknown>> = {};
  const schemas: Record<string, Record<string, unknown>> = {};
  const operationIds = new Set<string>();
  const tagNames = new Set<string>();

  const addComponent = (name: string, schema: ZodType): void => {
    assertIdentifier(name, "Component name");
    const generated = toComponentSchemas(name, schema, options);
    for (const [generatedName, generatedSchema] of Object.entries(generated)) {
      if (schemas[generatedName]) {
        throw new Error(`Duplicate OpenAPI component ${generatedName}`);
      }
      schemas[generatedName] = generatedSchema;
    }
  };

  for (const plugin of [...plugins].toSorted((a, b) =>
    a.tagName.localeCompare(b.tagName),
  )) {
    assertIdentifier(plugin.tagName, "Plugin tag name");
    if (tagNames.has(plugin.tagName)) {
      throw new Error(`Duplicate plugin tag name ${plugin.tagName}`);
    }
    tagNames.add(plugin.tagName);

    const dataComponent = `${plugin.tagName}.data`;
    addComponent(dataComponent, plugin.validator);
    addBidirectionalContract({
      paths,
      operationIds,
      path: `/plugins/${plugin.tagName}/data`,
      componentName: dataComponent,
      summary: `${plugin.tagName} data`,
      tag: "plugin-data",
    });

    const functions = Object.entries(plugin.functions ?? {}).toSorted(
      ([a], [b]) => a.localeCompare(b),
    );
    for (const [functionName, contract] of functions) {
      assertIdentifier(functionName, "Plugin function name");
      for (const [direction, schema] of [
        ["input", contract.input],
        ["output", contract.output],
      ] as const) {
        const componentName = `${plugin.tagName}.${functionName}.${direction}`;
        addComponent(componentName, schema);
        addBidirectionalContract({
          paths,
          operationIds,
          path: `/plugins/${plugin.tagName}/functions/${functionName}/${direction}`,
          componentName,
          summary: `${plugin.tagName} ${functionName} ${direction}`,
          tag: `rpc-${direction}`,
        });
      }
    }
  }

  const document: PluginOpenAPIDocument = {
    openapi: "3.1.0",
    info: {
      title: "marimo plugin contracts",
      version: "1.0.0",
      description: [
        "Machine-checkable description of every registered frontend plugin's",
        "Zod-backed data and RPC contracts. This is not an HTTP API: each",
        "synthetic GET models what consumers must accept and each PUT models",
        "what producers may write, allowing OpenAPI diff tooling to enforce",
        "backward compatibility in both directions.",
        "Regenerate with: pnpm --filter @marimo-team/frontend plugins:generate-schema",
      ].join("\n"),
    },
    tags: [
      {
        name: "plugin-data",
        description: "Data supplied when rendering a plugin.",
      },
      {
        name: "rpc-input",
        description: "Arguments supplied to a plugin RPC function.",
      },
      {
        name: "rpc-output",
        description: "Values returned by a plugin RPC function.",
      },
    ],
    paths,
    components: { schemas },
  };
  assertLocalReferencesResolve(document);
  return document;
}
