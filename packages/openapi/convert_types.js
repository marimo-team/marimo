/* Copyright 2024 Marimo. All rights reserved. */
/** biome-ignore-all lint/suspicious/noConsole: for debugging */
// @ts-check
import * as fs from "node:fs";
import * as process from "node:process";

/**
 * Make an assertion.
 *
 * @param {unknown} expression - The expression to test.
 * @param {string=} msg - The optional message to display if the assertion fails.
 * @returns {asserts expression}
 * @throws an {@link Error} if `expression` is not truthy.
 */
function assert(expression, msg = "") {
  if (!expression) {
    console.error(msg);
    process.exit(1);
  }
}

function main() {
  const paths = process.argv.slice(2);

  if (paths.length === 0) {
    console.error("Usage: node convert_types.js file1.ts [file2.ts ...]");
    process.exit(1);
  }

  for (const filePath of paths) {
    assert(fs.existsSync(filePath), `Expected ${filePath} to exist`);
    assert(
      filePath.endsWith(".ts"),
      `Expected ${filePath} to have .ts extension`,
    );
    const stats = fs.statSync(filePath);
    assert(stats.isFile(), `Expected ${filePath} to be a file`);

    const content = fs.readFileSync(filePath, "utf8");
    const newContent = content.replace(
      /Record<string, never>/g,
      "Record<string, any>",
    );
    if (content !== newContent) {
      fs.writeFileSync(filePath, newContent);
      console.log(`Updated: ${filePath}`);
    } else {
      console.log(`No changes made to: ${filePath}`);
    }
  }
}

main();
