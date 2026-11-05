/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { pendingAiPromptAtom } from "@/core/ai/state";
import { CellId } from "@/core/cells/ids";
import { useAskAiAboutCell } from "../useAskAiAboutCell";

const { aiAtom, openApplication, setAiPanelTab, saveModeChange } =
  await vi.hoisted(async () => {
    const { atom } = await import("jotai");
    return {
      aiAtom: atom<{ mode?: "ask" | "agent" | "code_mode" }>({}),
      openApplication: vi.fn(),
      setAiPanelTab: vi.fn(),
      saveModeChange: vi.fn().mockResolvedValue(undefined),
    };
  });
vi.mock("@/core/config/config", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  aiAtom,
}));
vi.mock("@/core/ai/config", () => ({
  useAIConfigActions: () => ({ saveModeChange }),
}));
vi.mock("../../state", () => ({
  useChromeActions: () => ({ openApplication }),
}));
vi.mock("../useAiPanel", () => ({ useAiPanelTab: () => ({ setAiPanelTab }) }));

beforeEach(() => vi.clearAllMocks());
it.each([undefined, "ask", "agent", "code_mode"] as const)(
  "opens chat from %s mode without submitting or replacing the draft",
  async (mode) => {
    const store = createStore();
    store.set(aiAtom, { mode });
    const cellId = CellId.create();
    const { result } = renderHook(useAskAiAboutCell, {
      wrapper: ({ children }: PropsWithChildren) => (
        <Provider store={store}>{children}</Provider>
      ),
    });
    await act(() => result.current(cellId));
    expect(openApplication).toHaveBeenCalledWith("ai");
    expect(setAiPanelTab).toHaveBeenCalledWith("chat");
    expect(saveModeChange.mock.calls).toEqual(
      mode === "agent" || mode === "code_mode" ? [] : [["agent"]],
    );
    expect(store.get(pendingAiPromptAtom)).toEqual({
      prompt: `@cell://${cellId} `,
      submit: false,
      append: true,
    });
  },
);
