/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { viewStateAtom } from "@/core/mode";
import { requestClientAtom } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { MissingPackagePrompt } from "../missing-package-prompt";

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

describe("MissingPackagePrompt", () => {
  const { wrapper } = createTestWrapper();

  beforeEach(() => {
    vi.clearAllMocks();
    store.set(requestClientAtom, MockRequestClient.create());
    store.set(viewStateAtom, { mode: "edit", cellAnchor: null });
  });

  it("should render backend description and install button in edit mode", () => {
    render(
      <MissingPackagePrompt
        packages={["polars"]}
        featureName="Parquet export"
        description="Parquet export requires a DataFrame library."
      />,
      { wrapper },
    );
    expect(
      screen.getByText("Parquet export requires a DataFrame library."),
    ).toBeInTheDocument();
    expect(screen.getByText("Install polars")).toBeInTheDocument();
  });

  it("should fall back to generic copy when description is absent", () => {
    render(
      <MissingPackagePrompt
        packages={["polars"]}
        featureName="Parquet export"
      />,
      { wrapper },
    );
    expect(
      screen.getByText("Parquet export requires polars"),
    ).toBeInTheDocument();
    expect(screen.getByText("Install polars")).toBeInTheDocument();
  });

  it("should render generic line in read mode and not leak packages or description", () => {
    store.set(viewStateAtom, { mode: "read", cellAnchor: null });
    render(
      <MissingPackagePrompt
        packages={["polars"]}
        featureName="Parquet export"
        description="Install polars to enable Parquet."
      />,
      { wrapper },
    );
    expect(
      screen.getByText("Parquet export isn't available in this notebook"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Install polars to enable Parquet."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Install polars")).not.toBeInTheDocument();
    expect(screen.queryByText(/polars/)).not.toBeInTheDocument();
  });
});
