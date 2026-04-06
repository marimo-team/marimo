/* Copyright 2026 Marimo. All rights reserved. */

import type { FieldPath, FieldValues } from "react-hook-form";
import type { UserConfig } from "@/core/config/config-schema";

/**
 * Extract only the values that have been modified (dirty) from form state.
 * This prevents sending unchanged fields that could overwrite backend values.
 */
export function getDirtyValues<T extends FieldValues>(
  values: T,
  dirtyFields: Partial<Record<keyof T, unknown>>,
): Partial<T> {
  const result: Partial<T> = {};
  for (const key of Object.keys(dirtyFields) as (keyof T)[]) {
    const dirty = dirtyFields[key];
    const value = values[key];

    // Skip if the value no longer exists (e.g., deleted from a record)
    if (value === undefined) {
      continue;
    }

    if (dirty === true) {
      result[key] = value;
    } else if (typeof dirty === "object" && dirty !== null) {
      // Nested object - recurse
      const nested = getDirtyValues(
        value as FieldValues,
        dirty as Partial<Record<string, unknown>>,
      );
      if (Object.keys(nested).length > 0) {
        result[key] = nested as T[keyof T];
      }
    }
  }
  return result;
}

type ManualInjector = (
  values: UserConfig,
  dirtyValues: Partial<UserConfig>,
) => void;

const modelsAiInjection = (
  values: UserConfig,
  dirtyValues: Partial<UserConfig>,
) => {
  dirtyValues.ai = {
    ...dirtyValues.ai,
    models: {
      ...dirtyValues.ai?.models,
      displayed_models: values.ai?.models?.displayed_models ?? [],
      custom_models: values.ai?.models?.custom_models ?? [],
    },
  };
};

// Some fields (like AI model lists) have empty arrays as default values.
// If a user explicitly clears them, RHF won't mark them dirty, so we use
// touchedFields to force-include those values in the payload.
const MANUAL_INJECT_ENTRIES = [
  ["ai.models.displayed_models", modelsAiInjection],
  ["ai.models.custom_models", modelsAiInjection],
] as const satisfies readonly (readonly [
  FieldPath<UserConfig>,
  ManualInjector,
])[];

const MANUAL_INJECT_FIELDS = new Map(MANUAL_INJECT_ENTRIES);

const isTouchedPath = (
  touched: unknown,
  path: FieldPath<UserConfig>,
): boolean => {
  if (!touched) {
    return false;
  }
  let current: unknown = touched;
  for (const segment of path.split(".")) {
    if (typeof current !== "object" || current === null) {
      return false;
    }
    current = (current as Record<string, unknown>)[segment];
  }
  return current === true;
};

export const applyManualInjections = (opts: {
  values: UserConfig;
  dirtyValues: Partial<UserConfig>;
  touchedFields: unknown;
}) => {
  const { values, dirtyValues, touchedFields } = opts;
  for (const [fieldPath, injector] of MANUAL_INJECT_FIELDS) {
    if (isTouchedPath(touchedFields, fieldPath)) {
      injector(values, dirtyValues);
    }
  }
};
