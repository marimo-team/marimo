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
  const originalInnerWidth = window.innerWidth;
  const originalInnerHeight = window.innerHeight;
  let intersectionCallback: IntersectionObserverCallback;
  let observedElement: Element | undefined;

  beforeEach(() => {
    vi.stubGlobal(
      "PointerEvent",
      class PointerEvent extends MouseEvent {
        readonly pointerId: number;
        readonly pointerType: string;

        constructor(type: string, init: PointerEventInit = {}) {
          super(type, init);
          this.pointerId = init.pointerId ?? 0;
          this.pointerType = init.pointerType ?? "";
        }
      },
    );
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );

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
    setViewport(originalInnerWidth, originalInnerHeight);
    vi.unstubAllGlobals();
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

  test("shows a placeholder that can return the floating video", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ width: 640, height: 360 }),
    );
    expect(
      screen.queryByTestId("marimo-video-placeholder"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Float video" }));

    expect(
      screen.getByText("Video is playing in a floating window"),
    ).toHaveRole("status");
    const placeholder = screen.getByTestId("marimo-video-placeholder");
    expect(placeholder).toHaveClass("h-full", "w-full");
    expect(placeholder).toHaveStyle({ borderRadius: "4px" });

    fireEvent.click(screen.getByRole("button", { name: "Return video here" }));

    expect(
      screen.queryByTestId("marimo-video-placeholder"),
    ).not.toBeInTheDocument();
    expect(portalContainer.parentElement).toBe(
      screen.getByTestId("marimo-video-anchor"),
    );
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

  test("keeps a manually floated video docked until its output is visible", () => {
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
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));

    getBoundingClientRect.mockReturnValue(rectAt(-400));
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

  test("restores host styles when unmounted", () => {
    const host = document.createElement("marimo-video");
    host.style.display = "block";
    host.style.maxWidth = "80%";
    host.style.width = "320px";
    const result = render(<VideoComponent data={data} host={host} />);

    expect(host).toHaveStyle({
      display: "inline-block",
      maxWidth: "100%",
      width: "640px",
    });

    result.unmount();

    expect(host).toHaveStyle({
      display: "block",
      maxWidth: "80%",
      width: "320px",
    });
  });

  test("remounts for playback changes but not cosmetic changes", () => {
    const host = document.createElement("marimo-video");
    const result = render(<VideoComponent data={data} host={host} />);
    const initialVideo = screen.getByTestId("marimo-video");

    result.rerender(
      <VideoComponent data={{ ...data, loop: true }} host={host} />,
    );
    const loopedVideo = screen.getByTestId("marimo-video");
    expect(loopedVideo).not.toBe(initialVideo);

    result.rerender(
      <VideoComponent
        data={{ ...data, loop: true, rounded: false }}
        host={host}
      />,
    );
    expect(screen.getByTestId("marimo-video")).toBe(loopedVideo);
  });

  test("resizes from the inward corner while preserving aspect ratio", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ width: 640, height: 360 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));

    const resizeCorner = screen.getByTestId("marimo-video-resize-corner");
    fireEvent.pointerDown(resizeCorner, {
      pointerId: 1,
      button: 0,
      clientX: 500,
      clientY: 300,
    });
    fireEvent.pointerMove(document.body, {
      pointerId: 1,
      clientX: 400,
      clientY: 300,
    });
    fireEvent.pointerUp(document.body, {
      pointerId: 1,
      clientX: 400,
      clientY: 300,
    });

    expect(portalContainer).toHaveStyle({
      width: "460px",
      height: "258.75px",
    });
  });

  test("drags the video itself and flicks it to another corner", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    const getBoundingClientRect = vi.spyOn(
      portalContainer,
      "getBoundingClientRect",
    );
    getBoundingClientRect.mockReturnValue(
      rect({ left: 100, top: 100, width: 640, height: 360 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));
    getBoundingClientRect.mockReturnValue(
      rect({ left: 648, top: 501.5, width: 360, height: 202.5 }),
    );

    const video = screen.getByTestId("marimo-video");
    fireEvent.pointerDown(video, {
      pointerId: 1,
      button: 0,
      clientX: 800,
      clientY: 600,
    });
    fireEvent.pointerMove(document.body, {
      pointerId: 1,
      clientX: 100,
      clientY: 100,
    });
    fireEvent.pointerUp(document.body, {
      pointerId: 1,
      clientX: 100,
      clientY: 100,
    });

    expect(portalContainer).toHaveStyle({
      left: "16px",
      top: "16px",
      width: "360px",
      height: "202.5px",
    });
    expect(screen.queryByTestId("marimo-video-move")).not.toBeInTheDocument();
    expect(screen.queryByTestId("marimo-video-resize")).not.toBeInTheDocument();
  });

  test("does not start dragging until the pointer moves", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ left: 648, top: 501.5, width: 360, height: 202.5 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));

    const video = screen.getByTestId("marimo-video");
    fireEvent.pointerDown(video, {
      pointerId: 1,
      button: 0,
      clientX: 800,
      clientY: 600,
    });
    fireEvent.pointerUp(window, {
      pointerId: 1,
      clientX: 800,
      clientY: 600,
    });

    expect(portalContainer.style.left).toContain("100vw");
    expect(portalContainer.style.top).toContain("100vh");
  });

  test("does not move the floating video on hover", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ left: 648, top: 501.5, width: 360, height: 202.5 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));

    fireEvent.pointerMove(screen.getByTestId("marimo-video"), {
      pointerId: 1,
      clientX: 100,
      clientY: 100,
    });

    expect(portalContainer.style.left).toContain("100vw");
    expect(portalContainer.style.top).toContain("100vh");
  });

  test("cancels dragging when the mouse button is no longer pressed", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ left: 648, top: 501.5, width: 360, height: 202.5 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));
    fireEvent.pointerDown(screen.getByTestId("marimo-video"), {
      pointerId: 1,
      pointerType: "mouse",
      button: 0,
      buttons: 1,
      clientX: 800,
      clientY: 600,
    });
    fireEvent.pointerMove(document.body, {
      pointerId: 1,
      pointerType: "mouse",
      buttons: 0,
      clientX: 100,
      clientY: 100,
    });

    expect(portalContainer.style.left).toContain("100vw");
    expect(portalContainer.style.top).toContain("100vh");
  });

  test("cancels rather than snaps when the pointer is canceled", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ left: 648, top: 501.5, width: 360, height: 202.5 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));
    fireEvent.pointerDown(screen.getByTestId("marimo-video"), {
      pointerId: 1,
      pointerType: "mouse",
      button: 0,
      buttons: 1,
      clientX: 800,
      clientY: 550,
    });
    fireEvent.pointerMove(window, {
      pointerId: 1,
      pointerType: "mouse",
      buttons: 1,
      clientX: 100,
      clientY: 100,
    });
    fireEvent.pointerCancel(window, { pointerId: 1 });

    expect(portalContainer.style.left).toContain("100vw");
    expect(portalContainer.style.top).toContain("100vh");
  });

  test("leaves the native control strip available for video controls", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ left: 648, top: 501.5, width: 360, height: 202.5 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));
    fireEvent.pointerDown(screen.getByTestId("marimo-video"), {
      pointerId: 1,
      pointerType: "mouse",
      button: 0,
      buttons: 1,
      clientX: 800,
      clientY: 690,
    });
    fireEvent.pointerMove(window, {
      pointerId: 1,
      pointerType: "mouse",
      buttons: 1,
      clientX: 100,
      clientY: 100,
    });
    fireEvent.pointerUp(window, {
      pointerId: 1,
      clientX: 100,
      clientY: 100,
    });

    expect(portalContainer.style.left).toContain("100vw");
    expect(portalContainer.style.top).toContain("100vh");
  });

  test("cancels resizing when the mouse button is no longer pressed", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ width: 640, height: 360 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));
    fireEvent.pointerDown(screen.getByTestId("marimo-video-resize-corner"), {
      pointerId: 1,
      pointerType: "mouse",
      button: 0,
      buttons: 1,
      clientX: 500,
      clientY: 300,
    });
    fireEvent.pointerMove(document.body, {
      pointerId: 1,
      pointerType: "mouse",
      buttons: 0,
      clientX: 400,
      clientY: 300,
    });

    expect(portalContainer).toHaveStyle({
      width: "360px",
      height: "202.5px",
    });
  });

  test("does not resize for movement below the gesture threshold", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ width: 640, height: 360 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));
    fireEvent.pointerDown(screen.getByTestId("marimo-video-resize-corner"), {
      pointerId: 1,
      button: 0,
      clientX: 500,
      clientY: 300,
    });
    fireEvent.pointerMove(document.body, {
      pointerId: 1,
      clientX: 497,
      clientY: 300,
    });
    fireEvent.pointerUp(document.body, {
      pointerId: 1,
      clientX: 497,
      clientY: 300,
    });

    expect(portalContainer).toHaveStyle({
      width: "360px",
      height: "202.5px",
    });
  });

  test("cancels a pending resize when a drag starts", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ left: 648, top: 501.5, width: 360, height: 202.5 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));
    fireEvent.pointerDown(screen.getByTestId("marimo-video-resize-corner"), {
      pointerId: 1,
      button: 0,
      clientX: 648,
      clientY: 501.5,
    });
    fireEvent.pointerDown(screen.getByTestId("marimo-video"), {
      pointerId: 1,
      button: 0,
      clientX: 800,
      clientY: 600,
    });
    fireEvent.pointerMove(document.body, {
      pointerId: 1,
      clientX: 100,
      clientY: 100,
    });
    fireEvent.pointerUp(document.body, {
      pointerId: 1,
      clientX: 100,
      clientY: 100,
    });

    expect(portalContainer).toHaveStyle({
      left: "16px",
      top: "16px",
      width: "360px",
      height: "202.5px",
    });
  });

  test("keeps the floating video inside a resized viewport", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ width: 640, height: 360 }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Float video" }));
    const resizeCorner = screen.getByTestId("marimo-video-resize-corner");
    fireEvent.pointerDown(resizeCorner, {
      pointerId: 1,
      button: 0,
      clientX: 500,
      clientY: 300,
    });
    fireEvent.pointerMove(window, {
      pointerId: 1,
      clientX: 200,
      clientY: 300,
    });
    fireEvent.pointerUp(window, {
      pointerId: 1,
      clientX: 200,
      clientY: 300,
    });
    expect(portalContainer).toHaveStyle({ width: "660px" });

    setViewport(400, 300);
    fireEvent(window, new Event("resize"));

    expect(portalContainer).toHaveStyle({
      width: "368px",
      height: "207px",
    });
    expect(portalContainer.style.left).toBe("calc(100vw - 384px)");
  });

  test("animates between inline and floating positions", () => {
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect")
      .mockReturnValueOnce(
        rect({ left: 100, top: 80, width: 640, height: 360 }),
      )
      .mockReturnValue(
        rect({ left: 648, top: 501.5, width: 360, height: 202.5 }),
      );
    const animation = { cancel: vi.fn() } as unknown as Animation;
    const animate = vi.fn(() => animation);
    Object.defineProperty(portalContainer, "animate", {
      configurable: true,
      value: animate,
    });

    fireEvent.click(screen.getByRole("button", { name: "Float video" }));

    expect(animate).toHaveBeenCalledWith(
      [
        expect.objectContaining({
          transform: expect.stringContaining("translate3d"),
          opacity: 0.88,
        }),
        expect.objectContaining({ transform: "none", opacity: 1 }),
      ],
      expect.objectContaining({ duration: 220 }),
    );
  });

  test("does not animate when reduced motion is preferred", () => {
    vi.mocked(window.matchMedia).mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as unknown as MediaQueryList);
    const host = document.createElement("marimo-video");
    render(<VideoComponent data={data} host={host} />);

    const portalContainer = screen.getByTestId("marimo-video-container");
    vi.spyOn(portalContainer, "getBoundingClientRect").mockReturnValue(
      rect({ left: 100, top: 80, width: 640, height: 360 }),
    );
    const animate = vi.fn();
    Object.defineProperty(portalContainer, "animate", {
      configurable: true,
      value: animate,
    });

    fireEvent.click(screen.getByRole("button", { name: "Float video" }));

    expect(animate).not.toHaveBeenCalled();
    expect(portalContainer).toHaveStyle({ transition: "none" });
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
    return rect({ top, width: 640, height: 360 });
  }

  function rect({
    left = 0,
    top = 0,
    width,
    height,
  }: {
    left?: number;
    top?: number;
    width: number;
    height: number;
  }): DOMRect {
    return {
      width,
      height,
      top,
      right: left + width,
      bottom: top + height,
      left,
      x: left,
      y: top,
      toJSON: () => ({}),
    };
  }

  function setViewport(width: number, height: number): void {
    Object.defineProperties(window, {
      innerWidth: { configurable: true, value: width },
      innerHeight: { configurable: true, value: height },
    });
  }
});
