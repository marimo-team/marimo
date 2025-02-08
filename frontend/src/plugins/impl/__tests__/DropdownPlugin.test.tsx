import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, vi, expect } from "vitest";
import { DropdownPlugin } from "../DropdownPlugin";
import type { IPluginProps } from "../../types";
import "../../../setupTests";

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

    it("filters options based on search input", async () => {
      const plugin = new DropdownPlugin();
      const host = document.createElement("div");
      const props: IPluginProps<
        string[],
        (typeof plugin)["validator"]["_type"]
      > = {
        data: {
          label: "Test Label",
          options: ["Apple", "Banana", "Orange"],
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

      const input = screen.getByRole("combobox");
      fireEvent.change(input, { target: { value: "app" } });

      expect(screen.getByText("Apple")).toBeInTheDocument();
      expect(screen.queryByText("Banana")).not.toBeInTheDocument();
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
          allowSelectNone: false,
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

      const input = screen.getByRole("combobox");
      fireEvent.change(input, { target: { value: "" } });

      // Select first option
      fireEvent.click(screen.getByText("Apple"));
      expect(setValue).toHaveBeenCalledWith(["Apple"]);

      // Select second option - should replace first
      fireEvent.click(screen.getByText("Banana"));
      expect(setValue).toHaveBeenCalledWith(["Banana"]);
    });
  });
});
