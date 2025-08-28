import * as util from 'node:util';
import { exec } from 'node:child_process';
import { loadPyodide } from 'pyodide';

// Promisify exec
const execPromise = util.promisify(exec);

export interface PyodideLockFileOptions {
  /** The hostname to use in the lock file for the marimo-base package. Default: 'localhost' */
  publishedWheelUrl: string;
  /** The URL to the marimo-base wheel file. Default: 'http://localhost:6000/marimo_base-<version>-py3-none-any.whl' */
  localWheelUrl: string;
  /** Additional packages to include in the lock file. Default: [] */
  packages?: string[];
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
  return wheelFile;
}

export async function buildPyodideLockFile(options: PyodideLockFileOptions) {
  // Load pyodide 
  const pyodide = await loadPyodide();
  await pyodide.loadPackage("micropip");
  await pyodide.loadPackage(options.localWheelUrl);
  const packages = (options.packages || []).concat([
    options.localWheelUrl,
    "Markdown",
    "pymdown-extensions",
    "narwhals",
    "packaging",
  ]);
  if (packages.length > 0) {
    const locals = pyodide.toPy({ packages: packages });
    await pyodide.runPythonAsync(`
      import micropip
      for pkg in packages:
          print(f"Installing {pkg}")
          await micropip.install(pkg)
      print("All packages installed")
      print(micropip.list())
    `, { locals });
  }

  // Generate the lock file
  const lockFile = await pyodide.runPythonAsync(`
      import json
      import micropip
      print("relist?")
      print(micropip.list())
      micropip.freeze()
  `);

  // Rewrite the lock file to use the proxy hostname for marimo-base
  const lockFileJson = JSON.parse(lockFile);
  if (!lockFileJson.packages) {
    throw new Error("Invalid lock file format: missing 'packages' key");
  }
  if (lockFileJson.packages["marimo-base"]) {
    const marimoBaseProject = lockFileJson.packages["marimo-base"];
    marimoBaseProject.name = "marimo";
    // Replace the hostname in the file_name URL
    marimoBaseProject.file_name = options.publishedWheelUrl;
    lockFileJson.packages.marimo = marimoBaseProject;
    lockFileJson.packages["marimo-base"] = marimoBaseProject;

  } else {
    throw new Error("marimo-base not found in lock file packages");
  }
  return JSON.stringify(lockFileJson);
}
