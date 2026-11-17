/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ModalProvider } from "@/components/modal/ImperativeModal";
import { TooltipProvider } from "@/components/ui/tooltip";
import { store } from "@/core/state/jotai";
import { PairWithAgentBanner } from "../pair-with-agent";

const mocks = vi.hoisted(() => ({
  isWasm: vi.fn(() => false),
}));

vi.mock("@/core/wasm/utils", () => ({
  isWasm: mocks.isWasm,
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

function stubTokenFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ token: null }))),
  );
}

describe("PairWithAgent", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    mocks.isWasm.mockReset();
    mocks.isWasm.mockReturnValue(false);
  });

  it("shows local agent options", () => {
    render(<PairWithAgentBanner />, { wrapper });

    expect(
      screen.getByRole("group", { name: "Supported agents" }),
    ).toBeVisible();
    expect(screen.getByRole("figure", { name: "Claude Code" })).toBeVisible();
    expect(screen.getByRole("figure", { name: "Codex" })).toBeVisible();
    expect(screen.getByRole("figure", { name: "Cursor" })).toBeVisible();
    expect(screen.getByRole("figure", { name: "Gemini CLI" })).toBeVisible();
    expect(screen.getByRole("figure", { name: "OpenCode" })).toBeVisible();
    expect(
      screen.getByRole("figure", { name: "GitHub Copilot" }),
    ).toBeVisible();
    expect(
      screen.getByRole("figure", { name: "Any local agent" }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", {
        name: "Set up pairing",
      }),
    ).toBeVisible();
  });

  it("opens the pairing dialog from the banner button", () => {
    stubTokenFetch();
    render(<PairWithAgentBanner />, { wrapper });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Set up pairing",
      }),
    );

    expect(
      screen.getByRole("dialog", { name: "Pair an agent to this notebook" }),
    ).toBeVisible();
  });

  it("hides pairing controls in WASM", () => {
    mocks.isWasm.mockReturnValue(true);

    const { container } = render(<PairWithAgentBanner />, { wrapper });
    expect(container).toBeEmptyDOMElement();
  });
});
