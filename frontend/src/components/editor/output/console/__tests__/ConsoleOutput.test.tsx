/* Copyright 2024 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { CellId } from "@/core/cells/ids";
import type { OutputMessage } from "@/core/kernel/messages";
import { ConsoleOutput } from "../ConsoleOutput";

describe("ConsoleOutput integration", () => {
  const createOutput = (data: string, channel = "stdout"): OutputMessage => ({
    channel: channel as "stdout" | "stderr",
    mimetype: "text/plain",
    data,
    timestamp: 0,
  });

  const defaultProps = {
    cellId: "cell-1" as CellId,
    cellName: "test_cell",
    consoleOutputs: [],
    stale: false,
    debuggerActive: false,
    onSubmitDebugger: () => {},
  };

  it("should render console output with clickable URLs", () => {
    const props = {
      ...defaultProps,
      consoleOutputs: [
        {
          ...createOutput("Check out https://marimo.io for more info"),
          response: undefined,
        },
      ],
    };

    render(
      <TooltipProvider>
        <ConsoleOutput {...props} />
      </TooltipProvider>,
    );

    const link = screen.getByRole("link", { name: "https://marimo.io" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "https://marimo.io");
  });
});
