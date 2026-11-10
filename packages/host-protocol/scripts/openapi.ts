/* Copyright 2026 Marimo. All rights reserved. */

/** Print the OpenAPI document of the host protocol as JSON. */

import * as NodeUtil from "node:util";
import { OpenApi } from "effect/http-api";
import * as Analysis from "../src/experimental/Analysis.ts";
import * as Host from "../src/Host.ts";

const args = NodeUtil.parseArgs({
  options: { experimental: { type: "boolean", default: false } },
});

const doc = args.values.experimental
  ? OpenApi.fromApi(Analysis.Api, { referencePolicy: Host.referencePolicy })
  : OpenApi.fromApi(Host.Api, { referencePolicy: Host.referencePolicy });

process.stdout.write(`${JSON.stringify(doc, null, 2)}\n`);
