/* Copyright 2024 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import type { IPluginProps } from "../../types";
import { DateSliderPlugin } from "../DateSliderPlugin";

interface DateSliderData {
  label: string | null;
  start: number;
  stop: number;
  step: number;
  steps: string[];
  debounce: boolean;
  orientation: "horizontal" | "vertical";
  showValue: boolean;
  fullWidth: boolean;
  disabled?: boolean;
}

beforeAll(() => {
  global.ResizeObserver = class ResizeObserver {
    observe() {
      // do nothing
    }
    unobserve() {
      // do nothing
    }
    disconnect() {
      // do nothing
    }
  };
});

describe("DateSliderPlugin", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    store.set(initialModeAtom, "edit");
  });

  it("should render with daily steps", () => {
    const plugin = new DateSliderPlugin();
    const host = document.createElement("div");
    const steps = [
      "2024-01-01",
      "2024-01-02",
      "2024-01-03",
      "2024-01-04",
      "2024-01-05",
    ];
    const props: IPluginProps<string[], DateSliderData> = {
      host,
      value: ["2024-01-01", "2024-01-05"],
      setValue: (valueOrFn) => {
        if (typeof valueOrFn === "function") {
          valueOrFn(["2024-01-01", "2024-01-05"]);
        }
      },
      data: {
        label: "Select date range",
        start: 0,
        stop: 4,
        step: 1,
        steps: steps,
        debounce: false,
        orientation: "horizontal",
        showValue: true,
        fullWidth: false,
        disabled: false,
      },
      functions: {},
    };
    const { container } = render(plugin.render(props));

    // Check if the component renders successfully
    expect(container.innerHTML).not.toBe("");
    // Check for the slider component
    const slider = container.querySelector('[role="slider"]');
    expect(slider).not.toBeNull();
  });

  it("should render with weekly steps and debounce", () => {
    const plugin = new DateSliderPlugin();
    const host = document.createElement("div");
    const steps = [
      "2024-01-01",
      "2024-01-08",
      "2024-01-15",
      "2024-01-22",
      "2024-01-29",
    ];
    const props: IPluginProps<string[], DateSliderData> = {
      host,
      value: ["2024-01-08", "2024-01-22"],
      setValue: (valueOrFn) => {
        if (typeof valueOrFn === "function") {
          valueOrFn(["2024-01-08", "2024-01-22"]);
        }
      },
      data: {
        label: null,
        start: 0,
        stop: 4,
        step: 1,
        steps: steps,
        debounce: true,
        orientation: "horizontal",
        showValue: false,
        fullWidth: true,
        disabled: false,
      },
      functions: {},
    };
    const { container } = render(plugin.render(props));

    // Check if the component renders successfully
    expect(container.innerHTML).not.toBe("");
    const slider = container.querySelector('[role="slider"]');
    expect(slider).not.toBeNull();
  });

  it("should render with vertical orientation", () => {
    const plugin = new DateSliderPlugin();
    const host = document.createElement("div");
    const steps = ["2024-01-01", "2024-02-01", "2024-03-01"];
    const props: IPluginProps<string[], DateSliderData> = {
      host,
      value: ["2024-01-01", "2024-03-01"],
      setValue: (valueOrFn) => {
        if (typeof valueOrFn === "function") {
          valueOrFn(["2024-01-01", "2024-03-01"]);
        }
      },
      data: {
        label: "Monthly dates",
        start: 0,
        stop: 2,
        step: 1,
        steps: steps,
        debounce: false,
        orientation: "vertical",
        showValue: true,
        fullWidth: false,
        disabled: false,
      },
      functions: {},
    };
    const { container } = render(plugin.render(props));

    // Check if the component renders successfully
    expect(container.innerHTML).not.toBe("");
    const slider = container.querySelector('[role="slider"]');
    expect(slider).not.toBeNull();
  });

  it("should handle edge case with large date range", () => {
    // Test with a large number of steps (daily over a year)
    const plugin = new DateSliderPlugin();
    const host = document.createElement("div");
    const steps = Array.from({ length: 365 }, (_, i) => {
      const date = new Date(2024, 0, 1);
      date.setDate(date.getDate() + i);
      return date.toISOString().split("T")[0];
    });
    const props: IPluginProps<string[], DateSliderData> = {
      host,
      value: [steps[0], steps[steps.length - 1]],
      setValue: (valueOrFn) => {
        if (typeof valueOrFn === "function") {
          valueOrFn([steps[0], steps[steps.length - 1]]);
        }
      },
      data: {
        label: null,
        start: 0,
        stop: steps.length - 1,
        step: 1,
        steps: steps,
        debounce: false,
        orientation: "horizontal",
        showValue: false,
        fullWidth: false,
        disabled: false,
      },
      functions: {},
    };

    // This should not throw an error
    const { container } = render(plugin.render(props));

    // Check if the component renders successfully
    expect(container.innerHTML).not.toBe("");
    const slider = container.querySelector('[role="slider"]');
    expect(slider).not.toBeNull();
  });

  it("should handle disabled state", () => {
    const plugin = new DateSliderPlugin();
    const host = document.createElement("div");
    const steps = ["2024-01-01", "2024-01-02"];
    const props: IPluginProps<string[], DateSliderData> = {
      host,
      value: ["2024-01-01", "2024-01-02"],
      setValue: (valueOrFn) => {
        if (typeof valueOrFn === "function") {
          valueOrFn(["2024-01-01", "2024-01-02"]);
        }
      },
      data: {
        label: null,
        start: 0,
        stop: 1,
        step: 1,
        steps: steps,
        debounce: false,
        orientation: "horizontal",
        showValue: false,
        fullWidth: false,
        disabled: true,
      },
      functions: {},
    };
    const { container } = render(plugin.render(props));

    // Check if the component renders successfully
    expect(container.innerHTML).not.toBe("");
    const slider = container.querySelector('[role="slider"]');
    expect(slider).not.toBeNull();
  });
});
