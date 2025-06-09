/* Copyright 2024 Marimo. All rights reserved. */

import { repl } from "@/utils/repl";
import type { UserConfig } from "vite";
import { saveUserConfig } from "../network/requests";
import { getResolvedMarimoConfig } from "./config";

// eslint-disable-next-line @typescript-eslint/no-empty-interface
export interface ExperimentalFeatures {
  inline_ai_tooltip: boolean;
  rtc_v2: boolean;
  table_charts: boolean;
  // Add new feature flags here
}

const defaultValues: ExperimentalFeatures = {
  inline_ai_tooltip: import.meta.env.DEV,
  rtc_v2: false,
  table_charts: false,
};

export function getFeatureFlag<T extends keyof ExperimentalFeatures>(
  feature: T,
): ExperimentalFeatures[T] {
  return (
    (getResolvedMarimoConfig().experimental?.[
      feature
    ] as ExperimentalFeatures[T]) ?? defaultValues[feature]
  );
}

function setFeatureFlag(
  feature: keyof UserConfig["experimental"],
  value: boolean,
) {
  const userConfig = getResolvedMarimoConfig();
  userConfig.experimental = userConfig.experimental ?? {};
  userConfig.experimental[feature] = value;
  saveUserConfig({ config: userConfig });
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
