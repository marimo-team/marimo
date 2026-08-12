/* Copyright 2026 Marimo. All rights reserved. */

import type { Role } from "@marimo-team/llm-info";
import { useSetAtom } from "jotai";
import { merge } from "lodash-es";
import type { QualifiedModelId } from "@/core/ai/ids/ids";
import { userConfigAtom } from "@/core/config/config";
import type {
  AiCapability,
  AIModelKey,
  CopilotMode,
  UserConfig,
} from "@/core/config/config-schema";
import { useRequestClient } from "@/core/network/requests";

// Extract only the supported roles from the Role type
export type SupportedRole = Extract<Role, "chat" | "autocomplete" | "edit">;

interface AiConfigPatch {
  capabilities?: Partial<
    NonNullable<NonNullable<UserConfig["ai"]>["capabilities"]>
  >;
  mode?: CopilotMode;
  models?: Partial<NonNullable<NonNullable<UserConfig["ai"]>["models"]>>;
}

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
 * Hook for saving AI config changes
 */
export const useAIConfigActions = () => {
  const setUserConfig = useSetAtom(userConfigAtom);
  const { saveUserConfig } = useRequestClient();

  const saveConfig = async (aiConfig: AiConfigPatch) => {
    const newConfig = { ai: aiConfig };
    await saveUserConfig({ config: newConfig }).then(() => {
      setUserConfig((prev) => merge({}, prev, newConfig));
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

    const newConfig: AiConfigPatch = {
      models: { [modelKey]: model },
    };

    await saveConfig(newConfig);
  };

  const saveModeChange = async (newMode: CopilotMode) => {
    const newConfig: AiConfigPatch = { mode: newMode };

    await saveConfig(newConfig);
  };

  const saveCapabilityChange = async (
    capability: AiCapability,
    enabled: boolean,
  ) => {
    const newConfig: AiConfigPatch = {
      capabilities: { [capability]: enabled },
    };

    await saveConfig(newConfig);
  };

  return { saveModelChange, saveModeChange, saveCapabilityChange };
};
