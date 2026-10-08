/* Copyright 2026 Marimo. All rights reserved. */

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { CompletionBannerPresence } from "../completion-banner-presence";

function banner(open: boolean) {
  return (
    <CompletionBannerPresence open={open}>
      <button type="button">Keep change</button>
    </CompletionBannerPresence>
  );
}

const getAnimations = vi.fn<() => { finished: Promise<void> }[]>(() => []);
const originalGetAnimations = Object.getOwnPropertyDescriptor(
  HTMLElement.prototype,
  "getAnimations",
);

beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, "getAnimations", {
    configurable: true,
    value: getAnimations,
  });
});

afterEach(() => {
  cleanup();
  getAnimations.mockReset();
  getAnimations.mockReturnValue([]);
  if (originalGetAnimations) {
    Object.defineProperty(
      HTMLElement.prototype,
      "getAnimations",
      originalGetAnimations,
    );
  } else {
    Reflect.deleteProperty(HTMLElement.prototype, "getAnimations");
  }
});

describe("CompletionBannerPresence", () => {
  it("does not mount controls or inspect animations in inactive cells", () => {
    const { rerender } = render(banner(false));
    expect(screen.queryByText("Keep change")).not.toBeInTheDocument();
    expect(getAnimations).not.toHaveBeenCalled();

    rerender(banner(true));
    expect(
      screen.getByRole("button", { name: "Keep change" }),
    ).toBeInTheDocument();
    expect(getAnimations).not.toHaveBeenCalled();
  });

  it("keeps exiting controls inert until all wrapper transitions finish", async () => {
    const height = new Deferred<void>();
    const opacity = new Deferred<void>();
    getAnimations.mockReturnValue([
      { finished: height.promise },
      { finished: opacity.promise },
    ]);
    const { rerender } = render(banner(true));
    rerender(banner(false));

    const button = screen.getByText("Keep change");
    const content = button.closest(".completion-banner-presence");
    expect(content).toHaveAttribute("inert");
    expect(content).toHaveAttribute("aria-hidden", "true");
    expect(screen.queryByRole("button", { name: "Keep change" })).toBeNull();

    await act(async () => height.resolve(undefined));
    expect(button).toBeInTheDocument();
    await act(async () => opacity.resolve(undefined));
    await waitFor(() => expect(button).not.toBeInTheDocument());
  });

  it("ignores the previous exit when reopened", async () => {
    const exit = new Deferred<void>();
    getAnimations.mockReturnValue([{ finished: exit.promise }]);
    const { rerender } = render(banner(true));
    rerender(banner(false));
    rerender(banner(true));
    await act(async () => exit.reject(new Error("Transition reversed")));

    const button = screen.getByRole("button", { name: "Keep change" });
    expect(button).toBeInTheDocument();
    expect(button.closest(".completion-banner-presence")).not.toHaveAttribute(
      "inert",
    );
  });

  it("removes controls when a closing transition is cancelled", async () => {
    const exit = new Deferred<void>();
    getAnimations.mockReturnValue([{ finished: exit.promise }]);
    const { rerender } = render(banner(true));
    rerender(banner(false));
    await act(async () => exit.reject(new Error("Motion disabled")));
    expect(screen.queryByText("Keep change")).not.toBeInTheDocument();
  });

  it("removes controls immediately without animations", () => {
    const { rerender } = render(banner(true));
    rerender(banner(false));
    expect(screen.queryByText("Keep change")).not.toBeInTheDocument();
  });
});
