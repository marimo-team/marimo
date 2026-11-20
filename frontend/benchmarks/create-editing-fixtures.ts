/* Copyright 2026 Marimo. All rights reserved. */

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const directory = process.argv[2];
const outlines = process.argv.includes("--outlines");
if (!directory) {
  throw new Error(
    "Usage: node benchmarks/create-editing-fixtures.ts NEW_DIRECTORY [--outlines]",
  );
}
// A new directory prevents overwriting notebooks or personal configuration.
await mkdir(directory, { recursive: false });
await writeFile(
  path.join(directory, ".marimo.toml"),
  `
[runtime]
auto_instantiate = true
[completion]
copilot = false
[language_servers.pylsp]
enabled = false
`,
);
// Stop project configuration discovery before reaching the repository config.
await writeFile(path.join(directory, "pyproject.toml"), "[tool.marimo]\n");

for (const count of [25, 100]) {
  let source = "import marimo\napp = marimo.App()\n";
  for (let i = 0; i < count; i++) {
    const imports = outlines && i === 0;
    const output = outlines && i > 0;
    source += `\n@app.cell\ndef _(${output ? "mo" : ""}):\n`;
    source += imports ? "    import marimo as mo\n" : `    value_${i} = ${i}\n`;
    for (let line = 2; line <= (output ? 18 : 19); line++) {
      source += `    # line ${line}\n`;
    }
    if (output) {
      source += `    mo.md("## Section ${i}\\n\\n### Details ${i}")\n`;
    }
    source += `    # edit here\n    return (${imports ? "mo" : `value_${i}`},)\n`;
  }
  source += '\nif __name__ == "__main__":\n    app.run()\n';
  await writeFile(
    path.join(directory, `${outlines ? "outline" : "browser"}-${count}.py`),
    source,
  );
}
