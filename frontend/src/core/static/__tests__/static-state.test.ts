/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  getStaticModelNotifications,
  getStaticVirtualFiles,
  isStaticNotebook,
} from "../static-state";

function setMarimoStatic(value: unknown): void {
  (window as unknown as { __MARIMO_STATIC__?: unknown }).__MARIMO_STATIC__ =
    value;
}

function clearMarimoStatic(): void {
  delete (window as unknown as { __MARIMO_STATIC__?: unknown })
    .__MARIMO_STATIC__;
}

describe("static-state shape validation", () => {
  beforeEach(() => {
    clearMarimoStatic();
  });

  afterEach(() => {
    clearMarimoStatic();
  });

  it("treats an absent global as not-a-static-notebook", () => {
    expect(isStaticNotebook()).toBe(false);
    expect(getStaticModelNotifications()).toBeUndefined();
  });

  it("accepts a well-formed state", () => {
    setMarimoStatic({
      files: { "/@file/a.txt": "data:text/plain;base64,YQ==" },
      modelNotifications: [],
    });
    expect(isStaticNotebook()).toBe(true);
    expect(getStaticVirtualFiles()).toEqual({
      "/@file/a.txt": "data:text/plain;base64,YQ==",
    });
    expect(getStaticModelNotifications()).toEqual([]);
  });

  it("rejects a malformed global (missing files)", () => {
    setMarimoStatic({ modelNotifications: [] });
    expect(isStaticNotebook()).toBe(false);
    expect(getStaticModelNotifications()).toBeUndefined();
  });

  it("rejects a malformed global (non-array modelNotifications)", () => {
    setMarimoStatic({ files: {}, modelNotifications: "oops" });
    expect(isStaticNotebook()).toBe(false);
  });

  it("rejects a non-object global", () => {
    setMarimoStatic("pwned");
    expect(isStaticNotebook()).toBe(false);
  });

  it("rejects an array as the state", () => {
    setMarimoStatic([]);
    expect(isStaticNotebook()).toBe(false);
  });

  it("rejects files when it is an array", () => {
    setMarimoStatic({ files: [], modelNotifications: [] });
    expect(isStaticNotebook()).toBe(false);
  });

  it("rejects files that contain non-string values", () => {
    setMarimoStatic({
      files: { "/@file/a.txt": 42 },
      modelNotifications: [],
    });
    expect(isStaticNotebook()).toBe(false);
  });
});
