/* Copyright 2024 Marimo. All rights reserved. */

import type { Role } from "@marimo-team/llm-info";
import { useAtom } from "jotai";
import type { QualifiedModelId } from "@/core/ai/ids/ids";
import { userConfigAtom } from "@/core/config/config";
import type { AIModelKey, UserConfig } from "@/core/config/config-schema";
import { useRequestClient } from "@/core/network/requests";

// Extract only the supported roles from the Role type
export type SupportedRole = Extract<Role, "chat" | "autocomplete" | "edit">;

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
 * Strip Bedrock inference profile prefix from a model ID.
 *
 * Bedrock models can have inference profile prefixes like "us.", "eu.", or "global."
 * We need to strip these before storing the model ID, as the profiles are stored
 * separately in the bedrock_inference_profiles mapping.
 *
 * @example
 * stripBedrockInferenceProfile("bedrock/us.claude-3-5-sonnet-latest")
 * // returns "bedrock/claude-3-5-sonnet-latest"
 *
 * @param modelId - The qualified model ID (e.g., "bedrock/us.claude-3-5-sonnet-latest")
 * @returns The model ID without the inference profile prefix
 */
const stripBedrockInferenceProfile = (
  modelId: QualifiedModelId,
): QualifiedModelId => {
  if (!modelId.startsWith("bedrock/")) {
    return modelId;
  }

  const parts = modelId.split("/");
  if (parts.length !== 2) {
    return modelId;
  }

  let shortModel = parts[1];
  const validPrefixes = ["us.", "eu.", "global."];

  for (const prefix of validPrefixes) {
    if (shortModel.startsWith(prefix)) {
      shortModel = shortModel.slice(prefix.length);
      break;
    }
  }

  return `bedrock/${shortModel}` as QualifiedModelId;
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

    // Strip Bedrock inference profile prefix before saving the model ID
    // Profiles are stored separately in bedrock_inference_profiles
    const modelIdToSave = stripBedrockInferenceProfile(model);

    const newConfig: UserConfig = {
      ...userConfig,
      ai: {
        ...userConfig.ai,
        models: {
          custom_models: userConfig.ai?.models?.custom_models ?? [],
          displayed_models: userConfig.ai?.models?.displayed_models ?? [],
          ...userConfig.ai?.models,
          [modelKey]: modelIdToSave,
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
