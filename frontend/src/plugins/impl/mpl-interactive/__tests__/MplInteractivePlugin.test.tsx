/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */
/* oxlint-disable marimo/prefer-object-params -- the mocked mpl.js figure
   constructor must match its real positional signature. */
import { render, waitFor } from "@testing-library/react";
import type { ExtractAtomValue } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { userConfigAtom } from "@/core/config/config";
import { parseUserConfig } from "@/core/config/config-schema";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { Model } from "@/plugins/impl/anywidget/model";
import { WIDGET_REGISTRY } from "@/plugins/impl/anywidget/registry";
import type { ModelState, WidgetModelId } from "@/plugins/impl/anywidget/types";
import { visibleForTesting } from "../MplInteractivePlugin";

const { ensureMplJs, injectCss, MplInteractiveSlot, resetMplJsLoading } =
  visibleForTesting;

/**
 * Clear every "notebook trust" signal `isTrustedVirtualFileUrl` consults so
 * the rejection cases below test the actually-untrusted branch. Positive
 * export-context trust is covered centrally in trusted-url.test.ts.
 */
function clearTrustSignals() {
  store.set(hasRunAnyCellAtom, false);
  const cleared = parseUserConfig({});
  store.set(userConfigAtom, {
    ...cleared,
    runtime: { ...cleared.runtime, auto_instantiate: false },
  });
  store.set(initialModeAtom, "edit");
}

describe("MplInteractivePlugin URL validation", () => {
  let previousConfig: ExtractAtomValue<typeof userConfigAtom>;
  let previousMode: ExtractAtomValue<typeof initialModeAtom>;
  let previousHasRunAnyCell: ExtractAtomValue<typeof hasRunAnyCellAtom>;

  beforeEach(() => {
    previousConfig = store.get(userConfigAtom);
    previousMode = store.get(initialModeAtom);
    previousHasRunAnyCell = store.get(hasRunAnyCellAtom);
    clearTrustSignals();
    // Reset module-level script-loading state and any stubs.
    delete (window as { mpl?: unknown }).mpl;
    resetMplJsLoading();
    // Remove any scripts the tests added to document.head.
    for (const el of document.head.querySelectorAll(
      "script[data-test-mpl],link[data-test-mpl]",
    )) {
      el.remove();
    }
  });

  afterEach(() => {
    vi.restoreAllMocks();
    store.set(userConfigAtom, previousConfig);
    store.set(initialModeAtom, previousMode);
    store.set(hasRunAnyCellAtom, previousHasRunAnyCell);
  });

  describe("ensureMplJs", () => {
    it("rejects the PoC attack URL without creating a <script>", async () => {
      const appendSpy = vi.spyOn(document.head, "append");
      await expect(ensureMplJs("http://127.0.0.1:8820/poc.js")).rejects.toThrow(
        /untrusted/i,
      );
      expect(appendSpy).not.toHaveBeenCalled();
    });

    it.each([
      "https://evil.example.com/x.js",
      "//evil.example.com/x.js",
      "javascript:alert(1)",
      // Data URL is rejected only in an untrusted context. WASM/autoInstantiate
      // intentionally accepts it — covered by trusted-url.test.ts.
      "data:text/javascript;base64,YWxlcnQoMSk=",
      "./@file/x.js?redirect=http://evil.com",
    ])("rejects %s", async (url) => {
      const appendSpy = vi.spyOn(document.head, "append");
      await expect(ensureMplJs(url)).rejects.toThrow(/untrusted/i);
      expect(appendSpy).not.toHaveBeenCalled();
    });

    it("is a no-op when window.mpl is already present", async () => {
      (window as { mpl?: unknown }).mpl = {};
      const appendSpy = vi.spyOn(document.head, "append");
      // Even a malicious URL should be ignored — short-circuit happens first.
      await expect(
        ensureMplJs("http://evil.example.com/x.js"),
      ).resolves.toBeUndefined();
      expect(appendSpy).not.toHaveBeenCalled();
    });

    it("creates a <script src> for a trusted virtual file URL", async () => {
      const appendSpy = vi
        .spyOn(document.head, "append")
        .mockImplementation((...nodes) => {
          // Simulate a successful load so ensureMplJs resolves.
          for (const node of nodes) {
            if (node instanceof HTMLScriptElement) {
              queueMicrotask(() => node.onload?.(new Event("load")));
            }
          }
        });

      await expect(ensureMplJs("./@file/123-mpl.js")).resolves.toBeUndefined();

      expect(appendSpy).toHaveBeenCalledTimes(1);
      const appended = appendSpy.mock.calls[0][0] as HTMLScriptElement;
      expect(appended.tagName).toBe("SCRIPT");
      expect(appended.src).toContain("@file/123-mpl.js");
    });
  });

  describe("injectCss", () => {
    it("refuses to append <link> for the PoC attack CSS URL", () => {
      const container = document.createElement("div");
      const loggerSpy = vi
        .spyOn(Logger, "error")
        .mockImplementation(() => undefined);

      const cleanup = injectCss(container, "http://127.0.0.1:8820/x.css");

      expect(container.querySelector("link")).toBeNull();
      expect(loggerSpy).toHaveBeenCalledWith(
        expect.stringContaining("untrusted"),
      );
      // Cleanup must be safe to call even when nothing was appended.
      expect(() => cleanup()).not.toThrow();
    });

    it.each([
      "https://evil.example.com/x.css",
      "javascript:alert(1)",
      "data:text/css,body{background:red}",
    ])("refuses to append <link> for %s", (url) => {
      const container = document.createElement("div");
      vi.spyOn(Logger, "error").mockImplementation(() => undefined);

      injectCss(container, url);

      expect(container.querySelector("link")).toBeNull();
    });

    it("appends a <link> for a trusted virtual file URL", () => {
      const container = document.createElement("div");

      const cleanup = injectCss(container, "./@file/456-mpl.css");

      const link = container.querySelector("link");
      expect(link).not.toBeNull();
      expect(link?.rel).toBe("stylesheet");
      expect(link?.getAttribute("href")).toBe("./@file/456-mpl.css");

      cleanup();
      expect(container.querySelector("link")).toBeNull();
    });
  });
});

