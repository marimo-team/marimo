/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/unbound-method */
import { describe, expect, it, vi } from "vitest";
import { queryParamHandlers } from "../queryParamHandlers";

// Helper to set up URL and searchParams
function setupURL(search = "") {
  const url = new URL("http://localhost:3000");
  url.search = search;
  window.history.pushState({}, "", `${url.pathname}${url.search}`);
  return url;
}

vi.spyOn(window.history, "pushState");

describe("queryParamHandlers", () => {
  it("should append a query parameter", () => {
    setupURL();
    queryParamHandlers.append({ key: "test", value: "123" });
    expect(window.location.href).toContain("test=123");
    expect(window.history.pushState).toHaveBeenCalled();
  });

  it("should set a query parameter", () => {
    setupURL();
    queryParamHandlers.set({ key: "test", value: "123" });
    expect(window.location.href).toContain("test=123");
    expect(window.history.pushState).toHaveBeenCalled();
  });

  it("should delete a specific query parameter", () => {
    setupURL("?test=123&sample=456");
    queryParamHandlers.delete({ key: "test", value: "123" });
    expect(window.location.href).not.toContain("test=123");
    expect(window.location.href).toContain("sample=456");
    expect(window.history.pushState).toHaveBeenCalled();
  });

  it("shouldn't delete a specific query parameter if the value doesn't match", () => {
    setupURL("?test=abc&sample=456");
    queryParamHandlers.delete({ key: "test", value: "123" });
    expect(window.location.href).toContain("test=abc");
    expect(window.location.href).toContain("sample=456");
    expect(window.history.pushState).toHaveBeenCalled();
  });

  it("should delete all instances of a query parameter", () => {
    setupURL("?test=123&test=456");
    queryParamHandlers.delete({ key: "test", value: null });
    expect(window.location.href).not.toContain("test=123");
    expect(window.location.href).not.toContain("test=456");
    expect(window.history.pushState).toHaveBeenCalled();
  });

  it("should clear all query parameters", () => {
    setupURL("?test=123&sample=456");
    queryParamHandlers.clear();
    expect(window.location.href).not.toContain("test=123");
    expect(window.location.href).not.toContain("sample=456");
    expect(window.history.pushState).toHaveBeenCalled();
  });
});
