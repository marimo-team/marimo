/* Copyright 2026 Marimo. All rights reserved. */

/** Print the OpenAPI document of the host protocol as JSON. */

import { parseArgs } from "node:util";
import { OpenApi } from "effect/http-api";
import { Api as ExperimentalApi } from "../src/experimental/Host.ts";
import { Api as StableApi, referencePolicy } from "../src/Host.ts";

const { values } = parseArgs({
  options: { experimental: { type: "boolean", default: false } },
});

const options = { referencePolicy };
const doc = values.experimental
  ? OpenApi.fromApi(ExperimentalApi, options)
  : OpenApi.fromApi(StableApi, options);

process.stdout.write(`${JSON.stringify(doc, null, 2)}\n`);
