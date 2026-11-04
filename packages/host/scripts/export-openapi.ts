/* Copyright 2026 Marimo. All rights reserved. */

import { parseArgs } from "node:util";
import { toOpenApi } from "../src/openapi.ts";
const { values } = parseArgs({
  options: { "include-experimental": { type: "boolean", default: false } },
});
process.stdout.write(
  `${JSON.stringify(toOpenApi({ analysis: values["include-experimental"] }), null, 2)}\n`,
);
