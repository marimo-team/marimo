/* Copyright 2024 Marimo. All rights reserved. */
import { getFeatureFlag } from "./feature-flag";

export function getAppWidths() {
  return getFeatureFlag("multi_column")
    ? (["compact", "medium", "full", "columns"] as const)
    : (["compact", "medium", "full"] as const);
}
