/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { PropsWithChildren } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import { pendingAiPromptAtom } from "@/core/ai/state";
import { CellId } from "@/core/cells/ids";
import { aiPanelTabAtom } from "../useAiPanel";
import { useAskAiAboutCell } from "../useAskAiAboutCell";

const { aiAtom, openApplication, saveModeChange } = await vi.hoisted(
  async () => {
    const { atom } = await import("jotai");
    return {
      aiAtom: atom<{ mode?: "ask" | "agent" | "code_mode" }>({}),
      openApplication: vi.fn(),
      saveModeChange: vi.fn().mockResolvedValue(undefined),
    };
  },
);
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

beforeEach(() => vi.clearAllMocks());
it.each([undefined, "ask", "agent", "code_mode"] as const)(
  "opens chat from %s mode without submitting or replacing the draft",
  async (mode) => {
    const store = createStore();
    store.set(aiAtom, { mode });
    store.set(aiPanelTabAtom, "agents");
    const cellId = CellId.create();
    const { result } = renderHook(useAskAiAboutCell, {
      wrapper: ({ children }: PropsWithChildren) => (
        <Provider store={store}>{children}</Provider>
      ),
    });
    await act(() => result.current(cellId));
    expect(openApplication).toHaveBeenCalledWith("ai");
    expect(store.get(aiPanelTabAtom)).toBe("chat");
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
