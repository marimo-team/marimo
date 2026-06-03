/* Copyright 2026 Marimo. All rights reserved. */
import { render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { kioskModeAtom } from "@/core/mode";
import { API } from "@/core/network/api";
import { ViewerBanner } from "../viewer-banner";

describe("ViewerBanner", () => {
  it("renders nothing when not in kiosk mode", () => {
    const store = createStore();
    store.set(kioskModeAtom, false);
    const { container } = render(
      <Provider store={store}>
        <TooltipProvider>
          <ViewerBanner />
        </TooltipProvider>
      </Provider>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing for an intentional kiosk client (?kiosk=true)", () => {
    const store = createStore();
    store.set(kioskModeAtom, true);
    window.history.pushState({}, "", "/?kiosk=true");
    try {
      const { container } = render(
        <Provider store={store}>
          <TooltipProvider>
            <ViewerBanner />
          </TooltipProvider>
        </Provider>,
      );
      expect(container).toBeEmptyDOMElement();
    } finally {
      window.history.pushState({}, "", "/");
    }
  });

  it("shows take over and posts without reload when viewing", () => {
    const store = createStore();
    store.set(kioskModeAtom, true);
    const post = vi.spyOn(API, "post").mockResolvedValue({} as never);
    render(
      <Provider store={store}>
        <TooltipProvider>
          <ViewerBanner />
        </TooltipProvider>
      </Provider>,
    );
    const button = screen.getByTestId("takeover-button");
    button.click();
    expect(post).toHaveBeenCalledWith(
      expect.stringContaining("/kernel/takeover"),
      {},
    );
  });
});
