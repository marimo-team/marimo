/* Copyright 2023 Marimo. All rights reserved. */

import { getUserConfig } from "./config";

export interface ExperimentalFeatures {
  /**
   * Allows the user to switch between different layouts.
   */
  layouts: boolean;
  /**
   * Allows the user to export the notebook as a static HTML file.
   */
  static_export: boolean;
}

const defaultValues: ExperimentalFeatures = {
  layouts: false,
  static_export: false,
};

export function getFeatureFlag<T extends keyof ExperimentalFeatures>(
  feature: T
): ExperimentalFeatures[T] {
  return getUserConfig().experimental?.[feature] ?? defaultValues[feature];
}
