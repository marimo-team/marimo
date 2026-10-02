/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { DatePickerPlugin } from "../DatePickerPlugin";
import { DateRangePickerPlugin } from "../DateRangePlugin";
import { DateTimePickerPlugin } from "../DateTimePickerPlugin";

const sharedProps = () => ({
  host: document.createElement("div"),
  setValue: vi.fn(),
  functions: {},
});

const widgets = [
  {
    name: "date",
    role: "group",
    fallback: "date picker",
    render: (label: string | null) =>
      new DatePickerPlugin().render({
        ...sharedProps(),
        value: "2026-10-02",
        data: {
          label,
          start: "2026-01-01",
          stop: "2026-12-31",
          fullWidth: false,
        },
      }),
  },
  {
    name: "datetime",
    role: "group",
    fallback: "date time picker",
    render: (label: string | null) =>
      new DateTimePickerPlugin().render({
        ...sharedProps(),
        value: "2026-10-02T12:00:00",
        data: {
          label,
          start: "2026-01-01T00:00:00",
          stop: "2026-12-31T23:59:59",
          precision: "minute",
          fullWidth: false,
        },
      }),
  },
  {
    name: "date range",
    role: "group",
    fallback: "date range picker",
    render: (label: string | null) =>
      new DateRangePickerPlugin().render({
        ...sharedProps(),
        value: ["2026-10-02", "2026-10-03"],
        data: {
          label,
          start: "2026-01-01",
          stop: "2026-12-31",
          fullWidth: false,
        },
      }),
  },
];

beforeEach(() => store.set(initialModeAtom, "edit"));

describe.each(widgets)("$name accessible labels", (widget) => {
  it("uses rendered formatting and decoded entities, and follows label updates", () => {
    const { getByRole, rerender } = render(
      widget.render("<span>Visit <strong>date</strong> &amp; time</span>"),
    );
    expect(getByRole(widget.role, { name: "Visit date & time" })).toBeTruthy();
    rerender(widget.render("<span>Updated <em>label</em></span>"));
    expect(getByRole(widget.role, { name: "Updated label" })).toBeTruthy();
    rerender(widget.render(null));
    expect(getByRole(widget.role, { name: widget.fallback })).toBeTruthy();
  });

  it.each([null, ""])("uses the fallback when label is %s", (label) => {
    const { getByRole } = render(widget.render(label));
    expect(getByRole(widget.role, { name: widget.fallback })).toBeTruthy();
  });

  it("keeps labels distinct for multiple widgets", () => {
    const { getByRole } = render(
      <>
        {widget.render("First")}
        {widget.render("Second")}
      </>,
    );
    expect(getByRole(widget.role, { name: "First" })).not.toBe(
      getByRole(widget.role, { name: "Second" }),
    );
  });
});
