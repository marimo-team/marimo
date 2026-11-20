/* Copyright 2026 Marimo. All rights reserved. */

import NodeChildProcess from "node:child_process";
import NodeFs from "node:fs";
import NodeOs from "node:os";
import NodePath from "node:path";
import NodeUrl from "node:url";
import NodeUtil from "node:util";
import { generate, type OpenApiDocument } from "orval";

const root = NodeUrl.fileURLToPath(new URL("../../../", import.meta.url));
const { values: args } = NodeUtil.parseArgs({
  options: {
    check: { type: "boolean", default: false },
    "output-dir": { type: "string" },
  },
});
const source = args["output-dir"] ?? NodePath.join(root, "packages/client/src");
// The host protocol package prints its OpenAPI document, piped in on stdin.
const spec: OpenApiDocument = JSON.parse(NodeFs.readFileSync(0, "utf8"));
const header = [
  "/* Copyright 2026 Marimo. All rights reserved. */",
  "// Generated from packages/host-protocol. Do not edit.",
  "// Regenerate with: pnpm --dir packages/client codegen",
  "\n",
].join("\n");

interface Parameter {
  name: string;
  in: "path" | "query" | "header";
  required?: boolean;
}

interface Response {
  content?: Record<
    string,
    { schema?: { $ref?: string; anyOf?: { $ref: string }[] } }
  >;
}

interface Operation {
  operationId: string;
  summary?: string;
  parameters?: Parameter[];
  requestBody?: {
    required?: boolean;
    content: Record<string, { schema: { $ref: string } }>;
  };
  responses: Record<string, Response>;
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
 * Shapes the client cannot call yet are rejected, so a change to the
 * spec fails here instead of producing a wrong table.
 */
function operationsModule(spec: OpenApiDocument): string {
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
      for (const parameter of operation.parameters ?? []) {
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
        const types = Object.keys(response.content ?? {});
        if (types.join() === "application/problem+json") {
          const schema = response.content?.["application/problem+json"]?.schema;
          const members = schema?.anyOf ?? [schema];
          problems.push(
            `${status}: [${members.map((member) => `Protocol.${refName(member?.$ref)}`).join(", ")}]`,
          );
        } else if (types.length === 0) {
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
          `problems: { ${problems.join(", ")} },`,
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
 * \`problems\` maps each error status to the problems it can carry.
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
  let generated = NodeFs.readFileSync(output, "utf8");
  for (const [name, schema] of Object.entries(schemas)) {
    if (
      typeof schema === "object" &&
      "additionalProperties" in schema &&
      schema.additionalProperties === false
    ) {
      const declaration = new RegExp(
        `(export const ${name} = zod\\s*\\.)object\\(`,
      );
      if (!declaration.test(generated)) {
        throw new Error(`Expected an object schema for ${name}`);
      }
      generated = generated.replace(declaration, "$1strictObject(");
    }
  }
  NodeFs.writeFileSync(output, header + generated);
  const table = NodePath.join(temporary, "operations-table.ts");
  NodeFs.writeFileSync(table, operationsModule(spec));
  NodeChildProcess.execFileSync(
    NodePath.join(root, "node_modules/.bin/oxfmt"),
    ["--config", NodePath.join(root, ".oxfmtrc.json"), output, table],
  );
  if (!args.check) {
    NodeFs.mkdirSync(source, { recursive: true });
  }
  for (const [generated, name] of [
    [output, "protocol.ts"],
    [table, "operations.ts"],
  ] as const) {
    const content = NodeFs.readFileSync(generated, "utf8");
    const destination = NodePath.join(source, name);
    if (args.check) {
      if (
        !NodeFs.existsSync(destination) ||
        NodeFs.readFileSync(destination, "utf8") !== content
      ) {
        throw new Error(
          `${name} is stale; regenerate with the same feature selection and output directory`,
        );
      }
    } else {
      NodeFs.writeFileSync(destination, content);
    }
  }
} finally {
  NodeFs.rmSync(temporary, { recursive: true, force: true });
}
