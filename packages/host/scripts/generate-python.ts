/* Copyright 2026 Marimo. All rights reserved. */

import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { toOpenApi } from "../src/openapi.ts";

const { values } = parseArgs({
  options: {
    "include-experimental": { type: "boolean", default: false },
    "output-dir": { type: "string" },
    check: { type: "boolean", default: false },
  },
});
const root = fileURLToPath(new URL("../../../", import.meta.url));
const output = values["output-dir"]
  ? resolve(values["output-dir"])
  : join(root, "packages/host/generated/python");
const temporary = mkdtempSync(join(tmpdir(), "marimo-host-"));
try {
  const input = join(temporary, "openapi.json");
  writeFileSync(
    input,
    JSON.stringify(toOpenApi({ analysis: values["include-experimental"] })),
  );
  execFileSync(
    "uv",
    [
      "run",
      "--no-config",
      "--locked",
      "--script",
      join(root, "protocols/host/generate.py"),
      "--input",
      input,
      "--output-dir",
      output,
      ...(values.check ? ["--check"] : []),
    ],
    { cwd: root, stdio: "inherit" },
  );
} finally {
  rmSync(temporary, { recursive: true, force: true });
}
