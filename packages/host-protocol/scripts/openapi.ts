/* Copyright 2026 Marimo. All rights reserved. */

/** Print the OpenAPI document of the host protocol as JSON. */

import { parseArgs } from "node:util";
import { OpenApi } from "effect/http-api";
import * as Analysis from "../src/experimental/Analysis.ts";
import * as Host from "../src/Host.ts";

const { values } = parseArgs({
  options: { experimental: { type: "boolean", default: false } },
});
const { referencePolicy } = Host;
const document = values.experimental
  ? OpenApi.fromApi(Analysis.Api, { referencePolicy })
  : OpenApi.fromApi(Host.Api, { referencePolicy });
process.stdout.write(`${JSON.stringify(document, null, 2)}\n`);
