/* Copyright 2024 Marimo. All rights reserved. */
import { useCallback, useEffect, type PropsWithChildren } from "react";
import { useCellActions } from "@/core/cells/cells";
import { PyodideBridge } from "@/core/wasm/bridge";
import type { FragmentStore } from "./fragment-store";

const COMMAND_PREFIX = "oso_commands:";

interface WrapperProps {
  fragmentStore: FragmentStore
}

/**
 * OSO's wrapper component
 */
export const OSOWrapper: React.FC<PropsWithChildren<WrapperProps>> = ({ children, fragmentStore }) => {
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
      const envVars = fragmentStore.getJSON<Record<string, string>>("env") || {};

      // Inject environment variables into Pyodide
      if (Object.keys(envVars).length > 0) {
        await bridge.sendFunctionRequest({
          args: {
            env: envVars
          },
          functionCallId: "__oso_initialize_env",
          functionName: "__oso_initialize_env",
          namespace: "marimo.oso"
        });
      }
    }
    setTimeout(setupBridge, 0);
    return () => {
      window.removeEventListener("message", windowMessageCallback);
    };
  }, []);

  return children;
};
