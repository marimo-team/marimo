/* Copyright 2026 Marimo. All rights reserved. */

/** Print the OpenAPI document of the host protocol as JSON. */

import { parseArgs } from "node:util";
import * as Analysis from "../src/experimental/Analysis.ts";
import * as Host from "../src/Host.ts";
import * as OpenApi from "../src/OpenApi.ts";

const { values } = parseArgs({
  options: { experimental: { type: "boolean", default: false } },
});
const document = values.experimental
  ? OpenApi.fromApi(Analysis.Api)
  : OpenApi.fromApi(Host.Api);
process.stdout.write(`${JSON.stringify(document, null, 2)}\n`);
