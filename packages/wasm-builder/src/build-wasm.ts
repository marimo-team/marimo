import * as util from 'node:util';
import fs from "node:fs";
import fsPromises from "node:fs/promises";
import { exec } from 'node:child_process';
import { loadPyodide } from 'pyodide';
import { parse, type TomlTable } from 'smol-toml'
import { minimatch } from 'minimatch';
import path from "node:path";


// Promisify exec
const execPromise = util.promisify(exec);

export interface PyodideLockFileOptions {
  /** Additional packages to include in the lock file. Default: [] */
  packages?: string[];

  localBuiltPackages: Record<string, BuiltWheelWithUrls>;
}

export type BuiltWheel = {
  path: string;
  timestamp: number;
}

export type BuiltWheelWithUrls = BuiltWheel & {
  publishedWheelUrl: string;
  localWheelUrl: string;
}

export interface WasmRebuilder {
  pathToWatch: string;
  // glob patterns to match
  filesToWatch: string[];
  rebuild(): Promise<BuiltWheel>;
}

export class GenericWatcher {
  private rebuilder: WasmRebuilder;
  private requiresRebuild: boolean;
  private builtWheel: BuiltWheel | null;
  private buildPromise: Promise<BuiltWheel> | null = null;

  constructor(rebuilder: WasmRebuilder) {
    this.rebuilder = rebuilder;
    this.requiresRebuild = true;
    this.builtWheel = null;
  }

  static create(rebuilder: WasmRebuilder): GenericWatcher {
    const watcher = new GenericWatcher(rebuilder);
    watcher.watchFiles();
    return watcher;
  }

  get is_ready(): boolean {
    return !this.requiresRebuild;
  }

  watchFiles() {
    console.log(`Watching for file changes in ${this.rebuilder.pathToWatch}`);
    fs.watch(this.rebuilder.pathToWatch, {recursive: true }, (event, filename) => {
      // Check if the filename matches any of the patterns in filesToWatch
      if (!filename) {
        return;
      }
      if (this.rebuilder.filesToWatch.some(pattern => minimatch(filename, pattern))) {
        this.requiresRebuild = true;
        console.log(`File changed: ${filename}`);
      }
    });
  }

  async latestBuild(): Promise<BuiltWheel> {
    // We store buildPromise to avoid multiple simultaneous builds
    if (this.requiresRebuild && !this.buildPromise) {
      console.log(`Rebuilding ${this.rebuilder.pathToWatch}`);
      this.buildPromise = (async () => {
        const wheel = await this.rebuilder.rebuild();
        this.builtWheel = wheel;
        this.requiresRebuild = false;
        this.buildPromise = null;
        return wheel;
      })();
    }
    if (this.buildPromise) {
      return await this.buildPromise;
    }
    return this.builtWheel!;
  }
}

// Current directory
export async function buildMarimoForWasm(repoDir: string) {
  const command = 'bash scripts/build_marimo_base_on_host.sh';
  const output = await execPromise(command, { cwd: repoDir });
  // Find the line `BUILD COMPLETE: <filename>` in the output
  const match = output.stdout.match(/BUILD COMPLETE: (.+\.whl)/);
  if (!match) {
    console.error("Build output:", output.stdout);
    console.error("Build error output:", output.stderr);
    throw new Error("Build failed or unexpected output");
  }

  if (match.length < 2) {
    throw new Error("Unexpected build output format");
  }

  const wheelFile = match[1].trim();
  console.log(`Built wheel file: ${wheelFile}`);
  const wheelPath = path.join(repoDir, ".wasmbuilds", wheelFile);
  return wheelPath;
}

export function createMarimoWatcher(repoDir: string) {
  const watcher = GenericWatcher.create({
    pathToWatch: path.join(repoDir, "marimo"),
    filesToWatch: ["**/*.py"],
    rebuild: async () => {
      const wheelPath = await buildMarimoForWasm(repoDir);
      return {
        path: wheelPath,
        timestamp: Date.now(),
      };
    },
  });
  return watcher;
}

