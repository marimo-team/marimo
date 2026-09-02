/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { type VideoData, VideoComponent, VideoPlugin } from "../VideoPlugin";

const data: VideoData = {
  src: "https://example.com/video.mp4",
  controls: true,
  muted: false,
  autoplay: false,
  loop: false,
  rounded: true,
  floating: "manual",
  width: "640px",
};

describe("VideoPlugin", () => {
  const originalIntersectionObserver = globalThis.IntersectionObserver;
  let intersectionCallback: IntersectionObserverCallback;
  let observedElement: Element | undefined;

  beforeEach(() => {
    globalThis.IntersectionObserver = class MockIntersectionObserver {
      readonly root = null;
      readonly rootMargin = "0px";
      readonly scrollMargin = "0px";
      readonly thresholds = [0];

      constructor(callback: IntersectionObserverCallback) {
        intersectionCallback = callback;
      }

      observe(element: Element) {
        observedElement = element;
      }

      unobserve() {
        // noop
      }

      disconnect() {
        // noop
      }

      takeRecords(): IntersectionObserverEntry[] {
        return [];
      }
    };
  });

  afterEach(() => {
    globalThis.IntersectionObserver = originalIntersectionObserver;
    observedElement = undefined;
  });

  test("validates floating video data", () => {
    const plugin = new VideoPlugin();
    expect(plugin.validator.parse(data)).toEqual(data);
  });

  test("moves the same video element between inline and floating positions", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const video = screen.getByTestId("marimo-video");
    const portalContainer = screen.getByTestId("marimo-video-container");
    const inlineAnchor = screen.getByTestId("marimo-video-anchor");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue({
      width: 640,
      height: 360,
      top: 0,
      right: 640,
      bottom: 360,
      left: 0,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });

    expect(portalContainer.parentElement).toBe(inlineAnchor);
    expect(video).toHaveAttribute("disablepictureinpicture");

    fireEvent.click(screen.getByRole("button", { name: "Float video" }));

    expect(screen.getByTestId("marimo-video")).toBe(video);
    expect(portalContainer.parentElement).toBe(document.body);
    expect(portalContainer).toHaveStyle({
      position: "fixed",
      width: "360px",
    });
    expect(inlineAnchor).toHaveStyle({ width: "640px", height: "360px" });

    fireEvent.click(
      screen.getByRole("button", { name: "Return video inline" }),
    );

    expect(screen.getByTestId("marimo-video")).toBe(video);
    expect(portalContainer.parentElement).toBe(inlineAnchor);
    expect(portalContainer).toHaveStyle({ position: "relative" });
  });

  test("auto-floats only after the video has first been visible", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={{ ...data, floating: "auto" }} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    const inlineAnchor = screen.getByTestId("marimo-video-anchor");
    vi.spyOn(inlineAnchor, "getBoundingClientRect").mockReturnValue({
      width: 640,
      height: 360,
      top: 100,
      right: 640,
      bottom: 460,
      left: 0,
      x: 0,
      y: 100,
      toJSON: () => ({}),
    });
    expect(observedElement).toBe(inlineAnchor);

    emitIntersection(false);
    expect(portalContainer.parentElement).toBe(inlineAnchor);

    emitIntersection(true);
    emitIntersection(false);
    expect(portalContainer.parentElement).toBe(document.body);

    emitIntersection(true);
    expect(portalContainer.parentElement).toBe(inlineAnchor);
  });

  test("re-arms auto-floating when manually docked in view", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={{ ...data, floating: "auto" }} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    const inlineAnchor = screen.getByTestId("marimo-video-anchor");
    vi.spyOn(inlineAnchor, "getBoundingClientRect").mockReturnValue({
      width: 640,
      height: 360,
      top: 100,
      right: 640,
      bottom: 460,
      left: 0,
      x: 0,
      y: 100,
      toJSON: () => ({}),
    });

    emitIntersection(true);
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Return video inline" }),
    );
    emitIntersection(false);

    expect(portalContainer.parentElement).toBe(document.body);
  });

  test("keeps auto-floating dismissed until the inline position is visible", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={{ ...data, floating: "auto" }} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    const inlineAnchor = screen.getByTestId("marimo-video-anchor");
    const getBoundingClientRect = vi.spyOn(
      inlineAnchor,
      "getBoundingClientRect",
    );
    getBoundingClientRect.mockReturnValue(rectAt(100));

    emitIntersection(true);
    getBoundingClientRect.mockReturnValue(rectAt(-400));
    emitIntersection(false);
    fireEvent.click(
      screen.getByRole("button", { name: "Return video inline" }),
    );
    emitIntersection(false);
    expect(portalContainer.parentElement).toBe(inlineAnchor);

    getBoundingClientRect.mockReturnValue(rectAt(100));
    emitIntersection(true);
    getBoundingClientRect.mockReturnValue(rectAt(-400));
    emitIntersection(false);
    expect(portalContainer.parentElement).toBe(document.body);
  });

  test("removes the portal container when unmounted", () => {
    const host = document.createElement("marimo-video");
    const result = render(<VideoComponent data={data} host={host} />);
    const portalContainer = screen.getByTestId("marimo-video-container");

    result.unmount();

    expect(portalContainer.isConnected).toBe(false);
  });

  function emitIntersection(isIntersecting: boolean): void {
    act(() => {
      intersectionCallback(
        [
          {
            isIntersecting,
            target: observedElement,
          } as IntersectionObserverEntry,
        ],
        {} as IntersectionObserver,
      );
    });
  }

  function rectAt(top: number): DOMRect {
    return {
      width: 640,
      height: 360,
      top,
      right: 640,
      bottom: top + 360,
      left: 0,
      x: 0,
      y: top,
      toJSON: () => ({}),
    };
  }
});
