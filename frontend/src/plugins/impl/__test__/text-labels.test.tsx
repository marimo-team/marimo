/* Copyright 2026 Marimo. All rights reserved. */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import type { IPlugin } from "../../types";
import { TextInputPlugin } from "../TextInputPlugin";
import { TextAreaPlugin } from "../TextAreaPlugin";

function testLabelBehavior<D extends { label: string | null }>(
  plugin: IPlugin<string, D>,
) {
  for (const debounce of [false, true, 200]) {
    test(`${plugin.tagName} associates formatted label with debounce=${debounce}`, () => {
      const setValue = vi.fn();
      const props = {
        host: document.createElement("div"),
        value: "",
        setValue,
        functions: {},
        data: plugin.validator.parse({
          initialValue: "",
          placeholder: "",
          label: "<strong>Notes &amp; details</strong>",
          debounce,
        }),
      };
      const { rerender } = render(plugin.render(props));
      const control = screen.getByLabelText("Notes & details");
      expect(control).toHaveAccessibleName("Notes & details");
      const id = control.id;
      rerender(
        plugin.render({
          ...props,
          data: { ...props.data, label: "Updated notes" },
        }),
      );
      expect(screen.getByLabelText("Updated notes").id).toBe(id);
      rerender(
        plugin.render({ ...props, data: { ...props.data, label: null } }),
      );
      expect(control).toHaveAccessibleName("");
    });
    test(`${plugin.tagName} preserves commit timing with debounce=${debounce}`, () => {
      vi.useFakeTimers();
      try {
        const setValue = vi.fn();
        const props = {
          host: document.createElement("div"),
          value: "",
          setValue,
          functions: {},
          data: plugin.validator.parse({
            initialValue: "",
            placeholder: "",
            label: "Notes",
            debounce,
          }),
        };
        render(plugin.render(props));
        const control = screen.getByLabelText("Notes");
        if (debounce === false) {
          fireEvent.input(control, { target: { value: "hello" } });
        } else {
          fireEvent.change(control, { target: { value: "hello" } });
        }
        const immediateCalls = debounce === false ? 1 : 0;
        expect(setValue).toHaveBeenCalledTimes(immediateCalls);
        act(() => vi.advanceTimersByTime(199));
        expect(setValue).toHaveBeenCalledTimes(immediateCalls);
        if (debounce === true) {
          fireEvent.blur(control);
        } else if (typeof debounce === "number") {
          act(() => vi.advanceTimersByTime(1));
        }
        expect(setValue).toHaveBeenCalledWith("hello");
      } finally {
        vi.useRealTimers();
      }
    });
  }
}

for (const kind of ["text", "password", "email", "url"] as const) {
  test(`native association preserves ${kind} input attributes`, () => {
    const plugin = new TextInputPlugin();
    render(
      plugin.render({
        host: document.createElement("div"),
        value: "",
        setValue: vi.fn(),
        functions: {},
        data: plugin.validator.parse({
          initialValue: "",
          placeholder: "",
          label: "Account",
          kind,
          disabled: true,
          minLength: 2,
          maxLength: 30,
        }),
      }),
    );
    const control = screen.getByLabelText("Account");
    expect(control).toHaveAttribute("type", kind);
    expect(control).toBeDisabled();
    expect(control).toBeRequired();
    expect(control).toHaveAttribute("minlength", "2");
    expect(control).toHaveAttribute("maxlength", "30");
  });
}

function testMultipleInstances<D>(plugin: IPlugin<string, D>) {
  test(`${plugin.tagName} keeps repeated labels independently associated`, () => {
    const props = {
      host: document.createElement("div"),
      value: "",
      setValue: vi.fn(),
      functions: {},
      data: plugin.validator.parse({
        initialValue: "",
        placeholder: "",
        label: "Notes",
      }),
    };
    render(
      <>
        {plugin.render(props)}
        {plugin.render(props)}
      </>,
    );
    const controls = screen.getAllByLabelText("Notes");
    expect(controls).toHaveLength(2);
    expect(controls[0].id).not.toBe(controls[1].id);
    expect(controls[0]).toHaveAccessibleName("Notes");
    expect(controls[1]).toHaveAccessibleName("Notes");
  });
}

testLabelBehavior(new TextInputPlugin());
testLabelBehavior(new TextAreaPlugin());
testMultipleInstances(new TextInputPlugin());
testMultipleInstances(new TextAreaPlugin());
