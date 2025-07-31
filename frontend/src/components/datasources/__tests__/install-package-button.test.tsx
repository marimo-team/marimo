/* Copyright 2024 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { InstallPackageButton } from "../install-package-button";

const mockOpenApplication = vi.fn();
vi.mock("@/components/editor/chrome/state", () => ({
  useChromeActions: () => ({
    openApplication: mockOpenApplication,
  }),
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

  it("should render correct package names when showMaxPackages is set", () => {
    render(
      <InstallPackageButton
        packages={["altair", "pandas"]}
        showMaxPackages={1}
      />,
    );
    expect(screen.getByText("Install altair")).toBeInTheDocument();
  });
});
