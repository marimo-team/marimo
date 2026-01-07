/**
 * Pyodide Acceptance Test
 *
 * This script tests the built marimo wheel in Pyodide to verify basic functionality works.
 *
 * Usage:
 *   node tests/_pyodide/test_pyodide_acceptance.mjs ./dist/marimo-*.whl
 *
 * Exit codes:
 *   0 - Success: session created, bridge verified
 *   1 - Failure: any error during the process
 */

import http from "node:http";
import fs from "node:fs";
import path from "node:path";


/**
 * Start a CORS-enabled HTTP server to serve the wheel file
 */
function startWheelServer(wheelPath) {
  const wheelDir = path.dirname(wheelPath);
  const wheelFilename = path.basename(wheelPath);

  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      // Add CORS headers
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
      res.setHeader("Access-Control-Allow-Headers", "Content-Type");

      if (req.method === "OPTIONS") {
        res.writeHead(200);
        res.end();
        return;
      }

      const requestedFile = req.url?.slice(1); // Remove leading /
      if (requestedFile === wheelFilename) {
        const filePath = path.join(wheelDir, wheelFilename);
        fs.readFile(filePath, (err, data) => {
          if (err) {
            res.writeHead(404);
            res.end("File not found");
            return;
          }
          res.setHeader("Content-Type", "application/zip");
          res.writeHead(200);
          res.end(data);
        });
      } else {
        res.writeHead(404);
        res.end("Not found");
      }
    });

    // Listen on a random available port
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === 'object' && address !== null && 'port' in address ? address.port : 0;
      console.log(`Wheel server started at http://127.0.0.1:${port}`);
      resolve({ server, port, wheelFilename });
    });

    server.on("error", reject);
  });
}

/**
 * Main test function
 */
