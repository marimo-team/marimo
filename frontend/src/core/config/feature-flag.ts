/* Copyright 2024 Marimo. All rights reserved. */

import { getUserConfig } from "./config";

// eslint-disable-next-line @typescript-eslint/no-empty-interface
export interface ExperimentalFeatures {
  // None yet
  ai: boolean;
}

const defaultValues: ExperimentalFeatures = {
  ai: process.env.NODE_ENV === "development",
};

export function getFeatureFlag<T extends keyof ExperimentalFeatures>(
  feature: T,
): ExperimentalFeatures[T] {
  return getUserConfig().experimental?.[feature] ?? defaultValues[feature];
}
