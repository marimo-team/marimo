/* Copyright 2024 Marimo. All rights reserved. */
import { useCallback, useEffect, useState, type PropsWithChildren } from "react";
import { useCellActions } from "@/core/cells/cells";
import { PyodideBridge } from "@/core/wasm/bridge";
import { useFragmentStore } from "./fragment-store";
import { userConfigAtom } from "@/core/config/config";
import { store } from "@/core/state/jotai";
import { runtimeConfigAtom } from "@/core/runtime/config";
import { setLatestEngineSelected, useDataSourceActions } from "@/core/datasets/data-source-connections";
import type { ConnectionName } from "@/core/datasets/engines";
import type { AddCellWithAIHook } from "@/components/editor/ai/add-cell-with-ai";

const COMMAND_PREFIX = "oso_commands:";

declare global {
  interface WindowEventMap {
    'add-cell-with-ai-opened': CustomEvent<AddCellWithAIHook>;
  }
}

/**
 * OSO's wrapper component
 */
export const OSOWrapper: React.FC<PropsWithChildren> = ({ children }) => {
  console.log("Setting up oso wrapper");
  //const config = { column: 0, hide_code: false, disabled: false };

  const [aiGenerateOpened, setAIGenerateOpened] = useState(false);
  const fragmentStore = useFragmentStore();
  const actions = useCellActions();
  const dataSourceActions = useDataSourceActions();
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

  const addCellWithAICallback = useCallback((ev: CustomEvent<AddCellWithAIHook>) => {
    const { setInput } = ev.detail;
    // Given a specific string, send every character to the input one by one
    // with a delay of X ms to simulate typing
    const aiPrompt = fragmentStore.getString("aiPrompt");
    if (aiPrompt) {
      let index = 0;
      const interval = setInterval(() => {
        if (index < aiPrompt.length) {
          setInput(aiPrompt.slice(0, index + 1));
          index++;
        } else {
          clearInterval(interval);
        }
      }, 25);

      setAIGenerateOpened(true);
      return () => clearInterval(interval);
    }
    setAIGenerateOpened(true);
  }, []);

  useEffect(() => {
    if (aiGenerateOpened) {
      return;
    };

    window.addEventListener("add-cell-with-ai-opened", addCellWithAICallback);
    return () => {
      window.removeEventListener("add-cell-with-ai-opened", addCellWithAICallback);
    }
  }, [aiGenerateOpened]);

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
                chat_model: envVars["OSO_AI_MODEL"] || "oso/text2sql",
                edit_model: envVars["OSO_AI_MODEL"] || "oso/text2sql",
                custom_models: [
                  "oso/text2sql",
                  "oso/gemini",
                ],
                displayed_models: ["oso/text2sql", "oso/gemini"],
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

    const setOSOWarehouseAsDefaultSQLConnection = async () => {
      // We may want to change how we do this in the future. It feels a bit
      // hacky but it works to set the default connection to OSO Warehouse at
      // this time. We need to "add" the connection to the store because that
      // doesn't happen if the setup_pyoso cell is the only cell available
      const pyosoSQLConnection = "pyoso_db_conn" as ConnectionName;
      dataSourceActions.addDataSourceConnection({
        connections: [
          {
            name: pyosoSQLConnection,
            dialect: "trino",
            source: "trino",
            display_name: "OSO Warehouse",
            databases: [],
          }
        ]
      })
      setLatestEngineSelected(pyosoSQLConnection);
    }

    setTimeout(setOSOWarehouseAsDefaultSQLConnection, 0);
    return () => {
      window.removeEventListener("message", windowMessageCallback);
    };
  }, []);

  return children;
};
