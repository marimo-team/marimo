import yargs from "yargs";
import { hideBin } from "yargs/helpers";
import fsPromises from "node:fs/promises";
import { startServer, type BuildOptions } from "./server";
import path from "node:path";
import type { ArgumentsCamelCase } from "yargs";

type WasmTesterArgs = ArgumentsCamelCase<BuildOptions>;

const cli = yargs(hideBin(process.argv))
  .option("target-hostname", {
    description: "The hostname of the target server",
    type: "string",
    default: process.env.TARGET_HOSTNAME || "127.0.0.1",
  })
  .option("target-scheme", {
    description: "The scheme of the target server",
    type: "string",
    default: process.env.TARGET_HOST_SCHEME || "http",
  })
  .option("target-port", {
    description: "The port of the target server",
    type: "number",
    default: parseInt(process.env.TARGET_PORT || "3000"),
  })
  .option("public-packages-scheme", {
    description: "The scheme for public packages",
    type: "string",
    default: process.env.PUBLIC_PACKAGES_SCHEME || "http",
  })
  .option("public-packages-host", {
    description: "The host for public packages",
    type: "string",
    default: process.env.PUBLIC_PACKAGES_HOST || "127.0.0.1",
  })
  .option("public-packages-port", {
    description: "The port for public packages",
    type: "number",
    default: parseInt(process.env.PUBLIC_PACKAGES_PORT || "6008"),
  })
  .option("public-packages-base-path", {
    description: "The base path for public packages",
    type: "string",
    default: process.env.PUBLIC_PACKAGES_BASE_PATH || "",
  })
  .option("proxy-host", {
    description: "The host for the proxy server",
    type: "string",
    default: process.env.PROXY_HOST || "127.0.0.1",
  })
  .option("proxy-port", {
    description: "The port for the proxy server",
    type: "number",
    default: parseInt(process.env.PROXY_PORT || "6008"),
  })
  .option("oso-api-key", {
    description: "The OSO API key",
    type: "string",
    default: process.env.OSO_API_KEY || "",
  })
  .option("other-uv-packages-to-include", {
    description: "Other UV packages to include",
    type: "string",
    default: process.env.OTHER_UV_PACKAGES_TO_INCLUDE || "[]",
  })
  .option("marimo-repo-dir", {
    description: "The path to the marimo repo",
    type: "string",
    default: process.env.MARIMO_REPO_DIR,
  })
  .command<WasmTesterArgs>(
    "serve",
    "Start the server",
    () => {},
    (argv) => {
      startServer({
        ...argv,
        postServerStart: async ({lockFileGenerator}) => {
          // Do something with the lockfileGenerator, watchers, and option
          // Build the initial pyodide lock file
          await lockFileGenerator();

          console.log("Initial pyodide-lock.json generated");
        },
      });
    }
  )
  .command<WasmTesterArgs & { isProduction: boolean, outputDir: string }>(
    "build",
    "Build the project for production",
    (yargs) => {
      yargs.option("is-production", {
        description: "Whether the build is for production",
        type: "boolean",
        default: false,
      }).option("output-dir", {
        description: "The output directory for the built project",
        type: "string",
        demandOption: true,
      });
    },
    (argv) => {
      // Assert that the public host is not localhost
      if (argv.isProduction) {
        if (argv.publicPackagesHost === "localhost") {
          throw new Error("Public packages host cannot be localhost");
        }
        if (argv.publicPackagesScheme === "http") {
          console.warn("Public packages host should not be http. Rewriting as https")
          argv.publicPackagesScheme = "https";
        }
        // Force port 443
        argv.publicPackagesPort = 443;

        // Ignore additional packages
        argv.otherUvPackagesToInclude = '[]';

      }

      startServer({
        ...argv,
        postServerStart: async ({lockFileGenerator, watchers, server}) => {
          // Output the lock file to the output dir
          const outputDir = argv.outputDir;
          
          // Build the initial pyodide lock file
          const lockfileContent = await lockFileGenerator();
          // Write out lockfile
          const lockfilePath = path.join(outputDir, "pyodide-lock.json");
          await fsPromises.writeFile(lockfilePath, lockfileContent);

          // Gather all the wheels
          const pathsToWheels: Array<string> = [];
          for (const watcherName in watchers) {
            const watcher = watchers[watcherName];
            const builtWheel = await watcher.latestBuild();
            pathsToWheels.push(builtWheel.path);
          }

          // Copy all the wheels into the output directory
          for (const wheelPath of pathsToWheels) {
            const destPath = path.join(outputDir, path.basename(wheelPath));
            await fsPromises.copyFile(wheelPath, destPath);
            console.log(`Copied wheel: ${wheelPath} to ${destPath}`);
          }

          // kill the server
          server.close();
          server.closeAllConnections();
          console.log("Build complete")
          process.exit(0);
        },
      });
    }
  )
  .demandCommand(1, "You need at least one command before moving on")
  .help();

async function main() {
  await cli.parseAsync();
}

main().catch(console.error);
