/* Copyright 2024 Marimo. All rights reserved. */

import { getUserConfig } from "./config";

export interface ExperimentalFeatures {
  /**
   * Allows the user to switch between different layouts.
   */
  layouts: boolean;
}

const defaultValues: ExperimentalFeatures = {
  layouts: false,
};

export function getFeatureFlag<T extends keyof ExperimentalFeatures>(
  feature: T,
): ExperimentalFeatures[T] {
  return getUserConfig().experimental?.[feature] ?? defaultValues[feature];
}
