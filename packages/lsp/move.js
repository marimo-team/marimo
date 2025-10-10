#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");

// Copy node_modules/@github/copilot-language-server/dist/ to dist/
const srcDir = path.join(
  __dirname,
  "node_modules/@github/copilot-language-server/dist",
);
const destDir = path.join(__dirname, "dist");

// Recursively copy directory
fs.cpSync(srcDir, destDir, { recursive: true, dereference: true });

// Rename language-server.js to language-server.cjs
const oldPath = path.join(destDir, "language-server.js");
const newPath = path.join(destDir, "language-server.cjs");
fs.renameSync(oldPath, newPath);

// biome-ignore lint/suspicious/noConsole: build script
console.log("Successfully copied and renamed language-server files");
