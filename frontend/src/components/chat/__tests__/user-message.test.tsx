/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { UserMessage } from "../user-message";

describe("UserMessage", () => {
  it("shows context mentions as chips instead of raw URIs", () => {
    render(
      <TooltipProvider>
        <UserMessage
          message={{
            id: "u",
            role: "user",
            parts: [{ type: "text", text: "Plot @variable://df please" }],
          }}
          canEdit={true}
          onEdit={vi.fn()}
        />
      </TooltipProvider>,
    );
    const chip = screen.getByTitle("variable://df");
    expect(chip.textContent).toBe("@df");
    expect(screen.queryByText(/@variable:\/\//)).toBeNull();
  });
});
