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
  it("persists and updates a capability change", async () => {
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

    await act(async () => {
      await result.current.saveCapabilityChange("web_search", true);
    });

    expect(saveUserConfig).toHaveBeenCalledWith({
      config: expect.objectContaining({
        ai: expect.objectContaining({
          capabilities: { web_search: "on" },
        }),
      }),
    });
    expect(store.get(userConfigAtom).ai?.capabilities?.web_search).toBe("on");
  });
});
