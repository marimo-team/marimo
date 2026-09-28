/* Copyright 2026 Marimo. All rights reserved. */
import { act, render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useIsFullScreen } from "../fullscreen";

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
