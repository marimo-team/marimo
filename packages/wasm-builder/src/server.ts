import fs from "node:fs";
import path from "node:path";

import express from "express";
import httpProxy from "http-proxy-3";
import * as dotenv from "dotenv";

import { buildPyodideLockFile, type BuiltWheelWithUrls, createMarimoWatcher, createUVProjectWatcher, type GenericWatcher } from "./build-wasm";
import type { Server } from "node:http";

dotenv.config();

export type BuildOptions = {
  targetHostname: string;
  targetScheme: string;
  targetPort: number;
  publicPackagesScheme: string;
  publicPackagesHost: string;
  publicPackagesPort: number;
  publicPackagesBasePath: string;
  proxyHost: string;
  proxyPort: number;
  osoApiKey: string;
  otherUvPackagesToInclude: string;
  marimoRepoDir?: string;
}
export type LockFileGenerator = () => Promise<string>;
export type ServerKill = () => Promise<void>;
export type Watchers = Record<string, GenericWatcher>;

export type PostServerStartResponse = {
  lockFileGenerator: LockFileGenerator;
  watchers: Watchers;
  server: Server;
  options: BuildOptions;
}

export type BuildConfig = BuildOptions & {
  postServerStart: (response: PostServerStartResponse) => void;
}


const app = express();
const proxy = new httpProxy();

// Allow us to configure other uv packages we can load from source into the wasm environment
type UVProjectDefinition = {
  name: string;
  projectDir: string;
  outputDir: string;
}

export async function startServer(config: BuildConfig) {
  let TARGET_URL = `${config.targetScheme}://${config.targetHostname}:${config.targetPort}`;
  // If the port is 80 or 443, we don't need the port in the url
  if (config.targetPort === 80 || config.targetPort === 443) {
    TARGET_URL = `${config.targetScheme}://${config.targetHostname}`;
  }
  let PUBLIC_PACKAGES_BASE_URL = `${config.publicPackagesScheme}://${config.publicPackagesHost}:${config.publicPackagesPort}${config.publicPackagesBasePath}`;
  if (config.publicPackagesPort === 80 || config.publicPackagesPort === 443) {
    PUBLIC_PACKAGES_BASE_URL = `${config.publicPackagesScheme}://${config.publicPackagesHost}${config.publicPackagesBasePath}`;
  }
  const OTHER_UV_PACKAGES_TO_INCLUDE: Array<UVProjectDefinition> = JSON.parse(config.otherUvPackagesToInclude);
  const targetService = TARGET_URL;
  const REPO_DIR = config.marimoRepoDir || path.resolve(path.join(__dirname, "../../../"));
  let lockfileJson = "";
  let lockFileUpdateTimestamp = 0;

  const marimoWatcher = createMarimoWatcher(REPO_DIR);

  const watchers: Record<string, GenericWatcher> = {
    marimo_base: marimoWatcher,
    marimo: marimoWatcher,
  };

  for (const pkg of OTHER_UV_PACKAGES_TO_INCLUDE) {
    const { projectDir, outputDir } = pkg;
    watchers[pkg.name] = await createUVProjectWatcher({
      projectDir,
      outputDir,
    });
  }

  // HACK TO SUPPORT PYOSO
  app.all("/sql", async (req, res) => {
    // Add authorization header
    proxy.web(req, res, { 
      target: "https://www.opensource.observer/api/v1/sql",
      changeOrigin: true,
      headers: {
        Authorization: `Bearer ${config.osoApiKey}`,
      },
      ignorePath: true,
    });
  });

  app.all('/wasm/controller.js', async (req, res) => {
    req.headers.host = `${config.targetHostname}:${config.targetPort}`;
    proxy.web(req, res, {
      target: `${targetService}/src/oso-extensions/wasm/controller.tsx`,
      changeOrigin: true,
      ignorePath: true,
    });
  })

  app.all(/.*.whl/, async (req, res) => {
    // Parse the request URL. If it starts with one of the package names, we can
    // serve the corresponding wheel file
    const packageName = Object.keys(watchers).find((name) => req.url.startsWith(`/${name}`));
    if (packageName) {
      const buildWheel = await watchers[packageName].latestBuild();
      res
        .status(200)
        .setHeader("Content-Type", "application/octet-stream")
        .send(fs.readFileSync(buildWheel.path));
      return;
    } else {
      res.status(404).send("Not Found");
    }
  });

  const lockFileGenerator = async () => { 
    // Rebuild any watchers that are not ready
    const localBuiltPackages: Record<string, BuiltWheelWithUrls> = {};
    let latestTimestamp: number = 0;
    for (const [name, watcher] of Object.entries(watchers)) {
      const wheel = await watcher.latestBuild();
      // Create the published wheel url from the filename
      const wheelFilename = path.basename(wheel.path);
      localBuiltPackages[name] = {
        ...wheel,
        publishedWheelUrl: `${PUBLIC_PACKAGES_BASE_URL}/${wheelFilename}`,
        localWheelUrl: `http://127.0.0.1:${config.proxyPort}/${wheelFilename}`,
      };
      if (localBuiltPackages[name].timestamp > latestTimestamp) {
        latestTimestamp = localBuiltPackages[name].timestamp;
      }
    }

    // We generate the pyodide-lock.json
    if (lockFileUpdateTimestamp < latestTimestamp) {
      console.log("Generating pyodide-lock.json");
      lockfileJson = await buildPyodideLockFile({
        packages: ["pyoso", "pandas", "polars"],
        localBuiltPackages: localBuiltPackages,
      });
      lockFileUpdateTimestamp = latestTimestamp;
    }
    return lockfileJson;
  }

  app.all("/wasm/pyodide-lock.json", async (_req, res) => {
    const lockfileJson = await lockFileGenerator();
    res
      .status(200)
      .setHeader("Content-Type", "application/json")
      .send(lockfileJson);
  });

  app.all(/^\/notebook\/api\/.*$/, (req, res) => {
    const originalUrl = req.url;
    req.url = req.url.replace('/notebook', '');
    console.log(`Rewriting API request from ${originalUrl} to ${req.url}`);
    req.headers.host = `${config.targetHostname}:${config.targetPort}`;
    proxy.web(req, res, { target: targetService });
  });

  app.all("/{*path}", (req, res) => {
    console.log(`Proxying request to: ${targetService}${req.url}`);
    req.headers.host = `${config.targetHostname}:${config.targetPort}`;
    proxy.web(req, res, { target: targetService });
  });

  // Initialize _all_ of the watchers
  for (const watcher of Object.values(watchers)) {
    await watcher.latestBuild();
  }

  const server = app.listen(config.proxyPort, async () => {
    console.log(`Proxy server is running on ${config.proxyHost}:${config.proxyPort}`);
    // Call the postServerStart function with the necessary arguments
    config.postServerStart({
      lockFileGenerator,
      watchers,
      server,
      options: config,
    });
  });
}
