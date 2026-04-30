/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { Logger } from "@/utils/Logger";
import { buildCellData, buildLayoutState } from "../handlers";
import type { NotificationMessageData } from "../messages";
import { queryParamHandlers } from "../queryParamHandlers";

type KernelReadyMessage = NotificationMessageData<"kernel-ready">;

// Builds a minimal kernel-ready message with a one-cell notebook so the
// layout-state tests can focus on the `layout` field.
function makeKernelReady(
  layout: KernelReadyMessage["layout"],
): KernelReadyMessage {
  return {
    cell_ids: [cellId("cell1")],
    codes: ["x = 1"],
    names: ["__"],
    configs: [{ disabled: false, hide_code: false }],
    layout,
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
  };
}

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

describe("buildCellData", () => {
  it("should build cell data from kernel-ready data", () => {
    const kernelReadyData: NotificationMessageData<"kernel-ready"> = {
      cell_ids: [cellId("cell1"), cellId("cell2")],
      codes: ["x = 1", "y = 2"],
      names: ["__", "__"],
      configs: [
        { disabled: false, hide_code: false },
        { disabled: false, hide_code: false },
      ],
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
    };

    const cells = buildCellData(kernelReadyData);

    expect(cells).toMatchInlineSnapshot(`
      [
        {
          "code": "x = 1",
          "config": {
            "disabled": false,
            "hide_code": false,
          },
          "edited": false,
          "id": "cell1",
          "lastCodeRun": null,
          "lastExecutionTime": null,
          "name": "__",
          "serializedEditorState": null,
        },
        {
          "code": "y = 2",
          "config": {
            "disabled": false,
            "hide_code": false,
          },
          "edited": false,
          "id": "cell2",
          "lastCodeRun": null,
          "lastExecutionTime": null,
          "name": "__",
          "serializedEditorState": null,
        },
      ]
    `);
  });

  it("should mark cells as edited when code differs from last executed code", () => {
    const kernelReadyData: NotificationMessageData<"kernel-ready"> = {
      cell_ids: [cellId("cell1"), cellId("cell2")],
      codes: ["x = 1", "y = 3"],
      names: ["__", "__"],
      configs: [
        { disabled: false, hide_code: false },
        { disabled: false, hide_code: false },
      ],
      layout: null,
      resumed: false,
      ui_values: {},
      last_executed_code: {
        cell1: "x = 1",
        cell2: "y = 2",
      },
      last_execution_time: {
        cell1: 1_234_567_890,
        cell2: 1_234_567_891,
      },
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
    };

    const cells = buildCellData(kernelReadyData);

    expect(cells[0].edited).toBe(false);
    expect(cells[1].edited).toBe(true);
    expect(cells[0].lastCodeRun).toBe("x = 1");
    expect(cells[1].lastCodeRun).toBe("y = 2");
  });

  it("should handle empty cell data", () => {
    const kernelReadyData: NotificationMessageData<"kernel-ready"> = {
      cell_ids: [],
      codes: [],
      names: [],
      configs: [],
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
    };

    const cells = buildCellData(kernelReadyData);

    expect(cells).toMatchInlineSnapshot("[]");
  });
});

describe("buildLayoutState", () => {
  it("should build default layout state when no layout is provided", () => {
    const kernelReadyData: NotificationMessageData<"kernel-ready"> = {
      cell_ids: [cellId("cell1")],
      codes: ["x = 1"],
      names: ["__"],
      configs: [{ disabled: false, hide_code: false }],
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
    };

    const cells = buildCellData(kernelReadyData);
    const mockSetLayoutData = vi.fn();
    const layoutState = buildLayoutState({
      data: kernelReadyData,
      cells,
      setLayoutData: mockSetLayoutData,
    });

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
      cell_ids: [cellId("cell1"), cellId("cell2")],
      codes: ["x = 1", "y = 2"],
      names: ["__", "__"],
      configs: [
        { disabled: false, hide_code: false },
        { disabled: false, hide_code: false },
      ],
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
    };

    const cells = buildCellData(kernelReadyData);
    const mockSetLayoutData = vi.fn();
    const layoutState = buildLayoutState({
      data: kernelReadyData,
      cells,
      setLayoutData: mockSetLayoutData,
    });

    expect(layoutState.selectedLayout).toBe("vertical");
    expect(mockSetLayoutData).toHaveBeenCalledWith({
      layoutView: "vertical",
      data: null,
    });
  });

  it("should build layout state with grid layout", () => {
    const kernelReadyData = makeKernelReady({
      type: "grid",
      data: {
        columns: 12,
        rowHeight: 20,
        cells: [{ position: [0, 0, 4, 3] }],
      },
    });

    const cells = buildCellData(kernelReadyData);
    const mockSetLayoutData = vi.fn();
    const layoutState = buildLayoutState({
      data: kernelReadyData,
      cells,
      setLayoutData: mockSetLayoutData,
    });

    expect(layoutState.selectedLayout).toBe("grid");
    expect(layoutState.layoutData.grid).toBeDefined();
    expect(layoutState.layoutData.grid?.cells).toEqual([
      { i: "cell1", x: 0, y: 0, w: 4, h: 3 },
    ]);
    expect(mockSetLayoutData).toHaveBeenCalledTimes(1);
    expect(mockSetLayoutData).toHaveBeenCalledWith({
      layoutView: "grid",
      data: layoutState.layoutData.grid,
    });
  });

  it("should build layout state with slides layout", () => {
    const kernelReadyData = makeKernelReady({
      type: "slides",
      data: {
        cells: [{ type: "slide" }],
        deck: { transition: "fade" },
      },
    });

    const cells = buildCellData(kernelReadyData);
    const mockSetLayoutData = vi.fn();
    const layoutState = buildLayoutState({
      data: kernelReadyData,
      cells,
      setLayoutData: mockSetLayoutData,
    });

    expect(layoutState.selectedLayout).toBe("slides");
    expect(layoutState.layoutData.slides?.deck).toEqual({ transition: "fade" });
    expect(layoutState.layoutData.slides?.cells.get(cellId("cell1"))).toEqual({
      type: "slide",
    });
    expect(mockSetLayoutData).toHaveBeenCalledTimes(1);
    expect(mockSetLayoutData).toHaveBeenCalledWith({
      layoutView: "slides",
      data: layoutState.layoutData.slides,
    });
  });

  it("should ignore unknown layout types and warn", () => {
    const warnSpy = vi.spyOn(Logger, "warn").mockImplementation(() => {});
    const kernelReadyData = makeKernelReady({
      // oxlint-disable-next-line typescript/no-explicit-any
      type: "totally-bogus" as any,
      data: {},
    });

    const cells = buildCellData(kernelReadyData);
    const mockSetLayoutData = vi.fn();
    const layoutState = buildLayoutState({
      data: kernelReadyData,
      cells,
      setLayoutData: mockSetLayoutData,
    });

    expect(layoutState.selectedLayout).toBe("vertical");
    expect(layoutState.layoutData).toEqual({});
    expect(mockSetLayoutData).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('unknown layout type "totally-bogus"'),
    );
    warnSpy.mockRestore();
  });
});