async function main() {
  // Parse CLI arguments
  const wheelPath = process.argv[2];

  if (!wheelPath) {
    console.error("Usage: node test_pyodide_acceptance.mjs <wheel-path>");
    console.error("Example: node test_pyodide_acceptance.mjs ./dist/marimo-0.1.0-py3-none-any.whl");
    process.exit(1);
  }

  // Resolve to absolute path
  const absoluteWheelPath = path.resolve(wheelPath);

  // Check if wheel file exists
  if (!fs.existsSync(absoluteWheelPath)) {
    console.error(`Error: Wheel file not found: ${absoluteWheelPath}`);
    process.exit(1);
  }

  console.log(`Testing wheel: ${absoluteWheelPath}`);
  console.log("");

  let serverInfo = null;

  try {
    // Step 1: Start wheel server
    console.log("Step 1: Starting wheel server...");
    serverInfo = await startWheelServer(absoluteWheelPath);
    const wheelUrl = `http://127.0.0.1:${serverInfo.port}/${serverInfo.wheelFilename}`;
    console.log(`Wheel URL: ${wheelUrl}`);
    console.log("");

    // Step 2: Load Pyodide
    console.log("Step 2: Loading Pyodide...");
    const { loadPyodide, version } = await import("pyodide");
    console.log(`Pyodide version: ${version}`);

    // In Node.js, loadPyodide uses the bundled files from the npm package
    // Load without packages first, then add packages separately
    const pyodide = await loadPyodide();
    console.log("Pyodide loaded successfully");

    // Load required packages that marimo depends on
    // Some packages are bundled with Pyodide, others need micropip
    console.log("Loading required packages...");

    // Load packages that are bundled with Pyodide
    await pyodide.loadPackage(["micropip", "msgspec", "packaging", "pyodide_http", "docutils", "pygments", "jedi"]);

    // Install packages via micropip that aren't bundled or need specific versions
    // Note: narwhals>=2.0.0 is required by marimo, but Pyodide bundles an older version
    const micropipPackages = ["Markdown", "pymdown-extensions", "narwhals>=2.0.0"];
    console.log(`Installing via micropip: ${micropipPackages.join(", ")}...`);
    await pyodide.runPythonAsync(`
import micropip
await micropip.install(${JSON.stringify(micropipPackages)})
print("micropip packages installed")
`);
    console.log("Required packages loaded");
    console.log("");

    // Step 3: Install the marimo wheel
    console.log("Step 3: Installing marimo wheel...");
    await pyodide.loadPackage(wheelUrl);
    console.log("Marimo wheel installed successfully");
    console.log("");

    // Step 4: Create a minimal notebook file for testing
    console.log("Step 4: Setting up test notebook...");
    pyodide.runPython(`
import os

# Create a minimal test notebook
test_notebook = '''
import marimo

__generated_with = "0.0.0"
app = marimo.App()

@app.cell
def test_cell():
    x = 1 + 1
    return x,

if __name__ == "__main__":
    app.run()
'''

# Write the test notebook to the filesystem
os.makedirs('/home/pyodide', exist_ok=True)
with open('/home/pyodide/test_notebook.py', 'w') as f:
    f.write(test_notebook)

print("Test notebook created at /home/pyodide/test_notebook.py")
`);
    console.log("");

    // Step 5: Create session and verify bridge
    console.log("Step 5: Creating session and verifying bridge...");

    const result = await pyodide.runPythonAsync(`
import json
import asyncio

# Collect messages sent by the session
messages = []

def message_callback(msg):
    messages.append(msg)

# Import and create session
from marimo._pyodide.bootstrap import create_session, instantiate

def init(auto_instantiate=True):
    instantiate(session, auto_instantiate)
    asyncio.create_task(session.start())

session, bridge = create_session(
    filename="/home/pyodide/test_notebook.py",
    query_params={},
    message_callback=message_callback,
    user_config={},
)

# Run the session
init(session)

# Verify session was created
assert session is not None, "Session should not be None"
print(f"Session created: {type(session).__name__}")

# Verify bridge was created
assert bridge is not None, "Bridge should not be None"
print(f"Bridge created: {type(bridge).__name__}")

# Verify bridge has expected methods
expected_methods = [
    "put_control_request",
    "put_input",
    "code_complete",
    "read_code",
    "read_snippets",
    "format",
    "save",
    "save_app_config",
    "save_user_config",
    "rename_file",
    "list_files",
    "search_files",
    "file_details",
    "create_file_or_directory",
    "delete_file_or_directory",
    "move_file_or_directory",
    "update_file",
    "export_html",
    "export_markdown",
]

missing_methods = []
for method in expected_methods:
    if not hasattr(bridge, method):
        missing_methods.append(method)
    else:
        print(f"  - {method}: OK")

if missing_methods:
    raise AssertionError(f"Bridge missing methods: {missing_methods}")

# Sleep until we get two messages (one after kernel-ready)
while len(messages) < 2:
    await asyncio.sleep(0.1)
message_ops = [json.loads(msg)["op"] for msg in messages]

print("Messages received:", message_ops);
kernel_ready_received = "kernel-ready" in message_ops
assert kernel_ready_received, "Should have received kernel-ready message"
print("\\nKernelReady message received: OK")

# Return summary
result = {
    "session_type": type(session).__name__,
    "bridge_type": type(bridge).__name__,
    "methods_verified": len(expected_methods),
    "messages_received": len(messages),
    "kernel_ready": kernel_ready_received,
}
json.dumps(result)
`);

    console.log("");
    console.log("Verification results:", result);
    console.log("");

    // Success
    console.log("=".repeat(50));
    console.log("SUCCESS: All acceptance tests passed!");
    console.log("=".repeat(50));

    // Cleanup
    serverInfo.server.close();
    process.exit(0);
  } catch (error) {
    console.error("");
    console.error("=".repeat(50));
    console.error("FAILURE: Acceptance test failed!");
    console.error("=".repeat(50));
    console.error("");
    console.error("Error:", error.message || error);

    if (error.stack) {
      console.error("");
      console.error("Stack trace:");
      console.error(error.stack);
    }

    // Cleanup
    if (serverInfo?.server) {
      serverInfo.server.close();
    }
    process.exit(1);
  }
}

main();
