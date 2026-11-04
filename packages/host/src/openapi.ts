/* Copyright 2026 Marimo. All rights reserved. */

import { JsonSchema, Schema } from "effect";
import { OpenApi } from "effect/http-api";
import { AnalysisHostApi, HostApi } from "./api.ts";
import { modelDescriptions, operationDescriptions } from "./documentation.ts";
import * as Models from "./models.ts";

type StreamMetadata =
  | OpenApi.OpenApiSpecEffectStream
  | {
      encoding: "sse";
      errorSchema: JsonSchema.JsonSchema;
      failureEvent: "effect/httpapi/stream/failure";
    };
type MediaType = Omit<OpenApi.OpenApiSpecMediaType, "x-effect-stream"> & {
  "x-effect-stream"?: StreamMetadata;
};
type Response = Omit<OpenApi.OpenApiSpecResponse, "content"> & {
  content?: Record<string, MediaType>;
};
type Operation = Omit<OpenApi.OpenAPISpecOperation, "responses"> & {
  responses: Record<string, Response>;
};
export type HostOpenApi = Omit<OpenApi.OpenAPISpec, "paths"> & {
  paths: Record<
    string,
    Partial<Record<OpenApi.OpenAPISpecMethodName, Operation>>
  >;
};

const referenceName = (ref: string) =>
  ref.startsWith("#/components/schemas/")
    ? ref.slice("#/components/schemas/".length)
    : undefined;
const rewriteRefs = <A>(value: A, rewrite: (ref: string) => string): A =>
  JSON.parse(
    JSON.stringify(value, (key, value: unknown) =>
      key === "$ref" && typeof value === "string" ? rewrite(value) : value,
    ),
  );

const experimental = new Set([
  "Analysis",
  "CellAnalysis",
  "AnalysisEvent",
  "AnalysisMessage",
  "AnalysisNotebookEvent",
  "AnalysisProtocolEvent",
  "AnalysisObjectType",
]);

export function protocolModels(
  options: { analysis?: boolean } = {},
): Record<string, Schema.Top> {
  const models: Record<string, Schema.Top> = {};
  for (const [key, schema] of Object.entries(Models)) {
    if (experimental.has(key) || !Schema.isSchema(schema)) continue;
    const identifier = Schema.resolveAnnotations(schema)?.identifier;
    if (identifier) models[identifier] = schema;
  }
  if (options.analysis) {
    Object.assign(models, {
      Analysis: Models.Analysis,
      CellAnalysis: Models.CellAnalysis,
      AnalysisEvent: Models.AnalysisEvent,
      AnalysisMessage: Models.AnalysisMessage,
      Event: Models.AnalysisProtocolEvent,
      NotebookStreamEvent: Models.AnalysisNotebookEvent,
    });
    models.ObjectType = Models.AnalysisObjectType;
  }
  return models;
}

function fingerprint(
  value: unknown,
  definitions: JsonSchema.Definitions,
): string {
  function expand(node: unknown): unknown {
    if (Array.isArray(node)) return node.map(expand);
    if (node === null || typeof node !== "object") return node;
    const object = node as Record<string, unknown>;
    if (typeof object.$ref === "string") {
      const name = referenceName(object.$ref);
      if (name && definitions[name]) return expand(definitions[name]);
    }
    return Object.fromEntries(
      Object.entries(object)
        .filter(
          ([key, value]) =>
            key !== "description" &&
            !(
              key === "additionalProperties" &&
              typeof value === "boolean" &&
              object.properties !== undefined
            ),
        )
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([key, value]) => [key, expand(value)]),
    );
  }
  return JSON.stringify(expand(value));
}

/** Export the protocol, retaining one canonical component per handwritten model. */
export function toOpenApi(options: { analysis?: boolean } = {}): HostOpenApi {
  const spec = options.analysis
    ? OpenApi.fromApi(AnalysisHostApi)
    : OpenApi.fromApi(HostApi);
  const document = Schema.toJsonSchemaDocument(
    Schema.Struct(protocolModels(options)),
  );
  const canonical = JsonSchema.toMultiDocumentOpenApi3_1({
    dialect: document.dialect,
    schemas: [document.schema],
    definitions: document.definitions,
  }).definitions;
  const aliases = new Map<string, string>();
  for (const [name, schema] of Object.entries(canonical)) {
    const base = name.replace(/_\d+$/, "");
    if (
      base !== name &&
      canonical[base] &&
      fingerprint(schema, canonical) === fingerprint(canonical[base], canonical)
    )
      aliases.set(name, base);
  }
  for (const [name, schema] of Object.entries(spec.components.schemas)) {
    const base = name.replace(/_\d+$/, "");
    const target = [name, base].find(
      (candidate) =>
        canonical[candidate] &&
        fingerprint(schema, spec.components.schemas) ===
          fingerprint(canonical[candidate], canonical),
    );
    if (target) aliases.set(name, aliases.get(target) ?? target);
    else if (canonical[name] === undefined) canonical[name] = schema;
    else throw new Error(`Conflicting wire schemas for ${name}`);
  }
  const rewrite = (ref: string) => {
    const name = referenceName(ref);
    return name && aliases.has(name)
      ? `#/components/schemas/${aliases.get(name)}`
      : ref;
  };
  // Status annotations create distinct Effect ASTs for the same wire model.
  const output: HostOpenApi = rewriteRefs(spec, rewrite);
  output.components.schemas = Object.fromEntries(
    Object.entries(canonical)
      .filter(([name]) => !aliases.has(name) || aliases.get(name) === name)
      .map(([name, schema]) => [name, rewriteRefs(schema, rewrite)]),
  );
  for (const [name, schema] of Object.entries(output.components.schemas)) {
    if (modelDescriptions[name]) schema.description = modelDescriptions[name];
    const union = schema.anyOf ?? schema.oneOf;
    if (!Array.isArray(union)) continue;
    for (const propertyName of ["event", "kind"]) {
      const mapping: Record<string, string> = {};
      for (const branch of union) {
        if (typeof branch.$ref !== "string") break;
        const target = output.components.schemas[referenceName(branch.$ref)!];
        const fields = target?.properties as
          | Record<string, JsonSchema.JsonSchema>
          | undefined;
        const tag = fields?.[propertyName]?.enum;
        if (
          !Array.isArray(tag) ||
          tag.length !== 1 ||
          typeof tag[0] !== "string"
        )
          break;
        mapping[tag[0]] = branch.$ref;
      }
      if (Object.keys(mapping).length === union.length) {
        schema.oneOf = union;
        delete schema.anyOf;
        schema.discriminator = { propertyName, mapping };
        break;
      }
    }
  }
  for (const item of Object.values(output.paths)) {
    for (const method of ["get", "post", "put", "patch", "delete"] as const) {
      const operation = item[method];
      if (!operation) continue;
      if (operation.operationId)
        operation.description = operationDescriptions[operation.operationId];
      for (const response of Object.values(operation.responses)) {
        const stream = response.content?.["text/event-stream"];
        if (stream)
          stream["x-effect-stream"] = {
            encoding: "sse",
            errorSchema: { $ref: "#/components/schemas/Problem" },
            failureEvent: "effect/httpapi/stream/failure",
          };
      }
    }
  }
  if (options.analysis)
    Object.assign(output, { "x-marimo-experimental": ["analysis"] });
  Object.assign(output, { "x-marimo-source": "@marimo-team/host" });
  return output;
}
