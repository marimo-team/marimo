/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { Controller, useForm } from "react-hook-form";
import { describe, expect, it, vi } from "vitest";
import { userConfigAtom } from "@/core/config/config";
import {
  defaultUserConfig,
  type UserConfig,
} from "@/core/config/config-schema";
import { listProviderModels } from "@/core/network/ai";
import type { EditRequests } from "@/core/network/types";
import { AddModelForm } from "../ai-config";
import { aiSettingsSubTabAtom, pendingConfigSavesAtom } from "../state";
import {
  activeUserConfigCategoryAtom,
  UserConfigForm,
} from "../user-config-form";

const saveUserConfig = vi.hoisted(() =>
  vi.fn<EditRequests["saveUserConfig"]>(),
);

vi.mock("@/core/network/ai", () => ({ listProviderModels: vi.fn() }));
vi.mock("@/core/network/requests", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/core/network/requests")>()),
  useRequestClient: () => ({ saveUserConfig }),
}));
vi.mock("@uidotdev/usehooks", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@uidotdev/usehooks")>()),
  useMediaQuery: () => true,
}));

Element.prototype.scrollIntoView = vi.fn();

const search = () =>
  screen.getByRole("button", { name: "Search available models" });

async function openAddModel(providerName: string) {
  fireEvent.click(screen.getByRole("button", { name: "Add model" }));
  fireEvent.click(screen.getByRole("combobox"));
  fireEvent.click(
    await screen.findByRole("option", {
      name: new RegExp(providerName, "i"),
    }),
  );
}

function ModelForm({
  providerName,
  savedConfig,
  onSubmit,
}: {
  providerName: string;
  savedConfig: UserConfig;
  onSubmit: (config: UserConfig) => void;
}) {
  const form = useForm<UserConfig>({ defaultValues: savedConfig });
  return (
    <>
      <Controller
        control={form.control}
        name={`ai.custom_providers.${providerName}.api_key`}
        render={() => <span />}
      />
      <button
        type="button"
        onClick={() =>
          form.setValue(
            `ai.custom_providers.${providerName}.base_url`,
            "https://changed.example.com/v1",
          )
        }
      >
        Change URL
      </button>
      <AddModelForm
        form={form}
        config={savedConfig}
        customModels={[]}
        customProviderNames={[providerName]}
        onSubmit={onSubmit}
      />
    </>
  );
}

describe("AddModelForm discovery", () => {
  it.each(["gateway", "openrouter"])(
    "waits for %s changes to be saved and only saves a selected model on Add",
    async (providerName) => {
      vi.mocked(listProviderModels)
        .mockReset()
        .mockResolvedValue({
          models: [{ id: "model-a", name: "Model A" }],
        });
      const config = defaultUserConfig();
      config.ai = {
        ...config.ai,
        custom_providers: {
          [providerName]: { base_url: "https://original.example.com/v1" },
        },
      };
      const store = createStore();
      store.set(userConfigAtom, config);
      const onSubmit = vi.fn();
      const { rerender } = render(
        <Provider store={store}>
          <ModelForm
            providerName={providerName}
            savedConfig={config}
            onSubmit={onSubmit}
          />
        </Provider>,
      );
      await openAddModel(providerName);
      expect(search()).toBeEnabled();
      fireEvent.click(search());
      fireEvent.click(
        await screen.findByRole("button", { name: "Model A — model-a" }),
      );
      expect(onSubmit).not.toHaveBeenCalled();

      fireEvent.click(screen.getByRole("button", { name: "Change URL" }));
      expect(search()).toBeDisabled();
      const savedConfig = {
        ...config,
        ai: {
          ...config.ai,
          custom_providers: {
            [providerName]: { base_url: "https://changed.example.com/v1" },
          },
        },
      };
      act(() => {
        store.set(pendingConfigSavesAtom, 1);
        store.set(userConfigAtom, savedConfig);
      });
      rerender(
        <Provider store={store}>
          <ModelForm
            providerName={providerName}
            savedConfig={savedConfig}
            onSubmit={onSubmit}
          />
        </Provider>,
      );
      expect(search()).toBeDisabled();
      act(() => store.set(pendingConfigSavesAtom, 0));
      await waitFor(() => expect(search()).toBeEnabled());
      fireEvent.focus(screen.getByLabelText("Model"));
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      vi.mocked(listProviderModels).mockResolvedValue({
        models: [{ id: "model-b", name: "Model B" }],
      });
      fireEvent.change(screen.getByLabelText("Model"), {
        target: { value: "" },
      });
      fireEvent.click(search());
      fireEvent.click(
        await screen.findByRole("button", { name: "Model B — model-b" }),
      );
      expect(listProviderModels).toHaveBeenCalledTimes(2);
      expect(listProviderModels).toHaveBeenLastCalledWith(providerName);

      fireEvent.click(screen.getByRole("button", { name: /^Add$/ }));
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          ai: expect.objectContaining({
            models: expect.objectContaining({
              custom_models: [`${providerName}/model-b`],
            }),
          }),
        }),
      );
    },
  );

  it("keeps model entry focused across settings saves and only adds models on Add", async () => {
    const config = defaultUserConfig();
    config.ai = {
      ...config.ai,
      custom_providers: {
        gateway: { base_url: "https://gateway.example.com/v1" },
      },
    };
    const store = createStore();
    store.set(userConfigAtom, config);
    store.set(activeUserConfigCategoryAtom, "ai");
    store.set(aiSettingsSubTabAtom, "ai-models");
    saveUserConfig.mockReset().mockResolvedValue(null);
    vi.mocked(listProviderModels)
      .mockReset()
      .mockResolvedValue({
        models: [{ id: "second-model", name: "Second model" }],
      });
    render(
      <Provider store={store}>
        <UserConfigForm />
      </Provider>,
    );

    await openAddModel("gateway");
    fireEvent.change(screen.getByLabelText("Model"), {
      target: { value: "first-model" },
    });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 150));
    });
    fireEvent.click(screen.getByRole("button", { name: /^Add$/ }));
    await waitFor(() => expect(saveUserConfig).toHaveBeenCalledOnce());
    await waitFor(() => expect(store.get(pendingConfigSavesAtom)).toBe(0));

    await openAddModel("gateway");
    fireEvent.click(search());
    await screen.findByRole("button", { name: "Second model — second-model" });
    const pendingSave = Promise.withResolvers<null>();
    saveUserConfig.mockReturnValueOnce(pendingSave.promise);
    const input = screen.getByLabelText("Model");
    act(() => input.focus());
    fireEvent.change(input, { target: { value: "second" } });
    await waitFor(() => expect(saveUserConfig).toHaveBeenCalledTimes(2));
    expect(store.get(pendingConfigSavesAtom)).toBe(1);
    expect(screen.getByLabelText("Model")).toBe(input);
    expect(input).toHaveFocus();

    await act(async () => pendingSave.resolve(null));
    await screen.findByRole("button", { name: "Second model — second-model" });
    expect(screen.getByLabelText("Model")).toBe(input);
    expect(input).toHaveFocus();
    expect(input).toHaveValue("second");
    expect(store.get(userConfigAtom).ai?.models?.custom_models).toEqual([
      "gateway/first-model",
    ]);

    fireEvent.click(
      screen.getByRole("button", { name: "Second model — second-model" }),
    );
    fireEvent.click(screen.getByRole("button", { name: /^Add$/ }));
    await waitFor(() =>
      expect(store.get(userConfigAtom).ai?.models?.custom_models).toEqual([
        "gateway/second-model",
        "gateway/first-model",
      ]),
    );
  });
});
