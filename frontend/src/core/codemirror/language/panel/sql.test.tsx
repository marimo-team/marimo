/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { CellId } from "@/core/cells/ids";
import type { DetectedDataSource } from "@/core/datasets/data-source-discovery";
import type { ConnectionName } from "@/core/datasets/engines";
import { store } from "@/core/state/jotai";
import { SQLEngineSelect } from "./sql";

const { addDetectedDataSource } = vi.hoisted(() => ({
  addDetectedDataSource: vi.fn(),
}));

const POSTGRES_SOURCE: DetectedDataSource = {
  id: "postgres-libpq-environment",
  integration: "postgres",
  category: "database",
  displayName: "PostgreSQL",
  confidence: "high",
  origins: [{ type: "environment", label: "Kernel environment" }],
  configuration: [],
  code: "engine = create_engine()",
  hidesWhen: { kind: "dialect", substrings: ["postgres"] },
};

vi.mock("@/hooks/useDataSourceDiscovery", () => ({
  useDetectedDataSources: () => [POSTGRES_SOURCE],
}));

vi.mock("@/components/editor/connections/components", () => ({
  useAddDetectedDataSource: () => addDetectedDataSource,
}));

describe("SQLEngineSelect", () => {
  beforeAll(() => {
    HTMLElement.prototype.hasPointerCapture = vi.fn(() => false);
    HTMLElement.prototype.setPointerCapture = vi.fn();
    HTMLElement.prototype.releasePointerCapture = vi.fn();
    HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it("adds a database detected in the environment", async () => {
    render(
      <Provider store={store}>
        <TooltipProvider>
          <SQLEngineSelect
            selectedEngine={"" as ConnectionName}
            onChange={vi.fn()}
            cellId={"cell-1" as CellId}
          />
        </TooltipProvider>
      </Provider>,
    );

    fireEvent.keyDown(screen.getByRole("combobox"), { key: "ArrowDown" });

    expect(
      await screen.findByText("Detected in your environment"),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("option", { name: "Add PostgreSQL connection" }),
    );

    expect(addDetectedDataSource).toHaveBeenCalledWith(POSTGRES_SOURCE);
  });
});
