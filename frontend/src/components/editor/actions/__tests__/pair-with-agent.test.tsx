/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ModalProvider } from "@/components/modal/ImperativeModal";
import { TooltipProvider } from "@/components/ui/tooltip";
import { store } from "@/core/state/jotai";
import { PairWithAgentBanner, PairWithAgentButton } from "../pair-with-agent";

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
  afterEach(() => vi.unstubAllGlobals());

  it("shows local agent options", () => {
    render(<PairWithAgentBanner />, { wrapper });

    expect(screen.getByRole("img", { name: "claude" })).toBeVisible();
    expect(screen.getByRole("img", { name: "codex" })).toBeVisible();
    expect(screen.getByRole("img", { name: "cursor" })).toBeVisible();
    expect(screen.getByRole("img", { name: "gemini" })).toBeVisible();
    expect(screen.getByRole("img", { name: "opencode" })).toBeVisible();
    expect(screen.getByRole("img", { name: "github" })).toBeVisible();
    expect(screen.getByTitle("Any local agent")).toBeVisible();
    expect(
      screen.getByRole("button", {
        name: /any agent to work with this notebook/,
      }),
    ).toBeVisible();
  });

  it("opens the pairing dialog from the banner description", () => {
    stubTokenFetch();
    render(<PairWithAgentBanner />, { wrapper });

    fireEvent.click(
      screen.getByRole("button", {
        name: /any agent to work with this notebook/,
      }),
    );

    expect(
      screen.getByRole("dialog", { name: "Pair with an agent" }),
    ).toBeVisible();
  });

  it("opens the pairing dialog and preserves a passed click handler", () => {
    const onClick = vi.fn();
    stubTokenFetch();
    render(<PairWithAgentButton onClick={onClick} />, { wrapper });

    fireEvent.click(screen.getByRole("button", { name: "Pair with an agent" }));

    expect(onClick).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("dialog", { name: "Pair with an agent" }),
    ).toBeVisible();
  });
});
