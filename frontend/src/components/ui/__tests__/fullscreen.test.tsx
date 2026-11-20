/* Copyright 2026 Marimo. All rights reserved. */
import { act, render, renderHook } from "@testing-library/react";
import { useRef } from "react";
import { createPortal } from "react-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  useFullScreenClass,
  useFullScreenElement,
  useIsFullScreen,
  withFullScreenAsRoot,
} from "../fullscreen";

describe("full screen element inside a shadow root", () => {
  let host: HTMLElement;
  let target: HTMLElement;

  beforeEach(() => {
    host = document.createElement("div");
    host.append(document.createElement("div"));
    const shadowRoot = host.attachShadow({ mode: "open" });
    target = document.createElement("div");
    shadowRoot.append(target);
    document.body.append(host);

    // The browser retargets document.fullscreenElement to the shadow host and
    // reports the element itself on the shadow root.
    Object.defineProperty(document, "fullscreenElement", {
      configurable: true,
      get: () => host,
    });
    Object.defineProperty(shadowRoot, "fullscreenElement", {
      configurable: true,
      get: () => target,
    });
  });

  afterEach(() => {
    Reflect.deleteProperty(document, "fullscreenElement");
    host.remove();
  });

  it("resolves the element that is actually full screen", () => {
    const { result } = renderHook(useFullScreenElement);
    expect(result.current).toBe(target);
  });

  it("portals into that element, not the host's light DOM", () => {
    const Portal = withFullScreenAsRoot(
      ({ container }: { container?: Element | DocumentFragment | null }) =>
        createPortal(
          <span data-testid="portalled" />,
          container ?? document.body,
        ),
    );
    render(<Portal />);

    expect(host.children).toHaveLength(1);
    expect(target.querySelector('[data-testid="portalled"]')).not.toBeNull();
  });
});

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
