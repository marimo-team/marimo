/* Copyright 2024 Marimo. All rights reserved. */

import { repl } from "@/utils/repl";
import { getRequestClient } from "../network/requests";
import { getResolvedMarimoConfig } from "./config";

// eslint-disable-next-line @typescript-eslint/no-empty-interface
export interface ExperimentalFeatures {
  markdown: boolean; // Used in playground (community cloud)
  inline_ai_tooltip: boolean;
  wasm_layouts: boolean; // Used in playground (community cloud)
  rtc_v2: boolean;
  performant_table_charts: boolean;
  mcp_docs: boolean;
  sql_linter: boolean;
  external_agents: boolean;
  sql_mode: boolean;
  // Add new feature flags here
}

const defaultValues: ExperimentalFeatures = {
  markdown: true,
  inline_ai_tooltip: import.meta.env.DEV,
  wasm_layouts: false,
  rtc_v2: false,
  performant_table_charts: false,
  mcp_docs: false,
  sql_linter: false,
  external_agents: import.meta.env.DEV,
  sql_mode: false,
};

export function getFeatureFlag<T extends keyof ExperimentalFeatures>(
  feature: T,
): ExperimentalFeatures[T] {
  return (
    (getResolvedMarimoConfig()?.experimental?.[
      feature
    ] as ExperimentalFeatures[T]) ?? defaultValues[feature]
  );
}

function setFeatureFlag(feature: keyof ExperimentalFeatures, value: boolean) {
  const userConfig = getResolvedMarimoConfig();
  userConfig.experimental = userConfig.experimental ?? {};
  userConfig.experimental[feature] = value;
  getRequestClient().saveUserConfig({ config: userConfig });
}

export const FeatureFlagged: React.FC<{
  feature: keyof ExperimentalFeatures;
  children: React.ReactNode;
}> = ({ feature, children }) => {
  const value = getFeatureFlag(feature);
  if (value) {
    return children;
  }
  return null;
};

// Allow setting feature flags from the console
repl(setFeatureFlag, "setFeatureFlag");
