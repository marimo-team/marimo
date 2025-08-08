/* Copyright 2024 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { requestClientAtom } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
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

function createTestWrapper() {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
  return { wrapper };
}

describe("InstallPackageButton", () => {
  const { wrapper } = createTestWrapper();

  beforeEach(() => {
    vi.clearAllMocks();
    store.set(requestClientAtom, MockRequestClient.create());
  });

  it("should not render when packages is undefined", () => {
    const { container } = render(
      <InstallPackageButton packages={undefined} />,
      { wrapper },
    );
    expect(container.firstChild).toBeNull();
  });

  it("should not render when packages is empty", () => {
    const { container } = render(<InstallPackageButton packages={[]} />, {
      wrapper,
    });
    expect(container.firstChild).toBeNull();
  });

  it("should render with the correct package names", () => {
    render(<InstallPackageButton packages={["altair", "pandas"]} />, {
      wrapper,
    });
    expect(screen.getByText("Install altair, pandas")).toBeInTheDocument();
  });

  it("should render correct package names when showMaxPackages is set", () => {
    render(
      <InstallPackageButton
        packages={["altair", "pandas"]}
        showMaxPackages={1}
      />,
      { wrapper },
    );
    expect(screen.getByText("Install altair")).toBeInTheDocument();
  });
});
