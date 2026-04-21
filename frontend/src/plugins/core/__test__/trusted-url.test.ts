/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { userConfigAtom } from "@/core/config/config";
import { parseUserConfig } from "@/core/config/config-schema";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { isTrustedVirtualFileUrl } from "../trusted-url";

/**
 * Snapshot of all atoms that contribute to the "notebook trust established"
 * condition. Tests can flip them independently and we restore afterwards so
 * cases don't bleed into each other (Jotai state is module-global).
 */
function snapshotTrustState() {
  return {
    hasRunAnyCell: store.get(hasRunAnyCellAtom),
    userConfig: store.get(userConfigAtom),
    initialMode: store.get(initialModeAtom),
  };
}

function restoreTrustState(snapshot: ReturnType<typeof snapshotTrustState>) {
  store.set(hasRunAnyCellAtom, snapshot.hasRunAnyCell);
  store.set(userConfigAtom, snapshot.userConfig);
  store.set(initialModeAtom, snapshot.initialMode);
}

function setAutoInstantiate(value: boolean) {
  const current = store.get(userConfigAtom);
  store.set(userConfigAtom, {
    ...current,
    runtime: { ...current.runtime, auto_instantiate: value },
  });
}

/**
 * Fully untrusted baseline: no cell run, auto_instantiate off, edit mode.
 * All trust signals off so only the explicit overrides in a given test apply.
 */
function clearTrustSignals() {
  store.set(hasRunAnyCellAtom, false);
  store.set(userConfigAtom, parseUserConfig({}));
  setAutoInstantiate(false);
  store.set(initialModeAtom, "edit");
}

describe("isTrustedVirtualFileUrl", () => {
  let snapshot: ReturnType<typeof snapshotTrustState>;

  beforeEach(() => {
    snapshot = snapshotTrustState();
    clearTrustSignals();
  });

  afterEach(() => {
    restoreTrustState(snapshot);
  });

  it.each([
    "./@file/123-mpl.js",
    "./@file/456-mpl.css",
    "@file/789-bokeh.js",
    "/@file/0-empty.txt",
    "./@file/1234-name.with.dots.js",
  ])("accepts virtual file path %s", (url) => {
    expect(isTrustedVirtualFileUrl(url)).toBe(true);
  });

  it.each([
    // Attack vector from the vulnerability report
    "http://127.0.0.1:8820/poc.js",
    "https://evil.example.com/x.js",
    // Protocol-relative → takes attacker's origin
    "//evil.example.com/x.js",
    // Dangerous schemes
    "javascript:alert(1)",
    "data:text/javascript;base64,YWxlcnQoMSk=",
    "file:///etc/passwd",
    "blob:http://127.0.0.1/abc",
    // Almost-but-not virtual file paths
    "./evil.js",
    "../@file/x.js",
    "./malicious/@file/x.js",
    "@file",
    "@files/x.js",
    // Query/fragment smuggling
    "./@file/x.js?redirect=http://evil.com",
    "./@file/x.js#http://evil.com",
    // Empty and non-string
    "",
  ])("rejects %s", (url) => {
    expect(isTrustedVirtualFileUrl(url)).toBe(false);
  });

  it("rejects non-string input", () => {
    expect(isTrustedVirtualFileUrl(null)).toBe(false);
    expect(isTrustedVirtualFileUrl(undefined)).toBe(false);
    expect(isTrustedVirtualFileUrl(42)).toBe(false);
    expect(isTrustedVirtualFileUrl({})).toBe(false);
  });

  /**
   * Data URLs are the WASM / Pyodide fallback shape (see
   * `virtual_file.py`: when `virtual_files_supported=False`, files are
   * emitted directly as base64 data URLs). The tests below cover each
   * way the "notebook trust" signal can be established.
   */
  describe("data URL acceptance mirrors sanitize.ts trust signals", () => {
    const SAFE_DATA_URLS = [
      "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
      "data:application/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
      "data:text/css;base64,Ym9keXt9",
    ];

    it.each(SAFE_DATA_URLS)(
      "accepts %s once the user has run a cell (edit mode)",
      (url) => {
        store.set(hasRunAnyCellAtom, true);
        expect(isTrustedVirtualFileUrl(url)).toBe(true);
      },
    );

    it.each(SAFE_DATA_URLS)(
      "accepts %s when auto_instantiate is enabled",
      (url) => {
        setAutoInstantiate(true);
        expect(isTrustedVirtualFileUrl(url)).toBe(true);
      },
    );

    it.each(SAFE_DATA_URLS)(
      "accepts %s in read mode (marimo run / static HTML / WASM app)",
      (url) => {
        store.set(initialModeAtom, "read");
        expect(isTrustedVirtualFileUrl(url)).toBe(true);
      },
    );

    it.each([
      // Non-base64 data URLs are refused (length isn't delimited, attacker
      // payload could smuggle unescaped characters).
      "data:text/javascript,alert(1)",
      "data:text/javascript;charset=utf-8,alert(1)",
      // HTML / SVG / arbitrary types are refused even when trusted.
      "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
      "data:image/svg+xml;base64,PHN2Zy8+",
      "data:application/octet-stream;base64,AAA=",
    ])("still rejects unsafe data URL %s in trusted context", (url) => {
      store.set(hasRunAnyCellAtom, true);
      expect(isTrustedVirtualFileUrl(url)).toBe(false);
    });

    it("rejects data URLs when no trust signal is set", () => {
      expect(
        isTrustedVirtualFileUrl(
          "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
        ),
      ).toBe(false);
    });
  });
});
