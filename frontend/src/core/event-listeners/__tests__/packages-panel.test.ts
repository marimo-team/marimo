/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  initPackagesPanelEventListener,
  handleOpenPackagesPanel,
} from "../packages-panel";
import { store } from "@/core/state/jotai";
import { chromeAtom } from "@/components/editor/chrome/state";
import type { ChromeState } from "@/components/editor/chrome/state";

vi.mock("@/core/state/jotai", () => ({
  store: {
    set: vi.fn(),
  },
}));

const mockRequestAnimationFrame = vi.fn((callback) => {
  callback();
  return 1;
});
vi.stubGlobal("requestAnimationFrame", mockRequestAnimationFrame);

const mockElement = {
  focus: vi.fn(),
};
vi.spyOn(document, "getElementById").mockReturnValue(
  mockElement as unknown as HTMLElement,
);

describe("packages-panel event listener", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should handle opening the packages panel", () => {
    handleOpenPackagesPanel();

    expect(store.set).toHaveBeenCalledWith(chromeAtom, expect.any(Function));

    const updateFn = vi.mocked(store.set).mock.calls[0][1] as (
      state: ChromeState,
    ) => ChromeState;

    const mockState: ChromeState = {
      isSidebarOpen: false,
      selectedPanel: undefined,
      isTerminalOpen: false,
    };
    const newState = updateFn(mockState);

    expect(newState).toEqual({
      isSidebarOpen: true,
      selectedPanel: "packages",
      isTerminalOpen: false,
    });

    expect(mockRequestAnimationFrame).toHaveBeenCalled();

    expect(mockElement.focus).toHaveBeenCalled();
  });

  it("should initialize event listener that calls the handler", () => {
    const addEventListenerSpy = vi.spyOn(document, "addEventListener");

    initPackagesPanelEventListener();

    expect(addEventListenerSpy).toHaveBeenCalledWith(
      "marimo:open-packages-panel",
      handleOpenPackagesPanel,
    );
  });
});
