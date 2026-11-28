/* Copyright 2026 Marimo. All rights reserved. */

/** Write marimo's Python bindings for the host protocol. */

import * as NodeChildProcess from "node:child_process";
import * as NodeFs from "node:fs";
import * as NodePath from "node:path";
import * as NodeUtil from "node:util";
import { HttpApi, OpenApi } from "effect/http-api";
import { Api as ExperimentalApi } from "../src/experimental/Host.ts";
import { Api as StableApi, referencePolicy } from "../src/Host.ts";

import { calls } from "./python/calls.ts";
import { events } from "./python/events.ts";
import { models } from "./python/models.ts";

const PACKAGE = NodePath.resolve(
  import.meta.dirname,
  "../../../marimo/_core/protocol",
);
const options = { command: "make host-protocol-codegen" };

const args = NodeUtil.parseArgs({
  options: {
    experimental: { type: "boolean", default: false },
    check: { type: "boolean", default: false },
    "dry-run": { type: "boolean", default: false },
  },
});

// Operations need the groups and names that the OpenAPI document drops.
const [document, api] = args.values.experimental
  ? [
      OpenApi.fromApi(ExperimentalApi, { referencePolicy }),
      calls((visit) => HttpApi.reflect(ExperimentalApi, visit), options),
    ]
  : [
      OpenApi.fromApi(StableApi, { referencePolicy }),
      calls((visit) => HttpApi.reflect(StableApi, visit), options),
    ];

const modules = {
  // The package is its records, and it loads the modules that build on them.
  "__init__.py": `${models(document, options)}
from marimo._core.protocol import api as api, events as events  # noqa: E402
`,
  "events.py": events(document, options),
  "api.py": api,
};

let stale = false;
for (const [name, source] of Object.entries(modules)) {
  const formatted = NodeChildProcess.execFileSync(
    "uvx",
    ["ruff@0.16.4", "format", "--isolated", "--line-length", "79", "-"],
    { input: source, encoding: "utf8" },
  );
  const target = NodePath.join(PACKAGE, name);
  const current = NodeFs.existsSync(target)
    ? NodeFs.readFileSync(target, "utf8")
    : undefined;
  if (args.values["dry-run"] || current === formatted) {
    continue;
  }
  stale = true;
  if (!args.values.check) {
    NodeFs.mkdirSync(PACKAGE, { recursive: true });
    NodeFs.writeFileSync(target, formatted);
  }
}
if (stale && args.values.check) {
  throw new Error(`Host bindings are stale. Run \`${options.command}\`.`);
}
process.stdout.write("Host protocol bindings are current.\n");
