/* Copyright 2026 Marimo. All rights reserved. */
import type { ExtractAtomValue } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { userConfigAtom } from "@/core/config/config";
import { parseUserConfig } from "@/core/config/config-schema";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { loadPanelExtension } from "../PanelPlugin";

/**
 * Force the "no notebook trust" branch so the `data:` URL rejection below
 * actually exercises the untrusted path. Positive export-context trust is
 * covered centrally in trusted-url.test.ts.
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

describe("loadPanelExtension", () => {
  let previousConfig: ExtractAtomValue<typeof userConfigAtom>;
  let previousMode: ExtractAtomValue<typeof initialModeAtom>;
  let previousHasRunAnyCell: ExtractAtomValue<typeof hasRunAnyCellAtom>;

  beforeEach(() => {
    previousConfig = store.get(userConfigAtom);
    previousMode = store.get(initialModeAtom);
    previousHasRunAnyCell = store.get(hasRunAnyCellAtom);
    clearTrustSignals();
    for (const el of document.head.querySelectorAll("script")) {
      el.remove();
    }
  });

  afterEach(() => {
    vi.restoreAllMocks();
    store.set(userConfigAtom, previousConfig);
    store.set(initialModeAtom, previousMode);
    store.set(hasRunAnyCellAtom, previousHasRunAnyCell);
  });

  it("does nothing and returns false for null URL", () => {
    const appendSpy = vi.spyOn(document.head, "append");
    expect(loadPanelExtension(null)).toBe(false);
    expect(appendSpy).not.toHaveBeenCalled();
  });

  it("refuses to load the PoC attack URL", () => {
    const appendSpy = vi.spyOn(document.head, "append");
    const loggerSpy = vi.spyOn(Logger, "error").mockImplementation(() => {});

    expect(loadPanelExtension("http://127.0.0.1:8820/poc.js")).toBe(false);

    expect(appendSpy).not.toHaveBeenCalled();
    expect(loggerSpy).toHaveBeenCalledWith(
      expect.stringContaining("untrusted"),
    );
  });

  it.each([
    "https://evil.example.com/x.js",
    "//evil.example.com/x.js",
    // Data URL is rejected only in an untrusted context — the WASM fallback
    // legitimately produces these, so trusted-url.test.ts covers the
    // positive path when a notebook trust signal is set.
    "data:text/javascript;base64,YWxlcnQoMSk=",
    "javascript:alert(1)",
    "./@file/x.js#http://evil.com",
  ])("refuses to load %s", (url) => {
    const appendSpy = vi.spyOn(document.head, "append");
    vi.spyOn(Logger, "error").mockImplementation(() => {});

    expect(loadPanelExtension(url)).toBe(false);
    expect(appendSpy).not.toHaveBeenCalled();
  });

  it("appends a <script src> for a trusted virtual file URL", () => {
    expect(loadPanelExtension("./@file/42-bokeh.js")).toBe(true);

    const script = document.head.querySelector("script");
    expect(script).not.toBeNull();
    expect(script?.src).toContain("@file/42-bokeh.js");
    // Must NOT populate innerHTML — that was the original vulnerability sink.
    expect(script?.innerHTML).toBe("");
  });
});
