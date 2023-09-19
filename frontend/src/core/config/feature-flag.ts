/* Copyright 2023 Marimo. All rights reserved. */

import { getUserConfig } from "../state/config";

export interface ExperimentalFeatures {
  /**
   * Allows the user to switch between light and dark themes.
   */
  theming: boolean;
  /**
   * Allows the user to switch between different layouts.
   */
  layouts: boolean;
}

const defaultValues: ExperimentalFeatures = {
  theming: false,
  layouts: false,
};

export function getFeatureFlag<T extends keyof ExperimentalFeatures>(
  feature: T
): ExperimentalFeatures[T] {
  return getUserConfig().experimental?.[feature] ?? defaultValues[feature];
}