const asModelId = (id: string): WidgetModelId => id as WidgetModelId;

/**
 * Minimal stand-in for the global `window.mpl.figure` constructor. mpl.js
 * builds the canvas DOM and wires `onopen`/`onmessage` onto the socket at
 * construction; the mock reproduces just enough of that for the slot to mount
 * and rebind.
 */
function installMplFigureMock(): ReturnType<typeof vi.fn> {
  const ctor = vi.fn(function (
    this: any,
    id: string,
    ws: any,
    _ondownload: unknown,
    container: HTMLElement,
  ) {
    this.id = id;
    this.ws = ws;
    const root = document.createElement("div");
    const canvasDiv = document.createElement("div");
    canvasDiv.setAttribute("tabindex", "0");
    root.append(canvasDiv);
    container.append(root);
    this.root = root;
    this.send_message = vi.fn();
    ws.onopen = vi.fn();
    ws.onmessage = vi.fn();
  });
  (window as unknown as { mpl: unknown }).mpl = {
    figure: ctor,
    toolbar_items: [],
  };
  return ctor;
}

function makeModel(): Model<ModelState> {
  return new Model<ModelState>(
    {},
    {
      sendUpdate: vi.fn().mockResolvedValue(undefined),
      sendCustomMessage: vi.fn().mockResolvedValue(undefined),
    },
  );
}

function makeProps(modelId: WidgetModelId) {
  return {
    data: {
      mplJsUrl: "./@file/1-mpl.js",
      cssUrl: "./@file/2-mpl.css",
      toolbarImages: {},
      width: 640,
      height: 480,
    },
    value: { model_id: modelId },
    host: document.createElement("div"),
    setValue: vi.fn(),
    functions: {},
  } as any;
}

describe("MplInteractiveSlot rerun rebinding", () => {
  beforeEach(() => {
    vi.spyOn(Logger, "error").mockImplementation(() => undefined);
    resetMplJsLoading();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete (window as { mpl?: unknown }).mpl;
  });

  it("rebinds to a new model without rebuilding the figure DOM", async () => {
    const ctor = installMplFigureMock();
    const idA = asModelId("model-a");
    const idB = asModelId("model-b");
    WIDGET_REGISTRY.setModel(idA, makeModel());
    WIDGET_REGISTRY.setModel(idB, makeModel());

    const { container, rerender } = render(
      <MplInteractiveSlot {...makeProps(idA)} />,
    );

    await waitFor(() => expect(ctor).toHaveBeenCalledTimes(1));

    const figureRoot = ctor.mock.instances[0].root as HTMLElement;
    const socket = ctor.mock.calls[0][1];
    const slot = container.querySelector(".mpl-interactive-figure");
    expect(slot?.contains(figureRoot)).toBe(true);
    // One handshake on the initial bind.
    expect(socket.onopen).toHaveBeenCalledTimes(1);
    const setSendHandler = vi.spyOn(socket, "setSendHandler");

    // Cell re-run: only the model id changes.
    rerender(<MplInteractiveSlot {...makeProps(idB)} />);

    // The new model is bound through the existing socket, with a fresh
    // handshake, and the figure is never reconstructed.
    await waitFor(() => expect(socket.onopen).toHaveBeenCalledTimes(2));
    expect(ctor).toHaveBeenCalledTimes(1);
    expect(setSendHandler).toHaveBeenCalledTimes(1);
    // The same rendered DOM is still in place — not cleared and rebuilt.
    expect(container.querySelector(".mpl-interactive-figure")).toBe(slot);
    expect(slot?.contains(figureRoot)).toBe(true);
  });

  it("detaches the previous model's listener on each rerun (no buildup)", async () => {
    installMplFigureMock();
    // Unique ids: WIDGET_REGISTRY is a module singleton whose deferreds resolve
    // once, so reusing ids from another test would return that test's models.
    const idA = asModelId("leak-a");
    const idB = asModelId("leak-b");
    const idC = asModelId("leak-c");
    const modelA = makeModel();
    const modelB = makeModel();
    const modelC = makeModel();
    WIDGET_REGISTRY.setModel(idA, modelA);
    WIDGET_REGISTRY.setModel(idB, modelB);
    WIDGET_REGISTRY.setModel(idC, modelC);

    const onA = vi.spyOn(modelA, "on");
    const offA = vi.spyOn(modelA, "off");
    const onB = vi.spyOn(modelB, "on");
    const offB = vi.spyOn(modelB, "off");
    const onC = vi.spyOn(modelC, "on");
    const offC = vi.spyOn(modelC, "off");

    const { rerender } = render(<MplInteractiveSlot {...makeProps(idA)} />);
    await waitFor(() =>
      expect(onA).toHaveBeenCalledWith("msg:custom", expect.any(Function)),
    );

    rerender(<MplInteractiveSlot {...makeProps(idB)} />);
    await waitFor(() => expect(onB).toHaveBeenCalled());

    rerender(<MplInteractiveSlot {...makeProps(idC)} />);
    await waitFor(() => expect(onC).toHaveBeenCalled());

    // Each superseded model had its listener detached exactly once when the
    // next bind replaced it; the current model's listener stays attached.
    expect(offA).toHaveBeenCalledTimes(1);
    expect(offB).toHaveBeenCalledTimes(1);
    expect(offC).not.toHaveBeenCalled();
  });
});
