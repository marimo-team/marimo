/* Copyright 2024 Marimo. All rights reserved. */
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, vi, expect, beforeAll } from "vitest";
import { DropdownPlugin } from "../DropdownPlugin";
import type { IPluginProps } from "../../types";

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
  global.HTMLDivElement.prototype.scrollIntoView = () => {
    // do nothing
  };
});

describe("DropdownPlugin", () => {
  describe("searchable dropdown", () => {
    it("renders SearchableSelect when searchable is true", () => {
      const plugin = new DropdownPlugin();
      const host = document.createElement("div");
      const props: IPluginProps<
        string[],
        (typeof plugin)["validator"]["_type"]
      > = {
        data: {
          label: "Test Label",
          options: ["Option 1", "Option 2"],
          allowSelectNone: false,
          fullWidth: false,
          searchable: true,
          initialValue: [],
        },
        value: [],
        setValue: vi.fn(),
        host,
        functions: {},
      };
      render(plugin.render(props));
      expect(
        screen.getByTestId("marimo-plugin-searchable-dropdown"),
      ).toBeInTheDocument();
    });

    it("renders default dropdown when searchable is false", () => {
      const plugin = new DropdownPlugin();
      const host = document.createElement("div");
      const props: IPluginProps<
        string[],
        (typeof plugin)["validator"]["_type"]
      > = {
        data: {
          label: "Test Label",
          options: ["Option 1", "Option 2"],
          allowSelectNone: false,
          fullWidth: false,
          searchable: false,
          initialValue: [],
        },
        value: [],
        setValue: vi.fn(),
        host,
        functions: {},
      };
      render(plugin.render(props));
      expect(screen.getByTestId("marimo-plugin-dropdown")).toBeInTheDocument();
    });

    it("filters options based on search input and handles selection", async () => {
      const plugin = new DropdownPlugin();
      const host = document.createElement("div");
      const setValue = vi.fn();
      const props: IPluginProps<
        string[],
        (typeof plugin)["validator"]["_type"]
      > = {
        data: {
          label: "Test Label",
          options: ["Apple", "Banana", "Orange"],
          allowSelectNone: true,
          fullWidth: false,
          searchable: true,
          initialValue: [],
        },
        value: [],
        setValue,
        host,
        functions: {},
      };
      render(plugin.render(props));

      // Open dropdown
      fireEvent.click(
        screen.getByTestId("marimo-plugin-searchable-dropdown").firstChild!,
      );

      // Initial empty state
      const input = screen.getByRole("combobox");
      expect(input).toHaveValue("");

      // Search functionality
      fireEvent.change(input, { target: { value: "app" } });
      expect(screen.getByText("Apple")).toBeInTheDocument();
      expect(screen.queryByText("Banana")).not.toBeInTheDocument();

      // Selection after search
      fireEvent.click(screen.getByText("Apple"));
      expect(setValue).toHaveBeenCalledWith(["Apple"]);
    });

    it("supports single selection only", async () => {
      const plugin = new DropdownPlugin();
      const host = document.createElement("div");
      const setValue = vi.fn();
      const props: IPluginProps<
        string[],
        (typeof plugin)["validator"]["_type"]
      > = {
        data: {
          label: "Test Label",
          options: ["Apple", "Banana", "Orange"],
          allowSelectNone: true,
          fullWidth: false,
          searchable: true,
          initialValue: [],
        },
        value: ["Apple"],
        setValue,
        host,
        functions: {},
      };
      const { rerender } = render(plugin.render(props));

      // Initial value should be displayed
      expect(
        screen.getByTestId("marimo-plugin-searchable-dropdown").firstChild
          ?.textContent,
      ).toContain("Apple");

      // Open dropdown
      fireEvent.click(
        screen.getByTestId("marimo-plugin-searchable-dropdown").firstChild!,
      );

      // Select second option - should replace first
      fireEvent.click(screen.getByText("Banana"));
      expect(setValue).toHaveBeenCalledWith(["Banana"]);

      // Re-render
      rerender(
        plugin.render({
          ...props,
          value: ["Banana"],
        }),
      );
      expect(
        screen.getByTestId("marimo-plugin-searchable-dropdown").firstChild
          ?.textContent,
      ).toContain("Banana");

      // Open dropdown
      fireEvent.click(
        screen.getByTestId("marimo-plugin-searchable-dropdown").firstChild!,
      );

      // Select none should clear value
      fireEvent.click(screen.getByText("--"));
      expect(setValue).toHaveBeenCalledWith([]);
    });
  });
});
