/* Copyright 2026 Marimo. All rights reserved. */

/** Print the OpenAPI document of the host protocol as JSON. */

import * as NodeUtil from "node:util";
import { OpenApi } from "effect/http-api";
import { Api as ExperimentalApi } from "../src/experimental/Host.ts";
import { Api as StableApi, referencePolicy } from "../src/Host.ts";

const args = NodeUtil.parseArgs({
  options: { experimental: { type: "boolean", default: false } },
});

const doc = args.values.experimental
  ? OpenApi.fromApi(ExperimentalApi, { referencePolicy })
  : OpenApi.fromApi(StableApi, { referencePolicy });

process.stdout.write(`${JSON.stringify(doc, null, 2)}\n`);
