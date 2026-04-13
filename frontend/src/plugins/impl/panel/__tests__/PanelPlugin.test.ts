/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Logger } from "@/utils/Logger";
import { loadPanelExtension } from "../PanelPlugin";

describe("loadPanelExtension", () => {
  beforeEach(() => {
    for (const el of document.head.querySelectorAll("script")) {
      el.remove();
    }
  });

  afterEach(() => {
    vi.restoreAllMocks();
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
    // An attacker embedding inline JS as a data URL — what the old plugin
    // would have executed verbatim via script.innerHTML.
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