export async function buildPyodideLockFile(options: PyodideLockFileOptions) {
  // Load pyodide 
  const pyodide = await loadPyodide();
  await pyodide.loadPackage("micropip");


  const packages = (options.packages || []).concat([
    "Markdown",
    "pymdown-extensions",
    "narwhals",
    "packaging",
  ]);

  // If any packages in the package list are in the localBuiltPackages, replace them with the localWheelUrl
  for (const [name, built] of Object.entries(options.localBuiltPackages)) {
    if (packages.includes(name)) {
      packages[packages.indexOf(name)] = built.localWheelUrl;
    }

    // If the package doesn't appear in the list add it anyway
    if (!packages.includes(name)) {
      packages.push(built.localWheelUrl);
    }
  }

  if (packages.length > 0) {
    const locals = pyodide.toPy({ packages: packages });
    await pyodide.runPythonAsync(`
      import micropip
      for pkg in packages:
          print(f"Installing {pkg}")
          await micropip.install(pkg)
    `, { locals });
  }

  // Generate the lock file
  const lockFile = await pyodide.runPythonAsync(`
      import json
      import micropip
      micropip.freeze()
  `);

  // Rewrite the lock file to use the proxy hostname for marimo-base
  const lockFileJson = JSON.parse(lockFile);
  if (!lockFileJson.packages) {
    throw new Error("Invalid lock file format: missing 'packages' key");
  }
  // Rewrite all of the local packages in the lock file
  for (const [name, built] of Object.entries(options.localBuiltPackages)) {
    const alternativeName = name.replace(/_/g, "-");
    console.log(`Checking ${name}`);
    if (lockFileJson.packages[name]) {
      console.log(`Replacing ${name} with ${built.publishedWheelUrl}`);
      const pkg = lockFileJson.packages[name];
      pkg.file_name = built.publishedWheelUrl;
      lockFileJson.packages[name] = pkg;
      console.log(`${JSON.stringify(pkg)}`)
    }
    if (lockFileJson.packages[alternativeName]) {
      console.log(`Replacing ${alternativeName} with ${built.publishedWheelUrl}`);
      const pkg = lockFileJson.packages[alternativeName];
      pkg.file_name = built.publishedWheelUrl;
      lockFileJson.packages[alternativeName] = pkg;
    }
  }

  // Specifically for marimo_only
  if (lockFileJson.packages["marimo-base"]) {
    const marimoBaseProject = lockFileJson.packages["marimo-base"];
    marimoBaseProject.name = "marimo";
    lockFileJson.packages.marimo = marimoBaseProject;
    lockFileJson.packages["marimo-base"] = marimoBaseProject;
  } else {
    throw new Error("marimo-base not found in lock file packages");
  }
  return JSON.stringify(lockFileJson);
}

export interface PurePythonUVProjectBuildOptions {
  /** The directory containing the project files */
  projectDir: string;
  /** The output directory for the built project */
  outputDir: string;
  /** Additional environment variables to set during the build */
  env?: Record<string, string>;
}

export async function createUVProjectWatcher(options: PurePythonUVProjectBuildOptions): Promise<GenericWatcher> {
  // Parse the pyproject.toml file

  const watcher = GenericWatcher.create({
    pathToWatch: options.projectDir,
    filesToWatch: ["*.py", "**/*.py"],
    rebuild: async () => {
      console.log(`Rebuilding ${options.projectDir}`)
      const pyproject = parse(fs.readFileSync(path.join(options.projectDir, "pyproject.toml"), "utf-8"));
      // Get the project version
      const project = pyproject?.project as TomlTable;
      if (!project) {
        throw new Error("Invalid pyproject.toml: missing [project] section");
      }
      if (!project.version) {
        throw new Error("Invalid pyproject.toml: [project.version] is required");
      }

      // Run the build
      if (!project.name) {
        throw new Error("Invalid pyproject.toml: [project.name] is required");
      }

      // wheel file names replace `-` with `_`
      const projectName = project.name as string;
      const wheelName = projectName.replace(/-/g, "_");

      const wheelPath = path.join(options.outputDir, `${wheelName}-${project.version}-py3-none-any.whl`);

      if (fs.existsSync(wheelPath)) {
        // Remove any old builds with the same name
        console.log("removing old build with same version and name:", wheelPath);
        await fsPromises.rm(wheelPath);
      }

      const command = 'uv build';
      const env = { ...process.env, ...(options.env || {}) };
      const output = await execPromise(command, { cwd: options.projectDir, env });
      console.log("Build stdout:", output.stdout);
      console.error("Build stderr:", output.stderr);

      // Check the outputDirectory for the built wheel file
      if (!fs.existsSync(wheelPath)) {
        throw new Error(`Build failed: ${wheelPath} not found`);
      }

      return {
        path: wheelPath,
        timestamp: Date.now(),
      }
    },
  });
  return watcher;
}