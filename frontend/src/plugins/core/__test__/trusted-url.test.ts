/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { store } from "@/core/state/jotai";
import { isTrustedVirtualFileUrl } from "../trusted-url";

describe("isTrustedVirtualFileUrl", () => {
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

  describe("data URL exemption", () => {
    let previousHasRunAnyCell: boolean;

    beforeEach(() => {
      previousHasRunAnyCell = store.get(hasRunAnyCellAtom);
      store.set(hasRunAnyCellAtom, true);
    });

    afterEach(() => {
      store.set(hasRunAnyCellAtom, previousHasRunAnyCell);
    });

    it.each([
      "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
      "data:application/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
      "data:text/css;base64,Ym9keXt9",
    ])("accepts safe data URL %s after a cell has run", (url) => {
      expect(isTrustedVirtualFileUrl(url)).toBe(true);
    });

    it.each([
      // Non-base64 data URLs are refused
      "data:text/javascript,alert(1)",
      "data:text/javascript;charset=utf-8,alert(1)",
      // HTML / SVG / arbitrary types are refused
      "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
      "data:image/svg+xml;base64,PHN2Zy8+",
      "data:application/octet-stream;base64,AAA=",
    ])("still rejects unsafe data URL %s", (url) => {
      expect(isTrustedVirtualFileUrl(url)).toBe(false);
    });

    it("rejects data URL when no cell has been run", () => {
      store.set(hasRunAnyCellAtom, false);
      expect(
        isTrustedVirtualFileUrl(
          "data:text/javascript;base64,ZXhwb3J0IGRlZmF1bHQge30=",
        ),
      ).toBe(false);
    });
  });
});
