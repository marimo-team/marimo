/* Copyright 2024 Marimo. All rights reserved. */

import type { Role } from "@marimo-team/llm-info";
import { useAtom } from "jotai";
import type { QualifiedModelId } from "@/core/ai/ids/ids";
import { userConfigAtom } from "@/core/config/config";
import type { AIModelKey, UserConfig } from "@/core/config/config-schema";
import { useRequestClient } from "@/core/network/requests";

// Extract only the supported roles from the Role type
type SupportedRole = Extract<Role, "chat" | "autocomplete" | "edit">;

const getModelKeyForRole = (forRole: SupportedRole): AIModelKey | null => {
  switch (forRole) {
    case "chat":
      return "chat_model";
    case "autocomplete":
      return "autocomplete_model";
    case "edit":
      return "edit_model";
  }
};

/**
 * Hook for saving model and mode changes.
 */
export const useModelChange = () => {
  const [userConfig, setUserConfig] = useAtom(userConfigAtom);
  const { saveUserConfig } = useRequestClient();

  const saveConfig = async (newConfig: UserConfig) => {
    await saveUserConfig({ config: newConfig }).then(() => {
      setUserConfig(newConfig);
    });
  };

  const saveModelChange = async (
    model: QualifiedModelId,
    forRole: SupportedRole,
  ) => {
    const modelKey = getModelKeyForRole(forRole);

    if (!modelKey) {
      return;
    }

    const newConfig: UserConfig = {
      ...userConfig,
      ai: {
        ...userConfig.ai,
        models: {
          custom_models: userConfig.ai?.models?.custom_models ?? [],
          displayed_models: userConfig.ai?.models?.displayed_models ?? [],
          ...userConfig.ai?.models,
          [modelKey]: model,
        },
      },
    };

    saveConfig(newConfig);
  };

  const saveModeChange = async (newMode: "ask" | "manual") => {
    const newConfig: UserConfig = {
      ...userConfig,
      ai: {
        ...userConfig.ai,
        mode: newMode,
      },
    };

    saveConfig(newConfig);
  };

  return { saveModelChange, saveModeChange };
};
