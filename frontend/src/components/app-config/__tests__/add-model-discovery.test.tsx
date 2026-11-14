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
import { AddModelForm } from "../ai-config";
import { pendingConfigSavesAtom } from "../state";

vi.mock("@/core/network/ai", () => ({ listProviderModels: vi.fn() }));

Element.prototype.scrollIntoView = vi.fn();

const search = () =>
  screen.getByRole("button", { name: "Search available models" });

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
      fireEvent.click(screen.getByRole("button", { name: "Add model" }));
      fireEvent.click(screen.getByRole("combobox"));
      fireEvent.click(
        await screen.findByRole("option", {
          name: new RegExp(providerName, "i"),
        }),
      );
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
});
