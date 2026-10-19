/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync } from "node:fs";
import path from "node:path";
import { pairConfigSchema } from "@/core/config/pair";

// Read the Python-owned resource only in tests to check the shared contract.
export const PAIR_CONFIG = pairConfigSchema.parse({
  command: "uvx marimo@latest",
  hostEnabled: true,
  templates: JSON.parse(
    readFileSync(
      path.resolve(
        import.meta.dirname,
        "../../../../marimo/_cli/pair/prompt.json",
      ),
      "utf8",
    ),
  ),
});
