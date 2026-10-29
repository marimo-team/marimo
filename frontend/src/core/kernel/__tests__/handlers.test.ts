/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { createCell } from "@/core/cells/types";
import { buildLayoutState } from "../handlers";
import type { NotificationMessageData } from "../messages";
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

describe("buildLayoutState", () => {
  it("should build default layout state when no layout is provided", () => {
    const kernelReadyData: NotificationMessageData<"kernel-ready"> = {
      layout: null,
      resumed: false,
      ui_values: {},
      last_executed_code: {},
      last_execution_time: {},
      app_config: {
        width: "normal",
        app_title: null,
        layout_file: null,
        css_file: null,
        auto_download: [],
      },
      kiosk: false,
      capabilities: {
        terminal: false,
      },
      auto_instantiated: false,
      consumer_capabilities: { edit: true, interact: true },
    };

    const cells = [createCell({ id: cellId("cell1") })];
    const mockSetLayoutData = vi.fn();
    const layoutState = buildLayoutState(
      kernelReadyData,
      cells,
      mockSetLayoutData,
    );

    expect(layoutState).toMatchInlineSnapshot(`
      {
        "layoutData": {},
        "selectedLayout": "vertical",
      }
    `);
    expect(mockSetLayoutData).not.toHaveBeenCalled();
  });

  it("should build layout state with vertical layout", () => {
    const kernelReadyData: NotificationMessageData<"kernel-ready"> = {
      layout: {
        type: "vertical",
        data: [],
      },
      resumed: false,
      ui_values: {},
      last_executed_code: {},
      last_execution_time: {},
      app_config: {
        width: "normal",
        app_title: null,
        layout_file: null,
        css_file: null,
        auto_download: [],
      },
      kiosk: false,
      capabilities: {
        terminal: false,
      },
      auto_instantiated: false,
      consumer_capabilities: { edit: true, interact: true },
    };

    const cells = [
      createCell({ id: cellId("cell1") }),
      createCell({ id: cellId("cell2") }),
    ];
    const mockSetLayoutData = vi.fn();
    const layoutState = buildLayoutState(
      kernelReadyData,
      cells,
      mockSetLayoutData,
    );

    expect(layoutState.selectedLayout).toBe("vertical");
    expect(mockSetLayoutData).toHaveBeenCalledWith({
      layoutView: "vertical",
      data: expect.any(Array),
    });
  });
});
