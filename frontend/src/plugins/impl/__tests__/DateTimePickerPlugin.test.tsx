/* Copyright 2024 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { IPluginProps } from "../../types";
import { DateTimePickerPlugin } from "../DateTimePickerPlugin";

interface DateTimeData {
  label: string | null;
  start: string;
  stop: string;
  fullWidth: boolean;
}

describe("DateTimePickerPlugin", () => {
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
});
