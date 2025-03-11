/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { InstallPackageButton } from "../install-package-button";
import { store } from "@/core/state/jotai";
import { chromeAtom } from "@/components/editor/chrome/state";

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

const mockInput = {
  focus: vi.fn(),
  value: "",
  dispatchEvent: vi.fn(),
};
vi.spyOn(document, "getElementById").mockReturnValue(
  mockInput as unknown as HTMLInputElement,
);

describe("InstallPackageButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should not render when packages is undefined", () => {
    const { container } = render(<InstallPackageButton packages={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("should not render when packages is empty", () => {
    const { container } = render(<InstallPackageButton packages={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("should render with the correct package names", () => {
    render(<InstallPackageButton packages={["altair", "pandas"]} />);
    expect(screen.getByText("Install altair, pandas")).toBeInTheDocument();
  });

  it("should open the packages panel when clicked", () => {
    render(<InstallPackageButton packages={["altair"]} />);

    fireEvent.click(screen.getByText("Install altair"));

    expect(store.set).toHaveBeenCalledWith(chromeAtom, expect.any(Function));

    const updateFn = vi.mocked(store.set).mock.calls[0][1] as (
      state: any,
    ) => any;

    const mockState = {
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

    expect(mockInput.focus).toHaveBeenCalled();

    expect(mockInput.value).toBe("altair");

    expect(mockInput.dispatchEvent).toHaveBeenCalled();
  });
});
