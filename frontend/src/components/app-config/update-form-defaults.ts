/* Copyright 2026 Marimo. All rights reserved. */

import type { FieldPath, FormState, UseFormReturn } from "react-hook-form";
import type { UserConfig } from "@/core/config/config-schema";

type DirtyFields = FormState<UserConfig>["dirtyFields"];

function dirtyPaths(fields: unknown, prefix = ""): FieldPath<UserConfig>[] {
  if (fields === true && prefix) {
    return [prefix as FieldPath<UserConfig>];
  }
  if (!fields || typeof fields !== "object") {
    return [];
  }
  const paths = Object.entries(fields).flatMap(([key, value]) =>
    dirtyPaths(value, prefix ? `${prefix}.${key}` : key),
  );
  if (Array.isArray(fields) && paths.length > 0 && prefix) {
    return [prefix as FieldPath<UserConfig>];
  }
  return paths;
}

export function updateFormDefaults(
  form: UseFormReturn<UserConfig>,
  savedConfig: UserConfig,
  fieldsBeingSaved: DirtyFields,
) {
  const paths = new Set([
    ...dirtyPaths(fieldsBeingSaved),
    ...dirtyPaths(form.formState.dirtyFields),
  ]);
  const edits = [...paths].map((path) => ({
    path,
    value: form.getValues(path),
  }));
  form.reset(savedConfig, { keepTouched: true, keepErrors: true });
  // Preserve newer edits, including reverts to the previous defaults.
  for (const { path, value } of edits) {
    form.setValue(path, value, { shouldDirty: true });
  }
  return [...paths].some((path) => form.getFieldState(path).isDirty);
}
