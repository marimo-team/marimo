/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { InstallPackageButton } from "../install-package-button";

const mockToggleApplication = vi.fn();
vi.mock("@/components/editor/chrome/state", () => ({
  useChromeActions: () => ({
    toggleApplication: mockToggleApplication,
  }),
}));

const mockSetPackagesToInstall = vi.fn();
vi.mock("jotai", () => ({
  atom: () => ({}),
  useSetAtom: () => mockSetPackagesToInstall,
}));

vi.mock("@/components/editor/chrome/panels/packages-state", () => ({
  packagesToInstallAtom: {},
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

    expect(mockSetPackagesToInstall).toHaveBeenCalledWith("altair");

    expect(mockToggleApplication).toHaveBeenCalledWith("packages");
  });
});
