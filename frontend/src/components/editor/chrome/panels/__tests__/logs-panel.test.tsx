/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CellLog } from "@/core/cells/logs";
import { LogViewer } from "../logs-panel";

describe("LogViewer", () => {
  it("labels logs that came from a language server instead of a cell", () => {
    const logs: CellLog[] = [
      {
        timestamp: 0,
        level: "stderr",
        message: "pylsp failed to start",
        source: { type: "lsp", name: "pylsp" },
      },
    ];

    render(<LogViewer logs={logs} />);

    expect(screen.getByText("(lsp:pylsp)")).toBeInTheDocument();
    expect(screen.getByText("pylsp failed to start")).toBeInTheDocument();
    expect(screen.getByText("STDERR")).toBeInTheDocument();
  });
});
