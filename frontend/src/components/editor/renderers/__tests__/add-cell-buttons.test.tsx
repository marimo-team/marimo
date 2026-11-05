/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CellColumnId } from "@/core/cells/layout";
import { AddCellButtons } from "../cell-array";

const { openApplication, setAiPanelTab, saveModeChange, aiAtom } =
  await vi.hoisted(async () => {
    const { atom } = await import("jotai");
    return {
      aiAtom: atom<{ mode?: "ask" | "agent" | "code_mode" }>({}),
      openApplication: vi.fn(),
      setAiPanelTab: vi.fn(),
      saveModeChange: vi.fn().mockResolvedValue(undefined),
    };
  });

vi.mock("@/core/config/config", async (importOriginal) => {
  const actual = await importOriginal<object>();
  const { atom } = await import("jotai");
  return { ...actual, aiAtom, aiEnabledAtom: atom(true) };
});
vi.mock("@/core/network/connection", async (importOriginal) => {
  const actual = await importOriginal<object>();
  const { atom } = await import("jotai");
  return { ...actual, canInteractWithAppAtom: atom(true) };
});
vi.mock("@/core/ai/config", () => ({
  useAIConfigActions: () => ({ saveModeChange }),
}));
vi.mock("../../chrome/state", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useChromeActions: () => ({ openApplication }),
}));
vi.mock("../../chrome/wrapper/useAiPanel", () => ({
  useAiPanelTab: () => ({ setAiPanelTab }),
}));

describe("AddCellButtons", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each([
    { mode: undefined, calls: [["agent"]] },
    { mode: "ask", calls: [["agent"]] },
    { mode: "agent", calls: [] },
    { mode: "code_mode", calls: [] },
  ] as const)(
    "opens chat with edit access from $mode mode",
    async ({ mode, calls }) => {
      const store = createStore();
      store.set(aiAtom, { mode });
      render(
        <Provider store={store}>
          <AddCellButtons columnId={"column-1" as CellColumnId} />
        </Provider>,
      );

      fireEvent.click(screen.getByRole("button", { name: "Generate with AI" }));
      await waitFor(() => expect(openApplication).toHaveBeenCalledWith("ai"));
      expect(setAiPanelTab).toHaveBeenCalledWith("chat");
      expect(saveModeChange.mock.calls).toEqual(calls);
      expect(
        screen.getByRole("button", { name: "Python" }),
      ).toBeInTheDocument();
      expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    },
  );
});
