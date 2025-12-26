/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import type { IPluginProps } from "../../types";
import { DateTimePickerPlugin } from "../DateTimePickerPlugin";

interface DateTimeData {
  label: string | null;
  start: string;
  stop: string;
  precision: "hour" | "minute" | "second";
  fullWidth: boolean;
}

describe("DateTimePickerPlugin", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    store.set(initialModeAtom, "edit");
  });

  it("should render when initial value is not provided", () => {
    const plugin = new DateTimePickerPlugin();
    // Create a host element as required by IPluginProps
    const host = document.createElement("div");
    const props: IPluginProps<string, DateTimeData> = {
      host,
      value: "", // Empty string instead of undefined since type T = string
      setValue: (valueOrFn) => {
        // No-op function to satisfy lint requirements
        if (typeof valueOrFn === "function") {
          valueOrFn("");
        }
      },
      data: {
        label: null,
        start: "2024-01-01T00:00:00",
        stop: "2024-12-31T23:59:59",
        precision: "minute",
        fullWidth: false,
      },
      functions: {},
    };
    const { container } = render(plugin.render(props));

    // Check if the component renders at all
    expect(container.innerHTML).not.toBe("");
    // Check for the date picker group
    const datePicker = container.querySelector('[class*="group"]');
    expect(datePicker).not.toBeNull();
  });

  it("should render with datetime.min and datetime.max edge cases", () => {
    // Regression test for issue #6700
    // Ensure the component can handle edge case dates like datetime.min
    const plugin = new DateTimePickerPlugin();
    const host = document.createElement("div");
    const props: IPluginProps<string, DateTimeData> = {
      host,
      value: "2024-01-01T12:00:00",
      setValue: (valueOrFn) => {
        if (typeof valueOrFn === "function") {
          valueOrFn("2024-01-01T12:00:00");
        }
      },
      data: {
        label: null,
        // These are the exact values that datetime.min and datetime.max produce
        start: "0001-01-01T00:00:00",
        stop: "9999-12-31T23:59:59",
        precision: "minute",
        fullWidth: false,
      },
      functions: {},
    };

    // This should not throw an error
    const { container } = render(plugin.render(props));

    // Check if the component renders successfully
    expect(container.innerHTML).not.toBe("");
    const datePicker = container.querySelector('[class*="group"]');
    expect(datePicker).not.toBeNull();
  });
});
