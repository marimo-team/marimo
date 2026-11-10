/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { defaultUserConfig } from "@/core/config/config-schema";
import { getDirtyValues } from "../get-dirty-values";
import { updateFormDefaults } from "../update-form-defaults";

const originalUrl = "https://original.example.com/v1";
const updatedUrl = "https://updated.example.com/v1";
const field = "ai.openrouter.base_url";

function setup() {
  const config = defaultUserConfig();
  config.ai = { ...config.ai, openrouter: { base_url: originalUrl } };
  return renderHook(() => {
    const form = useForm({ defaultValues: config });
    form.register(field);
    return { form, dirtyFields: form.formState.dirtyFields };
  });
}

describe("updateFormDefaults", () => {
  it("preserves clearing a model list while its previous value is saving", () => {
    const { result } = setup();
    act(() =>
      result.current.form.setValue(
        "ai.models.custom_models",
        ["openai/new-model"],
        { shouldDirty: true },
      ),
    );
    const saved = structuredClone(result.current.form.getValues());
    act(() =>
      result.current.form.setValue("ai.models.custom_models", [], {
        shouldDirty: true,
      }),
    );
    act(() =>
      updateFormDefaults(result.current.form, saved, {
        ai: { models: { custom_models: [true] } },
      }),
    );
    expect(result.current.form.getValues("ai.models.custom_models")).toEqual(
      [],
    );
    expect(
      getDirtyValues(
        result.current.form.getValues(),
        result.current.dirtyFields,
      ),
    ).toEqual({
      ai: { models: { custom_models: [] } },
    });
  });
  it("refreshes untouched settings without including them in the next save", () => {
    const { result } = setup();
    const saved = structuredClone(result.current.form.getValues());
    saved.display.theme = "dark";
    act(() => updateFormDefaults(result.current.form, saved, {}));
    expect(result.current.form.getValues("display.theme")).toBe("dark");
    expect(result.current.dirtyFields).toEqual({});
  });
  it("includes a revert to the original value in the next save", () => {
    const { result } = setup();
    act(() =>
      result.current.form.setValue(field, updatedUrl, { shouldDirty: true }),
    );
    const saved = structuredClone(result.current.form.getValues());
    const fieldsBeingSaved = structuredClone(result.current.dirtyFields);
    act(() => updateFormDefaults(result.current.form, saved, fieldsBeingSaved));
    expect(result.current.dirtyFields).toEqual({});

    act(() =>
      result.current.form.setValue(field, originalUrl, { shouldDirty: true }),
    );
    expect(
      getDirtyValues(
        result.current.form.getValues(),
        result.current.dirtyFields,
      ),
    ).toEqual({
      ai: { openrouter: { base_url: originalUrl } },
    });
  });

  it("keeps edits made during a save dirty against the completed save", () => {
    const { result } = setup();
    act(() =>
      result.current.form.setValue(field, updatedUrl, { shouldDirty: true }),
    );
    const inFlight = structuredClone(result.current.form.getValues());
    const fieldsBeingSaved = structuredClone(result.current.dirtyFields);
    act(() =>
      result.current.form.setValue(field, originalUrl, { shouldDirty: true }),
    );
    expect(result.current.dirtyFields).toEqual({});

    act(() =>
      updateFormDefaults(result.current.form, inFlight, fieldsBeingSaved),
    );
    expect(result.current.form.getValues(field)).toBe(originalUrl);
    expect(
      getDirtyValues(
        result.current.form.getValues(),
        result.current.dirtyFields,
      ),
    ).toEqual({
      ai: { openrouter: { base_url: originalUrl } },
    });
  });
});
