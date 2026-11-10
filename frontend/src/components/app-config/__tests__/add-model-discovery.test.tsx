/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

vi.mock("@/core/network/ai", () => ({ listProviderModels: vi.fn() }));

Element.prototype.scrollIntoView = vi.fn();

const search = () =>
  screen.getByRole("button", { name: "Search available models" });

function ModelForm({
  savedConfig,
  onSubmit,
  isSaving = false,
}: {
  isSaving?: boolean;
  savedConfig: UserConfig;
  onSubmit: (config: UserConfig) => void;
}) {
  const form = useForm<UserConfig>({ defaultValues: savedConfig });
  return (
    <>
      <Controller
        control={form.control}
        name="ai.custom_providers.gateway.api_key"
        render={() => <span />}
      />
      <button
        type="button"
        onClick={() =>
          form.setValue(
            "ai.custom_providers.gateway.base_url",
            "https://changed.example.com/v1",
          )
        }
      >
        Change URL
      </button>
      <AddModelForm
        isSaving={isSaving}
        form={form}
        config={savedConfig}
        customModels={[]}
        customProviderNames={["gateway"]}
        onSubmit={onSubmit}
      />
    </>
  );
}

describe("AddModelForm discovery", () => {
  it("waits for provider changes to be saved and only saves a selected model on Add", async () => {
    vi.mocked(listProviderModels).mockResolvedValue({
      models: [{ id: "model-a", name: "Model A" }],
    });
    const config = defaultUserConfig();
    config.ai = {
      ...config.ai,
      custom_providers: {
        gateway: { base_url: "https://original.example.com/v1" },
      },
    };
    const store = createStore();
    store.set(userConfigAtom, config);
    const onSubmit = vi.fn();
    const { rerender } = render(
      <Provider store={store}>
        <ModelForm savedConfig={config} onSubmit={onSubmit} />
      </Provider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Add model" }));
    fireEvent.click(screen.getByRole("combobox"));
    fireEvent.click(await screen.findByRole("option", { name: "Gateway" }));
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
          gateway: { base_url: "https://changed.example.com/v1" },
        },
      },
    };
    store.set(userConfigAtom, savedConfig);
    rerender(
      <Provider store={store}>
        <ModelForm
          savedConfig={savedConfig}
          onSubmit={onSubmit}
          isSaving={true}
        />
      </Provider>,
    );
    expect(search()).toBeDisabled();
    rerender(
      <Provider store={store}>
        <ModelForm savedConfig={savedConfig} onSubmit={onSubmit} />
      </Provider>,
    );
    await waitFor(() => expect(search()).toBeEnabled());
    fireEvent.focus(screen.getByLabelText("Model"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^Add$/ }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        ai: expect.objectContaining({
          models: expect.objectContaining({
            custom_models: ["gateway/model-a"],
          }),
        }),
      }),
    );
  });
});
