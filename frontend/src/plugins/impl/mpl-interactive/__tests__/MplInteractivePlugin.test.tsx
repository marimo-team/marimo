/* Copyright 2026 Marimo. All rights reserved. */
import type { ExtractAtomValue } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { userConfigAtom } from "@/core/config/config";
import { parseUserConfig } from "@/core/config/config-schema";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { visibleForTesting } from "../MplInteractivePlugin";

const { ensureMplJs, injectCss, resetMplJsLoading } = visibleForTesting;

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
      const loggerSpy = vi.spyOn(Logger, "error").mockImplementation(() => {});

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
      vi.spyOn(Logger, "error").mockImplementation(() => {});

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
