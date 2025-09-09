/* Copyright 2024 Marimo. All rights reserved. */
import { useCallback, useEffect, type PropsWithChildren } from "react";
import { useCellActions } from "@/core/cells/cells";
import { PyodideBridge } from "@/core/wasm/bridge";
import { useFragmentStore } from "./fragment-store";
import { userConfigAtom } from "@/core/config/config";
import { store } from "@/core/state/jotai";
import { runtimeConfigAtom } from "@/core/runtime/config";

const COMMAND_PREFIX = "oso_commands:";

/**
 * OSO's wrapper component
 */
export const OSOWrapper: React.FC<PropsWithChildren> = ({ children }) => {
  console.log("Setting up oso wrapper");
  //const config = { column: 0, hide_code: false, disabled: false };

  const fragmentStore = useFragmentStore();
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
      const envVars = fragmentStore.getJSON<Record<string, string>>("env", {});

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

        const osoApiKey = envVars["OSO_API_KEY"];
        if (osoApiKey) {
          store.set(userConfigAtom, (prev) => ({
            ...prev,
            ai: {
              ...prev.ai,
              open_ai_compatible: {
                ...prev.ai?.open_ai_compatible,
                api_key: osoApiKey,
                base_url: envVars["OSO_AI_API_BASE_URL"] || "https://opensource.observer/api/v1",
              },
              models: {
                ...prev.ai?.models,
                chat_model: envVars["OSO_AI_MODEL"] || "oso/semantic",
                edit_model: envVars["OSO_AI_MODEL"] || "oso/semantic",
                custom_models: prev.ai?.models?.custom_models || [],
                displayed_models: prev.ai?.models?.displayed_models || [],
              },
            },
          }));

          // Set the OSO API key as the auth token in the runtime config
          store.set(runtimeConfigAtom, (prev) => ({
            ...prev,
            authToken: osoApiKey,
          }));
        }
      }

      // Enable debug logging in pyodide. This could get crazy
      if (fragmentStore.getBoolean("debug")) {
        await bridge.sendFunctionRequest({
          args: {},
          functionCallId: "__oso_enable_debug_logging",
          functionName: "__oso_enable_debug_logging",
          namespace: "marimo.oso"
        });
      }
    };
    setTimeout(setupBridge, 0);
    return () => {
      window.removeEventListener("message", windowMessageCallback);
    };
  }, []);

  return children;
};
