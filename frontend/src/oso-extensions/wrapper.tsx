/* Copyright 2024 Marimo. All rights reserved. */
import { useCallback, useEffect, type PropsWithChildren } from "react";
import { useCellActions } from "@/core/cells/cells";
import { PyodideBridge } from "@/core/wasm/bridge";


const COMMAND_PREFIX = "oso_commands:";

/**
 * OSO's wrapper component
 */
export const OSOWrapper: React.FC<PropsWithChildren> = ({ children }) => {
  console.log("Setting up oso wrapper");
  //const config = { column: 0, hide_code: false, disabled: false };

  const actions = useCellActions();
  const createCellAtEnd = (code: string) => {
    actions.createNewCell({
      cellId: "__end__",
      code: code,
      before: false,
    });
  };

  const windowMessageCallback = useCallback((event: MessageEvent<any>) => {
    console.log("Received message:", event.data);
    // Don't really do anything for now.
    if (typeof event.data === "string") {
      if (event.data.startsWith(COMMAND_PREFIX)) {
        // Strip oso commands prefix and parse the remainder as JSON
        const json = event.data.slice(COMMAND_PREFIX.length);
        try {
          const command = JSON.parse(json) as {
            type?: string;
            code?: string;
          };
          if (command?.type === "create_cell") {
            if (command?.code) {
              createCellAtEnd(command.code);
            }
          }
          console.log("Parsed command:", command);
          // Handle the command as needed
        } catch (error) {
          console.error("Failed to parse command:", error);
        }
      }
    }
  }, []);

  // Setup the bridge and inject environment variables
  useEffect(() => {
    const setupBridge = async () => {
      console.log("waiting for bridge to be ready")
      const bridge = PyodideBridge.INSTANCE;
      await bridge.initialized.promise;

      console.log("Bridge initialized");

      window.addEventListener("message", windowMessageCallback);

      // Parse the fragment identifier for the `env` parameter and JSON parse it
      const hash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : window.location.hash;
      const hashParams = new URLSearchParams(hash);
      const envParam = hashParams.get("env");
      let envVars: Record<string, string> = {};
      if (envParam) {
        try {
          envVars = JSON.parse(envParam) as Record<string, string>;
          console.debug("Parsed env vars from query:", envVars);
        } catch (err) {
          console.error("Failed to parse env query parameter:", err);
        }
      }

      // Inject environment variables into Pyodide
      if (Object.keys(envVars).length > 0) {
        const envCode = Object.entries(envVars)
          .map(
        ([key, value]) =>
          `os.environ['${key}'] = '${value.replace(/'/g, "\\'")}'`
          )
          .join("\n");
        await bridge.sendRun({
          cellIds: ["____"],
          codes: [
        `exec("""import os\n${envCode}\n""")\n`,
          ],
        });
      }

      // This will automatically set the database connection. Leaving this here
      // for history in git but this feels a bit too magical as it might not be
      // intended behavior by marimo
      // await bridge.sendRun({
      //   cellIds: ["____"],
      //   codes: [
      //     "import pyoso as _oso\n_oso_client = _oso.Client()\npyoso = _oso_client.dbapi_connection()\n",
      //   ]
      // });
    }
    setTimeout(setupBridge, 0);
    return () => {
      window.removeEventListener("message", windowMessageCallback);
    };
  }, []);

  return children;
};
