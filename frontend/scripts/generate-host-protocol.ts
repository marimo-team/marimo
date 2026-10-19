/* Copyright 2026 Marimo. All rights reserved. */

import NodeChildProcess from "node:child_process";
import NodeFs from "node:fs";
import NodeOs from "node:os";
import NodePath from "node:path";
import NodeUrl from "node:url";
import { generate, type OpenApiDocument } from "orval";
import { parse } from "yaml";

const root = NodeUrl.fileURLToPath(new URL("../../", import.meta.url));
const destination = NodePath.join(root, "frontend/src/core/host/protocol.ts");
const header = `/* Copyright 2026 Marimo. All rights reserved. */
// Generated from protocols/host/openapi.yaml. Do not edit.
// Regenerate with: pnpm --dir frontend codegen

`;

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
  // Native marimo messages are independent of the portable host protocol.
  schemas.MarimoNotification = {};
  schemas.MarimoEvent = {
    type: "object",
    description: "A native marimo message carried by a host stream.",
    required: ["event", "data"],
    properties: {
      event: { type: "string", enum: ["marimo"] },
      id: { type: "string", minLength: 1 },
      data: {
        type: "object",
        required: ["marimo"],
        properties: {
          marimo: { $ref: "#/components/schemas/MarimoNotification" },
        },
      },
    },
  };
  const event = schemas.Event;
  if (!event || typeof event !== "object" || "$ref" in event || !event.oneOf) {
    throw new Error("Host protocol has no event union");
  }
  event.oneOf.push({ $ref: "#/components/schemas/MarimoEvent" });
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
  NodeChildProcess.execFileSync(
    NodePath.join(root, "node_modules/.bin/oxfmt"),
    ["--config", NodePath.join(root, ".oxfmtrc.json"), output],
  );
  const content = NodeFs.readFileSync(output, "utf8");
  if (process.argv.includes("--check")) {
    if (
      !NodeFs.existsSync(destination) ||
      NodeFs.readFileSync(destination, "utf8") !== content
    ) {
      throw new Error(
        "Host protocol schemas are stale; run pnpm --dir frontend codegen",
      );
    }
  } else {
    NodeFs.mkdirSync(NodePath.dirname(destination), { recursive: true });
    NodeFs.writeFileSync(destination, content);
  }
} finally {
  NodeFs.rmSync(temporary, { recursive: true, force: true });
}
