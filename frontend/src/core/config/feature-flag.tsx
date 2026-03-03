/* Copyright 2026 Marimo. All rights reserved. */

import { repl } from "@/utils/repl";
import { getRequestClient } from "../network/requests";
import { getResolvedMarimoConfig } from "./config";

// eslint-disable-next-line @typescript-eslint/no-empty-interface
export interface ExperimentalFeatures {
  markdown: boolean; // Used in playground (community cloud)
  wasm_layouts: boolean; // Used in playground (community cloud)
  rtc_v2: boolean;
  cache_panel: boolean;
  external_agents: boolean;
  server_side_pdf_export: boolean;
  storage_inspector: boolean;
  // Add new feature flags here
}

const defaultValues: ExperimentalFeatures = {
  markdown: true,
  wasm_layouts: false,
  rtc_v2: false,
  cache_panel: false,
  external_agents: import.meta.env.DEV,
  server_side_pdf_export: true,
  storage_inspector: false,
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
  // Send only the changed portion to avoid overwriting other config values
  void getRequestClient().saveUserConfig({
    config: { experimental: { [feature]: value } },
  });
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
