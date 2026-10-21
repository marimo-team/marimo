/* Copyright 2026 Marimo. All rights reserved. */

import NodeChildProcess from "node:child_process";
import NodeFs from "node:fs";
import NodeOs from "node:os";
import NodePath from "node:path";
import NodeUrl from "node:url";
import { generate, type OpenApiDocument } from "orval";
import { parse } from "yaml";

const root = NodeUrl.fileURLToPath(new URL("../../../", import.meta.url));
const source = NodePath.join(root, "packages/client/src");
const header = `/* Copyright 2026 Marimo. All rights reserved. */
// Generated from protocols/host/openapi.yaml. Do not edit.
// Regenerate with: pnpm --dir packages/client codegen

`;

interface Parameter {
  name: string;
  in: "path" | "query" | "header";
  required?: boolean;
}

interface Response {
  content?: Record<string, { schema?: { $ref?: string } }>;
}

interface Operation {
  operationId: string;
  summary?: string;
  parameters?: { $ref: string }[];
  requestBody?: {
    required?: boolean;
    content: Record<string, { schema: { $ref: string } }>;
  };
  responses: Record<string, Response | { $ref: string }>;
}

/** The last segment of a local `$ref`, such as `EditRequest`. */
function refName(ref: string | undefined): string {
  const name = ref?.match(/^#\/components\/\w+\/(\w+)$/)?.[1];
  if (name === undefined) {
    throw new Error(`Unsupported reference: ${ref}`);
  }
  return name;
}

/**
 * Describe each operation as data for the client to call.
 *
 * Error responses share the `Problem` schema, so only their statuses are
 * listed. Shapes the client cannot call yet are rejected, so a change to the
 * spec fails here instead of producing a wrong table.
 */
function operationsModule(spec: OpenApiDocument): string {
  const parameters = spec.components?.parameters as
    | Record<string, Parameter>
    | undefined;
  const entries: string[] = [];
  for (const [path, item] of Object.entries(spec.paths ?? {})) {
    for (const [method, value] of Object.entries(item ?? {})) {
      if (!["get", "post", "put", "patch", "delete"].includes(method)) {
        throw new Error(`Unsupported path item field ${method} on ${path}`);
      }
      const operation = value as Operation;
      const id = operation.operationId;
      const query: string[] = [];
      const headers: string[] = [];
      const pathNames: string[] = [];
      for (const reference of operation.parameters ?? []) {
        const parameter = parameters?.[refName(reference.$ref)];
        if (parameter === undefined) {
          throw new Error(`${id} names an unknown parameter`);
        }
        const entry = `${JSON.stringify(parameter.name)}: ${parameter.required === true}`;
        if (parameter.in === "path") {
          pathNames.push(parameter.name);
        } else if (parameter.in === "query") {
          query.push(entry);
        } else {
          headers.push(entry);
        }
      }
      const placeholders = [...path.matchAll(/\{(\w+)\}/g)].map((m) => m[1]);
      if (placeholders.join() !== pathNames.join()) {
        throw new Error(`${id} parameters do not match ${path}`);
      }
      let body = "null";
      if (operation.requestBody !== undefined) {
        const json = operation.requestBody.content["application/json"];
        if (operation.requestBody.required !== true || json === undefined) {
          throw new Error(`${id} has an unsupported request body`);
        }
        body = `Protocol.${refName(json.schema.$ref)}`;
      }
      const responses: string[] = [];
      const problems: string[] = [];
      for (const [status, response] of Object.entries(operation.responses)) {
        if ("$ref" in response) {
          problems.push(status);
          continue;
        }
        const types = Object.keys(response.content ?? {});
        if (types.length === 0) {
          responses.push(`${status}: null`);
        } else if (types.join() === "text/event-stream") {
          responses.push(`${status}: "text/event-stream"`);
        } else if (types.join() === "application/json") {
          const schema = response.content?.["application/json"]?.schema;
          responses.push(`${status}: Protocol.${refName(schema?.$ref)}`);
        } else {
          throw new Error(`${id} ${status} has unsupported content ${types}`);
        }
      }
      entries.push(
        [
          operation.summary ? `/** ${operation.summary}. */` : "",
          `${JSON.stringify(id)}: {`,
          `method: ${JSON.stringify(method.toUpperCase())},`,
          `path: ${JSON.stringify(path)},`,
          `query: { ${query.join(", ")} },`,
          `headers: { ${headers.join(", ")} },`,
          `body: ${body},`,
          `responses: { ${responses.join(", ")} },`,
          `problems: [${problems.join(", ")}],`,
          "},",
        ].join("\n"),
      );
    }
  }
  return `${header}import * as Protocol from "./protocol.ts";

/**
 * The host API's operations by id.
 *
 * Path parameters are the placeholders in \`path\`. \`query\` and \`headers\`
 * map each parameter to whether it is required. \`responses\` maps each
 * success status to its schema, \`null\` for no content, or an event stream.
 * \`problems\` lists the statuses that answer with a \`Problem\`.
 */
export const operations = {
${entries.join("\n")}
} as const;

/** An operation id, such as \`notebook.edit\`. */
export type OperationId = keyof typeof operations;
`;
}

const temporary = NodeFs.mkdtempSync(
  NodePath.join(NodeOs.tmpdir(), "marimo-host-protocol-"),
);
try {
  const spec: OpenApiDocument = parse(
    NodeFs.readFileSync(
      NodePath.join(root, "protocols/host/openapi.yaml"),
      "utf8",
    ),
  );
  const schemas = spec.components?.schemas;
  if (!schemas) {
    throw new Error("Host protocol has no component schemas");
  }
  const output = NodePath.join(temporary, "protocol.ts");
  await generate({
    input: {
      target: { ...spec, paths: {}, components: { schemas } },
    },
    output: {
      target: NodePath.join(temporary, "operations.ts"),
      client: "zod",
      schemas: { path: output, type: "zod", mode: "single" },
      override: {
        header: false,
        zod: {
          version: 4,
          generateReusableSchemas: true,
          dateTimeOptions: { offset: true },
        },
      },
    },
  });
  NodeFs.writeFileSync(output, header + NodeFs.readFileSync(output, "utf8"));
  const table = NodePath.join(temporary, "operations-table.ts");
  NodeFs.writeFileSync(table, operationsModule(spec));
  NodeChildProcess.execFileSync(
    NodePath.join(root, "node_modules/.bin/oxfmt"),
    ["--config", NodePath.join(root, ".oxfmtrc.json"), output, table],
  );
  for (const [generated, name] of [
    [output, "protocol.ts"],
    [table, "operations.ts"],
  ] as const) {
    const content = NodeFs.readFileSync(generated, "utf8");
    const destination = NodePath.join(source, name);
    if (process.argv.includes("--check")) {
      if (
        !NodeFs.existsSync(destination) ||
        NodeFs.readFileSync(destination, "utf8") !== content
      ) {
        throw new Error(
          `${name} is stale; run pnpm --dir packages/client codegen`,
        );
      }
    } else {
      NodeFs.writeFileSync(destination, content);
    }
  }
} finally {
  NodeFs.rmSync(temporary, { recursive: true, force: true });
}
