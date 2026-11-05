/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const logger = vi.hoisted(() => ({
  log: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
}));
vi.mock("@/utils/Logger", () => ({ Logger: logger }));
vi.mock("@/core/hotkeys/shortcuts", () => ({ isPlatformMac: () => true }));

describe("VS Code paste messages", () => {
  const originalUrl = window.location.href;
  const setData = vi.fn();
  let parent: Window;
  let child: Window;
  let input: HTMLTextAreaElement;
  let cleanupListeners: () => void;
  const onPaste = vi.fn();

  beforeEach(async () => {
    vi.resetModules();
    const parentFrame = document.createElement("iframe");
    const childFrame = document.createElement("iframe");
    input = document.createElement("textarea");
    document.body.append(parentFrame, childFrame, input);
    if (!parentFrame.contentWindow || !childFrame.contentWindow) {
      throw new Error("Test frames need windows");
    }
    parent = parentFrame.contentWindow;
    child = childFrame.contentWindow;
    vi.stubGlobal("parent", parent);
    vi.stubGlobal(
      "DataTransfer",
      class {
        public setData = setData;
      },
    );
    vi.stubGlobal(
      "ClipboardEvent",
      class extends Event {
        public clipboardData: DataTransfer | undefined;
        public constructor(type: string, init: ClipboardEventInit) {
          super(type);
          this.clipboardData = init.clipboardData ?? undefined;
        }
      },
    );
    window.history.replaceState(null, "", "?vscode=true");
    input.addEventListener("paste", onPaste);
    input.focus();
    const windowListeners = vi.spyOn(window, "addEventListener");
    const documentListeners = vi.spyOn(document, "addEventListener");
    cleanupListeners = () => {
      for (const [type, listener, options] of windowListeners.mock.calls) {
        window.removeEventListener(type, listener, options);
      }
      for (const [type, listener, options] of documentListeners.mock.calls) {
        document.removeEventListener(type, listener, options);
      }
    };
    const { maybeRegisterVSCodeBindings } = await import("../vscode-bindings");
    maybeRegisterVSCodeBindings();
  });

  afterEach(() => {
    cleanupListeners();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    document.body.replaceChildren();
    window.history.replaceState(null, "", originalUrl);
  });

  function send(data: unknown, source: Window | null = parent) {
    window.dispatchEvent(
      new MessageEvent("message", {
        data,
        source,
        origin: "vscode-webview://dynamic-parent",
      }),
    );
  }

  it.each(["clipboard text", ""])(
    "accepts parent paste with text %j",
    (text) => {
      send({ command: "paste", text });
      expect(setData).toHaveBeenCalledWith("text/plain", text);
      expect(onPaste).toHaveBeenCalledOnce();
      expect(logger.error).not.toHaveBeenCalled();
    },
  );

  it("rejects a child frame even when its reported origin matches", () => {
    send({ command: "paste", text: "unsolicited" }, child);
    expect(onPaste).not.toHaveBeenCalled();
    expect(setData).not.toHaveBeenCalled();
  });

  it("rejects a message without a source window", () => {
    send({ command: "paste", text: "unsolicited" }, null);
    expect(onPaste).not.toHaveBeenCalled();
  });

  it.each(
    [
      null,
      [],
      {},
      "paste",
      1,
      true,
      { command: "paste" },
      { command: "paste", text: {} },
      { command: "paste", text: 12 },
      { command: "paste", text: null },
      { command: "execute", text: "unexpected" },
    ].map((data) => ({ data })),
  )("ignores malformed parent messages without errors: %j", ({ data }) => {
    send(data);
    expect(onPaste).not.toHaveBeenCalled();
    expect(setData).not.toHaveBeenCalled();
    expect(logger.error).not.toHaveBeenCalled();
  });
});
