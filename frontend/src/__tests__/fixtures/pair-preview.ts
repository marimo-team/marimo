/* Copyright 2026 Marimo. All rights reserved. */

import { readFileSync } from "node:fs";
import path from "node:path";
import { pairPreviewSchema } from "@/core/config/pair";

// Read the Python-owned resource only in tests to check the shared contract.
export const PAIR_PREVIEW = pairPreviewSchema.parse({
  command: "uvx marimo@latest",
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
