// @ts-check
import * as fs from "node:fs";
import * as path from "node:path";

const target = process.argv[2];

if (!target) {
  console.error("Usage: node convert_types.js <file-or-directory>");
  process.exit(1);
}

/** @param {string} filePath */
function processFile(filePath) {
  const content = fs.readFileSync(filePath, "utf8");
  const newContent = content.replace(
    /Record<string, never>/g,
    "Record<string, any>",
  );
  if (content !== newContent) {
    fs.writeFileSync(filePath, newContent);
    console.log(`Updated: ${filePath}`);
  }
}

/** @param {string} dir */
function processDirectory(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      processDirectory(fullPath);
    } else if (entry.isFile() && entry.name.endsWith(".ts")) {
      processFile(fullPath);
    }
  }
}

if (fs.existsSync(target)) {
  const stats = fs.statSync(target);
  if (stats.isDirectory()) {
    processDirectory(target);
  } else if (stats.isFile()) {
    processFile(target);
  }
  console.log("Replacement complete.");
} else {
  console.error(`Error: ${target} is not a file or directory`);
  process.exit(1);
}
