/* Copyright 2026 Marimo. All rights reserved. */
import { act, render, renderHook } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useFullScreenClass, useIsFullScreen } from "../fullscreen";

describe("useFullScreenClass", () => {
  let fullscreenElement: Element | null = null;

  beforeEach(() => {
    fullscreenElement = null;
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      get: () => fullscreenElement,
    });
  });

  afterEach(() => {
    Reflect.deleteProperty(document, "fullscreenElement");
    document.documentElement.classList.remove("marimo-fullscreen");
  });

  it("reflects fullscreen state at mount and on entry and exit", () => {
    fullscreenElement = document.body;
    const { unmount } = renderHook(useFullScreenClass);
    expect(document.documentElement).toHaveClass("marimo-fullscreen");

    fullscreenElement = null;
    act(() => document.dispatchEvent(new Event("fullscreenchange")));
    expect(document.documentElement).not.toHaveClass("marimo-fullscreen");

    fullscreenElement = document.body;
    act(() => document.dispatchEvent(new Event("fullscreenchange")));
    expect(document.documentElement).toHaveClass("marimo-fullscreen");
    unmount();
  });

  it("removes the class and listener on unmount", () => {
    fullscreenElement = document.body;
    const { unmount } = renderHook(useFullScreenClass);
    unmount();
    expect(document.documentElement).not.toHaveClass("marimo-fullscreen");

    act(() => document.dispatchEvent(new Event("fullscreenchange")));
    expect(document.documentElement).not.toHaveClass("marimo-fullscreen");
  });
});

const FullScreenFlag = ({ label }: { label: string }) => {
  const ref = useRef<HTMLDivElement>(null);
  const isFullScreen = useIsFullScreen(ref);

  return (
    <div ref={ref} data-testid={label}>
      {String(isFullScreen)}
    </div>
  );
};

describe("useIsFullScreen", () => {
  let fullscreenElement: Element | null = null;

  beforeEach(() => {
    fullscreenElement = null;
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      get: () => fullscreenElement,
    });
  });

  afterEach(() => {
    Reflect.deleteProperty(document, "fullscreenElement");
  });

  const countFullScreenListeners = (calls: unknown[][]) =>
    calls.filter((call) => call[0] === "fullscreenchange").length;

  it("adds one document listener for many subscribers", () => {
    const addEventListener = vi.spyOn(document, "addEventListener");

    render(
      <>
        <FullScreenFlag label="first" />
        <FullScreenFlag label="second" />
        <FullScreenFlag label="third" />
      </>,
    );

    expect(countFullScreenListeners(addEventListener.mock.calls)).toBe(1);
    addEventListener.mockRestore();
  });

  it("removes the listener when the last subscriber unmounts", () => {
    const removeEventListener = vi.spyOn(document, "removeEventListener");

    const { unmount } = render(
      <>
        <FullScreenFlag label="first" />
        <FullScreenFlag label="second" />
      </>,
    );

    expect(countFullScreenListeners(removeEventListener.mock.calls)).toBe(0);

    unmount();

    expect(countFullScreenListeners(removeEventListener.mock.calls)).toBe(1);
    removeEventListener.mockRestore();
  });

  it("reports true for the full screen element only", () => {
    const { getByTestId } = render(
      <>
        <FullScreenFlag label="first" />
        <FullScreenFlag label="second" />
      </>,
    );

    expect(getByTestId("first")).toHaveTextContent("false");
    expect(getByTestId("second")).toHaveTextContent("false");

    fullscreenElement = getByTestId("second");
    act(() => {
      document.dispatchEvent(new Event("fullscreenchange"));
    });

    expect(getByTestId("first")).toHaveTextContent("false");
    expect(getByTestId("second")).toHaveTextContent("true");
  });
});
