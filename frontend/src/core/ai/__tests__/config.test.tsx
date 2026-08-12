/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { userConfigAtom } from "@/core/config/config";
import { defaultUserConfig } from "@/core/config/config-schema";
import { requestClientAtom } from "@/core/network/requests";
import type { EditRequests, RunRequests } from "@/core/network/types";
import { useAIConfigActions } from "../config";

describe("useAIConfigActions", () => {
  it("persists a disabled capability without overwriting newer AI config", async () => {
    const store = createStore();
    const saveUserConfig = vi.fn().mockResolvedValue(null);
    store.set(userConfigAtom, defaultUserConfig());
    store.set(requestClientAtom, {
      saveUserConfig,
    } as unknown as EditRequests & RunRequests);

    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    const { result } = renderHook(() => useAIConfigActions(), { wrapper });

    store.set(userConfigAtom, (config) => ({
      ...config,
      ai: {
        ...config.ai,
        mode: "agent",
        capabilities: { web_search: true },
      },
    }));

    await act(async () => {
      await result.current.saveCapabilityChange("web_search", false);
    });

    expect(saveUserConfig).toHaveBeenCalledWith({
      config: { ai: { capabilities: { web_search: false } } },
    });
    expect(store.get(userConfigAtom).ai).toMatchObject({
      capabilities: { web_search: false },
      mode: "agent",
    });
  });

  it("preserves concurrent AI changes when saves resolve out of order", async () => {
    const store = createStore();
    const resolvers: Array<() => void> = [];
    const saveUserConfig = vi.fn(
      () =>
        new Promise<null>((resolve) => {
          resolvers.push(() => resolve(null));
        }),
    );
    store.set(userConfigAtom, defaultUserConfig());
    store.set(requestClientAtom, {
      saveUserConfig,
    } as unknown as EditRequests & RunRequests);

    const wrapper = ({ children }: { children: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );
    const { result } = renderHook(() => useAIConfigActions(), { wrapper });

    const modeChange = result.current.saveModeChange("agent");
    const capabilityChange = result.current.saveCapabilityChange(
      "web_search",
      true,
    );

    expect(saveUserConfig).toHaveBeenNthCalledWith(1, {
      config: { ai: { mode: "agent" } },
    });
    expect(saveUserConfig).toHaveBeenNthCalledWith(2, {
      config: { ai: { capabilities: { web_search: true } } },
    });

    await act(async () => {
      resolvers[1]();
      await capabilityChange;
      resolvers[0]();
      await modeChange;
    });

    expect(store.get(userConfigAtom).ai).toMatchObject({
      capabilities: { web_search: true },
      mode: "agent",
    });
  });
});
