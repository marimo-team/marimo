/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { userConfigAtom } from "@/core/config/config";
import { parseUserConfig } from "@/core/config/config-schema";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { isTrustedVirtualFileUrl } from "../trusted-url";

type ExportContextWindow = Window & {
  __MARIMO_EXPORT_CONTEXT__?: {
    trusted: true;
    notebookCode?: string;
  };
  __MARIMO_STATIC__?: unknown;
};

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
  const cleared = parseUserConfig({});
  store.set(userConfigAtom, {
    ...cleared,
    runtime: { ...cleared.runtime, auto_instantiate: value },
  });
}

function clearTrustSignals() {
  store.set(hasRunAnyCellAtom, false);
  setAutoInstantiate(false);
  store.set(initialModeAtom, "edit");
}

describe("isTrustedVirtualFileUrl", () => {
  let windowWithExportContext: ExportContextWindow;
  let trustStateSnapshot: ReturnType<typeof snapshotTrustState>;

  beforeEach(() => {
    windowWithExportContext = window as ExportContextWindow;
    trustStateSnapshot = snapshotTrustState();
    clearTrustSignals();
    delete windowWithExportContext.__MARIMO_EXPORT_CONTEXT__;
    delete windowWithExportContext.__MARIMO_STATIC__;
  });

  afterEach(() => {
    restoreTrustState(trustStateSnapshot);
    delete windowWithExportContext.__MARIMO_EXPORT_CONTEXT__;
    delete windowWithExportContext.__MARIMO_STATIC__;
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
   * supported and unsupported trust signal.
   */
  describe("data URL acceptance", () => {
    const SAFE_DATA_URLS = [
      "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
      "data:application/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
      "data:text/css;base64,Ym9keXt9",
    ];

    it.each(SAFE_DATA_URLS)(
      "accepts %s once the user has run a cell",
      (url) => {
        store.set(hasRunAnyCellAtom, true);
        expect(isTrustedVirtualFileUrl(url)).toBe(true);
      },
    );

    it("accepts safe data URL when trusted export context is present", () => {
      windowWithExportContext.__MARIMO_EXPORT_CONTEXT__ = {
        trusted: true,
        notebookCode: "import marimo\napp = marimo.App()",
      };
      expect(
        isTrustedVirtualFileUrl(
          "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
        ),
      ).toBe(true);
    });

    it("rejects safe data URL when only read mode is present", () => {
      store.set(initialModeAtom, "read");
      expect(
        isTrustedVirtualFileUrl(
          "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
        ),
      ).toBe(false);
    });

    it("rejects safe data URL when only auto_instantiate is enabled", () => {
      setAutoInstantiate(true);
      expect(
        isTrustedVirtualFileUrl(
          "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
        ),
      ).toBe(false);
    });

    it("rejects safe data URL when only a marimo-code tag is present", () => {
      const tag = document.createElement("marimo-code");
      tag.textContent = encodeURIComponent("import marimo\napp = marimo.App()");
      document.body.appendChild(tag);
      try {
        expect(
          isTrustedVirtualFileUrl(
            "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
          ),
        ).toBe(false);
      } finally {
        tag.remove();
      }
    });

    it("rejects safe data URL when only __MARIMO_STATIC__ is present", () => {
      windowWithExportContext.__MARIMO_STATIC__ = { files: {} };
      expect(
        isTrustedVirtualFileUrl(
          "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
        ),
      ).toBe(false);
    });

    it.each([
      // Non-base64 data URLs are refused because the unencoded payload
      // broadens the parsing/loading surface for attacker-controlled content.
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
