/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { Controller, type UseFormReturn } from "react-hook-form";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { userConfigAtom } from "@/core/config/config";
import {
  defaultUserConfig,
  type UserConfig,
} from "@/core/config/config-schema";
import type { EditRequests } from "@/core/network/types";
import {
  activeUserConfigCategoryAtom,
  UserConfigForm,
} from "../user-config-form";

const saveUserConfig = vi.hoisted(() =>
  vi.fn<EditRequests["saveUserConfig"]>(),
);

vi.mock("@uidotdev/usehooks", () => ({ useMediaQuery: () => true }));
vi.mock("@/core/network/requests", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/core/network/requests")>()),
  useRequestClient: () => ({ saveUserConfig }),
}));
vi.mock("../ai-config", () => ({
  AiConfig: ({
    form,
    isSaving,
  }: {
    form: UseFormReturn<UserConfig>;
    isSaving: boolean;
  }) => (
    <>
      <output data-dirty={JSON.stringify(form.formState.dirtyFields)}>
        {isSaving ? "Saving" : "Idle"}
      </output>
      <Controller
        control={form.control}
        name="ai.openrouter.base_url"
        render={({ field }) => (
          <input
            {...field}
            aria-label="Provider URL"
            value={field.value ?? ""}
          />
        )}
      />
    </>
  ),
}));

const originalUrl = "https://original.example.com/v1";
const updatedUrl = "https://updated.example.com/v1";

function setup() {
  const config = defaultUserConfig();
  config.ai = { ...config.ai, openrouter: { base_url: originalUrl } };
  const store = createStore();
  store.set(userConfigAtom, config);
  store.set(activeUserConfigCategoryAtom, "ai");
  render(
    <Provider store={store}>
      <UserConfigForm />
    </Provider>,
  );
  return store;
}

async function changeUrl(url: string) {
  await act(async () =>
    fireEvent.change(screen.getByLabelText("Provider URL"), {
      target: { value: url },
    }),
  );
  await act(async () => vi.advanceTimersByTimeAsync(100));
}

describe("user configuration saving", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    saveUserConfig.mockReset().mockResolvedValue(null);
  });
  afterEach(() => vi.useRealTimers());

  it("saves a revert to the configuration from when settings opened", async () => {
    const store = setup();
    await changeUrl(updatedUrl);
    await changeUrl(originalUrl);
    expect(saveUserConfig).toHaveBeenCalledTimes(2);
    expect(saveUserConfig).toHaveBeenLastCalledWith({
      config: { ai: { openrouter: { base_url: originalUrl } } },
    });
    expect(store.get(userConfigAtom).ai?.openrouter?.base_url).toBe(
      originalUrl,
    );
  });

  it("serializes saves and sends newer edits after an in-flight save completes", async () => {
    const pending = Promise.withResolvers<null>();
    saveUserConfig.mockReturnValueOnce(pending.promise);
    const store = setup();
    await changeUrl(updatedUrl);
    expect(screen.getByRole("status")).toHaveTextContent("Saving");
    await changeUrl(originalUrl);
    expect(saveUserConfig).toHaveBeenCalledOnce();

    await act(async () => pending.resolve(null));
    expect(screen.getByLabelText("Provider URL")).toHaveValue(originalUrl);
    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(saveUserConfig).toHaveBeenCalledTimes(2);
    expect(saveUserConfig).toHaveBeenLastCalledWith({
      config: { ai: { openrouter: { base_url: originalUrl } } },
    });
    expect(store.get(userConfigAtom).ai?.openrouter?.base_url).toBe(
      originalUrl,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Idle");
  });

  it("sends queued edits even when the in-flight save fails", async () => {
    const pending = Promise.withResolvers<null>();
    saveUserConfig.mockReturnValueOnce(pending.promise);
    const store = setup();
    await changeUrl(updatedUrl);
    const latestUrl = "https://latest.example.com/v1";
    await changeUrl(latestUrl);
    expect(saveUserConfig).toHaveBeenCalledOnce();

    await act(async () => pending.reject(new Error("Save failed")));
    await act(async () => vi.advanceTimersByTimeAsync(100));

    expect(saveUserConfig).toHaveBeenCalledTimes(2);
    expect(saveUserConfig).toHaveBeenLastCalledWith({
      config: { ai: { openrouter: { base_url: latestUrl } } },
    });
    expect(store.get(userConfigAtom).ai?.openrouter?.base_url).toBe(latestUrl);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("offers a retry when settings cannot be saved", async () => {
    saveUserConfig.mockRejectedValueOnce(new Error("Save failed"));
    const store = setup();
    await changeUrl(updatedUrl);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Could not save settings.",
    );
    expect(store.get(userConfigAtom).ai?.openrouter?.base_url).toBe(
      originalUrl,
    );

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await act(async () => vi.advanceTimersByTimeAsync(100));

    expect(saveUserConfig).toHaveBeenCalledTimes(2);
    expect(store.get(userConfigAtom).ai?.openrouter?.base_url).toBe(updatedUrl);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
