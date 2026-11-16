/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ModalProvider } from "@/components/modal/ImperativeModal";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { DetectedDataSource } from "@/core/datasets/data-source-discovery";
import { store } from "@/core/state/jotai";
import { AddConnectionButton } from "../add-connection-button";

const mocks = vi.hoisted(() => ({
  addDetectedDataSource: vi.fn(),
  sources: [] as DetectedDataSource[],
}));

const MYSQL_SOURCE: DetectedDataSource = {
  id: "mysql-environment",
  integration: "mysql",
  category: "database",
  displayName: "MySQL",
  confidence: "high",
  origins: [{ type: "environment", label: "Kernel environment" }],
  configuration: [],
  code: "engine = create_engine()",
  hidesWhen: { kind: "dialect", substrings: ["mysql"] },
};

vi.mock("@/hooks/useDataSourceDiscovery", () => ({
  useDetectedDataSources: () => mocks.sources,
}));

vi.mock("../components", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../components")>()),
  useAddDetectedDataSource: () => mocks.addDetectedDataSource,
}));

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <Provider store={store}>
      <TooltipProvider>
        <ModalProvider>{children}</ModalProvider>
      </TooltipProvider>
    </Provider>
  );
}

describe("AddConnectionButton", () => {
  beforeEach(() => {
    mocks.sources = [];
    mocks.addDetectedDataSource.mockClear();
    vi.stubGlobal("PointerEvent", MouseEvent);
  });

  afterEach(() => vi.unstubAllGlobals());

  it("opens the connection dialog directly without suggestions", () => {
    render(
      <AddConnectionButton
        group="database"
        label="Add database or catalog"
        variant="outline"
      />,
      { wrapper },
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Add database or catalog" }),
    );

    expect(
      screen.getByRole("dialog", { name: "Add Connection" }),
    ).toBeVisible();
  });

  it("opens an ordered suggestion menu when sources are detected", async () => {
    mocks.sources = [MYSQL_SOURCE];
    render(
      <AddConnectionButton
        group="database"
        label="Add database or catalog"
        variant="outline"
      />,
      { wrapper },
    );

    fireEvent.pointerDown(
      screen.getByRole("button", {
        name: "View detected database connections",
      }),
      { button: 0, ctrlKey: false },
    );

    const suggestion = await screen.findByRole("menuitem", {
      name: "Add MySQL",
    });
    const browseAll = screen.getByRole("menuitem", {
      name: "Browse all connections",
    });
    expect(
      suggestion.compareDocumentPosition(browseAll) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    fireEvent.click(suggestion);
    expect(mocks.addDetectedDataSource).toHaveBeenCalledWith(MYSQL_SOURCE);
  });

  it("keeps the primary action direct when sources are detected", () => {
    mocks.sources = [MYSQL_SOURCE];
    render(
      <AddConnectionButton
        group="database"
        label="Add database or catalog"
        variant="outline"
      />,
      { wrapper },
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Add database or catalog" }),
    );

    expect(
      screen.getByRole("dialog", { name: "Add Connection" }),
    ).toBeVisible();
  });
});
