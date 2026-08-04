/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { parseQuery } from "better-filter-bar/react";
import { describe, expect, it, vi } from "vitest";
import { AiFilterBar } from "./AiFilterBar";
import type { AiFilterState } from "./useAiFilter";

vi.mock("better-filter-bar/react", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("better-filter-bar/react")>();
  return { ...actual, parseQuery: vi.fn(actual.parseQuery) };
});

vi.mock("@/utils/Logger", () => ({
  Logger: { error: vi.fn() },
}));

function makeAi(overrides: Partial<AiFilterState> = {}): AiFilterState {
  return {
    schema: {
      fields: [{ name: "status", label: "status", type: "text" }],
      allowUnknownFields: false,
    },
    rawQuery: "status:open",
    appliedRaw: "status:open",
    isActive: true,
    isGenerating: false,
    error: null,
    filterGroup: null,
    query: "",
    generationId: 1,
    generate: vi.fn(),
    applyFromEditor: vi.fn(),
    clear: vi.fn(),
    ...overrides,
  };
}

describe("AiFilterBar", () => {
  it("renders the filter editor and an exit control", () => {
    render(<AiFilterBar ai={makeAi()} />);
    expect(
      screen.getByRole("button", { name: "Exit AI filter" }),
    ).toBeInTheDocument();
  });

  it("renders while generating without crashing", () => {
    render(<AiFilterBar ai={makeAi({ isGenerating: true })} />);
    expect(
      screen.getByRole("button", { name: "Exit AI filter" }),
    ).toBeInTheDocument();
  });

  it("surfaces an error alongside the editor", () => {
    render(<AiFilterBar ai={makeAi({ error: "no model configured" })} />);
    expect(screen.getByText("no model configured")).toBeInTheDocument();
    // The editor stays mounted so the query text is not lost.
    expect(
      screen.getByRole("button", { name: "Exit AI filter" }),
    ).toBeInTheDocument();
  });

  it("exits AI-filter mode when the exit control is clicked", () => {
    const ai = makeAi();
    render(<AiFilterBar ai={ai} />);
    fireEvent.click(screen.getByRole("button", { name: "Exit AI filter" }));
    expect(ai.clear).toHaveBeenCalledTimes(1);
  });

  it("applies the filter on Enter key press", () => {
    const ai = makeAi();
    render(<AiFilterBar ai={ai} />);
    fireEvent.keyDown(screen.getByTestId("ai-filter-editor"), { key: "Enter" });
    expect(ai.applyFromEditor).toHaveBeenCalled();
  });

  it("surfaces parse errors when applying malformed editor input", () => {
    vi.mocked(parseQuery).mockImplementationOnce(() => {
      throw new Error("Unexpected token");
    });
    const ai = makeAi({ rawQuery: "malformed filter" });
    render(<AiFilterBar ai={ai} />);

    fireEvent.keyDown(screen.getByTestId("ai-filter-editor"), { key: "Enter" });

    expect(ai.applyFromEditor).not.toHaveBeenCalled();
    expect(screen.getByText("Unexpected token")).toBeInTheDocument();
  });
});
