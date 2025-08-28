import fs from "node:fs";
import path from "node:path";

import express from "express";
import httpProxy from "http-proxy-3";

import { buildMarimoForWasm, buildPyodideLockFile } from "./build-wasm";

const app = express();
const proxy = new httpProxy();

const TARGET_HOST = process.env.TARGET_HOST || "http://localhost";
const TARGET_PORT = parseInt(process.env.TARGET_PORT || "3000");
// The hostname is used when generating the pyodide lock file
const PUBLIC_PACKAGES_SCHEME = process.env.PUBLIC_PACKAGES_SCHEME || "http";
const PUBLIC_PACKAGES_HOST = process.env.PUBLIC_PACKAGES_HOST || "localhost";
const PUBLIC_PACKAGES_PORT = parseInt(
  process.env.PUBLIC_PACKAGES_PORT || "6008",
);
const PUBLIC_PACKAGES_BASE_PATH = process.env.PUBLIC_PACKAGES_BASE_PATH || "";
const PUBLIC_PACKAGES_BASE_URL =
  process.env.PUBLIC_PACKAGES_BASE_URL ||
  `${PUBLIC_PACKAGES_SCHEME}://${PUBLIC_PACKAGES_HOST}:${PUBLIC_PACKAGES_PORT}${PUBLIC_PACKAGES_BASE_PATH}`;
const PROXY_HOST = process.env.PROXY_HOST || "127.0.0.1";
const PROXY_PORT = parseInt(process.env.PROXY_PORT || "6008");

// The service you want to proxy to
const targetService = `${TARGET_HOST}:${TARGET_PORT}`;

let hasChanges = true;
let wheelFilename = "";
let lockFileUpToDate = false;
let lockfileJson = "";
const REPO_DIR =
  process.env.MARIMO_REPO_DIR ||
  path.resolve(path.join(__dirname, "../../../"));

// Watch the marimo directory for python file changes
fs.watch(path.join(REPO_DIR, "marimo"), (_event, filename) => {
  if ((filename || "").endsWith(".py")) {
    console.log(`${filename} file Changed`);
    hasChanges = true;
  }
});

app.all(/marimo_base.*.whl/, async (_req, res) => {
  // If there are changes we rebuild the marimo-base package and serve the file from disk
  if (hasChanges || wheelFilename === "") {
    console.log("Changes detected, rebuilding marimo-base package");
    try {
      wheelFilename = await buildMarimoForWasm(REPO_DIR);
    } catch (e) {
      res
        .status(500)
        .send(`Error building marimo-base package: ${(e as Error).message}`);
      return;
    }
    hasChanges = false;
    lockFileUpToDate = false;
  }
  const wheelPath = path.join(REPO_DIR, ".wasmbuilds", wheelFilename);
  console.log(`Serving marimo-base package: ${wheelPath}`);
  //res.sendFile(wheelPath);
  res
    .status(200)
    .setHeader("Content-Type", "application/octet-stream")
    .send(fs.readFileSync(wheelPath));
});

app.all("/pyodide-lock.json", async (_req, res) => {
  // We generate the pyodide-lock.json
  if (!lockFileUpToDate) {
    console.log("Generating pyodide-lock.json");
    lockfileJson = await buildPyodideLockFile({
      publishedWheelUrl: `${PUBLIC_PACKAGES_BASE_URL}/${wheelFilename}`,
      localWheelUrl: `http://127.0.0.1:${PROXY_PORT}/${wheelFilename}`,
      packages: ["pyoso==0.6.4", "pandas", "polars"],
    });
  }
  res
    .status(200)
    .setHeader("Content-Type", "application/json")
    .send(lockfileJson);
});

app.all("/{*path}", (req, res) => {
  console.log(`Proxying request to: ${targetService}${req.url}`);
  proxy.web(req, res, { target: targetService });
});

(async () => {
  try {
    console.log("Performing initial build of marimo-base package...");
    wheelFilename = await buildMarimoForWasm(REPO_DIR);
    console.log(`Initial build complete: ${wheelFilename}`);
    hasChanges = false;
  } catch (e) {
    console.error(
      "Error during initial build of marimo-base package:",
      (e as Error).message,
    );
  }
  app.listen(PROXY_PORT, async () => {
    console.log(`Proxy server is running on ${PROXY_HOST}:${PROXY_PORT}`);

    console.log("Performing initial generation of pyodide-lock.json...");

    // Build the initial pyodide lock file
    await buildPyodideLockFile({
      publishedWheelUrl: `${PUBLIC_PACKAGES_BASE_URL}/${wheelFilename}`,
      localWheelUrl: `http://${PROXY_HOST}:${PROXY_PORT}/${wheelFilename}`,
      packages: ["pyoso==0.6.4", "pandas", "polars"],
    });

    console.log("Initial pyodide-lock.json generated");
  });
})();
