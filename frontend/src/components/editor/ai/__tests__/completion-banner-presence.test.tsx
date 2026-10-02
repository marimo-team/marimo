/* Copyright 2026 Marimo. All rights reserved. */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompletionBannerPresence } from "../completion-banner-presence";

function banner(open: boolean) {
  return (
    <CompletionBannerPresence open={open}>
      <button type="button">Keep change</button>
    </CompletionBannerPresence>
  );
}

// jsdom does not apply imported CSS or emit animation events.
function simulateAnimationStyles() {
  const getComputedStyle = window.getComputedStyle;
  vi.spyOn(window, "getComputedStyle").mockImplementation((element) => {
    const styles = getComputedStyle(element);
    return new Proxy(styles, {
      get(target, property, receiver) {
        if (
          property === "animationName" &&
          element.classList.contains("completion-banner-presence")
        ) {
          return element.getAttribute("data-state") === "open"
            ? "completion-banner-enter"
            : "completion-banner-exit";
        }
        return Reflect.get(target, property, receiver);
      },
    });
  });
}

function endExit(element: Element) {
  const event = new Event("animationend", { bubbles: true });
  Object.defineProperty(event, "animationName", {
    value: "completion-banner-exit",
  });
  fireEvent(element, event);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("CompletionBannerPresence", () => {
  it("does not mount controls until opened", () => {
    const { rerender } = render(banner(false));
    expect(screen.queryByText("Keep change")).not.toBeInTheDocument();

    rerender(banner(true));
    const content = screen.getByRole("button", {
      name: "Keep change",
    }).parentElement;
    expect(content).not.toHaveAttribute("inert");
    expect(content).toHaveAttribute("aria-hidden", "false");
  });

  it("makes exiting controls inert and removes them when the animation ends", () => {
    simulateAnimationStyles();
    const { rerender } = render(banner(true));
    const content = screen.getByRole("button", {
      name: "Keep change",
    }).parentElement;
    expect(content).not.toBeNull();
    if (!content) {
      throw new Error("Banner content is missing");
    }

    rerender(banner(false));
    expect(screen.getByText("Keep change")).toBeInTheDocument();
    expect(content).toHaveAttribute("inert");
    expect(content).toHaveAttribute("aria-hidden", "true");
    expect(screen.queryByRole("button", { name: "Keep change" })).toBeNull();

    endExit(content);
    expect(screen.queryByText("Keep change")).not.toBeInTheDocument();
  });

  it("keeps controls mounted if reopened during exit", () => {
    simulateAnimationStyles();
    const { rerender } = render(banner(true));
    const content = screen.getByRole("button", {
      name: "Keep change",
    }).parentElement;
    if (!content) {
      throw new Error("Banner content is missing");
    }

    rerender(banner(false));
    rerender(banner(true));
    endExit(content);
    expect(
      screen.getByRole("button", { name: "Keep change" }),
    ).toBeInTheDocument();
    expect(content).not.toHaveAttribute("inert");
  });

  it("removes controls immediately when there is no animation", () => {
    const { rerender } = render(banner(true));
    rerender(banner(false));
    expect(screen.queryByText("Keep change")).not.toBeInTheDocument();
  });
});
