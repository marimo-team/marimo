/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, screen } from "@testing-library/react";
import { atom, createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProgressiveBoundary } from "../ProgressiveBoundary";

describe("ProgressiveBoundary", () => {
  let store: ReturnType<typeof createStore>;

  const wrapper = ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );

  beforeEach(() => {
    vi.useFakeTimers();
    store = createStore();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders children once the capability resolves true", () => {
    const capability = atom(true);
    render(
      <ProgressiveBoundary requires={capability}>
        <span>content</span>
      </ProgressiveBoundary>,
      { wrapper },
    );
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("blocks children with no fallback when capability is false", () => {
    const capability = atom(false);
    const { container } = render(
      <ProgressiveBoundary requires={capability}>
        <span>content</span>
      </ProgressiveBoundary>,
      { wrapper },
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the fallback when capability is false", () => {
    const capability = atom(false);
    render(
      <ProgressiveBoundary requires={capability} fallback={<span>wait</span>}>
        <span>content</span>
      </ProgressiveBoundary>,
      { wrapper },
    );
    expect(screen.getByText("wait")).toBeInTheDocument();
    expect(screen.queryByText("content")).not.toBeInTheDocument();
  });

  it("renders children once a previously-false capability flips true", () => {
    const capability = atom(false);
    render(
      <ProgressiveBoundary requires={capability} fallback={<span>wait</span>}>
        <span>content</span>
      </ProgressiveBoundary>,
      { wrapper },
    );
    expect(screen.getByText("wait")).toBeInTheDocument();

    act(() => store.set(capability, true));
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("reopens the gate when a capability flips back to false", () => {
    const capability = atom(true);
    render(
      <ProgressiveBoundary requires={capability} fallback={<span>wait</span>}>
        <span>content</span>
      </ProgressiveBoundary>,
      { wrapper },
    );
    expect(screen.getByText("content")).toBeInTheDocument();

    act(() => store.set(capability, false));
    expect(screen.queryByText("content")).not.toBeInTheDocument();
    expect(screen.getByText("wait")).toBeInTheDocument();
  });

  it("delays the fallback by `delay` ms", () => {
    const capability = atom(false);
    render(
      <ProgressiveBoundary
        requires={capability}
        delay={2000}
        fallback={<span>wait</span>}
      >
        <span>content</span>
      </ProgressiveBoundary>,
      { wrapper },
    );
    // Before the delay elapses, no fallback.
    expect(screen.queryByText("wait")).not.toBeInTheDocument();

    act(() => vi.advanceTimersByTime(2000));
    expect(screen.getByText("wait")).toBeInTheDocument();
  });

  it("re-arms the delay when the gate closes again", () => {
    const capability = atom(true);
    render(
      <ProgressiveBoundary
        requires={capability}
        delay={2000}
        fallback={<span>wait</span>}
      >
        <span>content</span>
      </ProgressiveBoundary>,
      { wrapper },
    );
    expect(screen.getByText("content")).toBeInTheDocument();

    // Gate closes: fallback should stay suppressed until the delay re-elapses.
    act(() => store.set(capability, false));
    expect(screen.queryByText("wait")).not.toBeInTheDocument();
    expect(screen.queryByText("content")).not.toBeInTheDocument();

    act(() => vi.advanceTimersByTime(2000));
    expect(screen.getByText("wait")).toBeInTheDocument();
  });

  it("skips the fallback entirely if the gate opens before the delay", () => {
    const capability = atom(false);
    render(
      <ProgressiveBoundary
        requires={capability}
        delay={5000}
        fallback={<span>wait</span>}
      >
        <span>content</span>
      </ProgressiveBoundary>,
      { wrapper },
    );
    expect(screen.queryByText("wait")).not.toBeInTheDocument();

    act(() => store.set(capability, true));
    expect(screen.getByText("content")).toBeInTheDocument();
  });
});
