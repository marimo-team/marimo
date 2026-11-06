/* Copyright 2026 Marimo. All rights reserved. */
import { act, render } from "@testing-library/react";
import { Provider } from "jotai";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { OutputRenderer } from "@/components/editor/Output";
import { configOverridesAtom } from "@/core/config/config";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { VideoOutput } from "../VideoOutput";

function snapshotTrustState() {
  return {
    hasRunAnyCell: store.get(hasRunAnyCellAtom),
    overrides: store.get(configOverridesAtom),
    mode: store.get(initialModeAtom),
    exportContext: window.__MARIMO_EXPORT_CONTEXT__,
  };
}

describe("VideoOutput", () => {
  let previous: ReturnType<typeof snapshotTrustState>;

  beforeEach(() => {
    previous = snapshotTrustState();
    store.set(hasRunAnyCellAtom, false);
    store.set(configOverridesAtom, { runtime: { auto_instantiate: false } });
    store.set(initialModeAtom, "edit");
    delete window.__MARIMO_EXPORT_CONTEXT__;
  });

  afterEach(() => {
    store.set(hasRunAnyCellAtom, previous.hasRunAnyCell);
    store.set(configOverridesAtom, previous.overrides);
    store.set(initialModeAtom, previous.mode);
    if (previous.exportContext) {
      window.__MARIMO_EXPORT_CONTEXT__ = previous.exportContext;
    } else {
      delete window.__MARIMO_EXPORT_CONTEXT__;
    }
  });

  function renderVideo(src = "https://example.com/video.mp4") {
    return render(
      <Provider store={store}>
        <VideoOutput src={src} className="output" />
      </Provider>,
    );
  }

  it.each([
    "https://example.com/video.mp4",
    "data:video/mp4;base64,AAAA",
    "./@file/123-video.mp4",
  ])("preserves the media source and controls before execution: %s", (src) => {
    const { container } = renderVideo(src);
    const video = container.querySelector("video");
    expect(video).toHaveAttribute("src", src);
    expect(video).toHaveAttribute("controls");
    expect(video).toHaveClass("output");
    expect(container.querySelector("iframe")).toBeNull();
  });

  it("keeps direct and JSON video outputs out of frames before execution", () => {
    const src = `data:text/html,${encodeURIComponent("<script>parent.postMessage('cached-video', '*')</script>")}`;
    const { container } = render(
      <Provider store={store}>
        <OutputRenderer
          message={{ channel: "output", mimetype: "video/mp4", data: src }}
        />
        <OutputRenderer
          message={{
            channel: "output",
            mimetype: "application/json",
            data: { video: `video/mp4:${src}` },
          }}
        />
      </Provider>,
    );
    expect(container.querySelector("iframe")).toBeNull();
    const videos = container.querySelectorAll("video");
    expect(videos).toHaveLength(2);
    for (const video of videos) {
      expect(video).toHaveAttribute("src", src);
    }
  });

  it("updates an existing output after the user runs a cell", () => {
    const { container } = renderVideo();
    expect(container.querySelector("video")).not.toBeNull();
    act(() => store.set(hasRunAnyCellAtom, true));
    expect(container.querySelector("video")).toBeNull();
    expect(container.querySelector("iframe")).toHaveAttribute(
      "src",
      "https://example.com/video.mp4",
    );
  });

  it.each(["app", "auto-instantiate", "export"] as const)(
    "preserves iframe output in a trusted %s context",
    (context) => {
      switch (context) {
        case "app":
          store.set(initialModeAtom, "read");
          break;
        case "auto-instantiate":
          store.set(configOverridesAtom, {
            runtime: { auto_instantiate: true },
          });
          break;
        case "export":
          window.__MARIMO_EXPORT_CONTEXT__ = { trusted: true };
          break;
      }
      const { container } = renderVideo();
      expect(container.querySelector("video")).toBeNull();
      expect(container.querySelector("iframe")).toHaveAttribute(
        "title",
        "Video output",
      );
      expect(container.querySelector("iframe")).toHaveClass("output");
    },
  );

  it("uses native video before the app mode is initialized", () => {
    store.set(initialModeAtom, undefined);
    const { container } = renderVideo();
    expect(container.querySelector("video")).not.toBeNull();
    expect(container.querySelector("iframe")).toBeNull();
  });
});
