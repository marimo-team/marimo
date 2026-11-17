/* Copyright 2026 Marimo. All rights reserved. */
import { createEvent, fireEvent, render } from "@testing-library/react";
import { Database } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { Select, SelectTrigger } from "../select";

describe("SelectTrigger", () => {
  it("renders its children without a chevron when hideChevron is true", () => {
    const { getByRole } = render(
      <Select>
        <SelectTrigger aria-label="Data explorer" hideChevron={true}>
          <Database aria-hidden="true" data-testid="trigger-icon" />
          Data explorer
        </SelectTrigger>
      </Select>,
    );

    const trigger = getByRole("combobox", { name: "Data explorer" });
    expect(trigger).toBeEnabled();
    expect(
      trigger.querySelector('[data-testid="trigger-icon"]'),
    ).toBeInTheDocument();
    expect(trigger.querySelectorAll("svg")).toHaveLength(1);
    expect(trigger).not.toHaveTextContent("▼");
  });

  it("shows the default chevron and updates when hideChevron changes", () => {
    const { getByRole, rerender } = render(
      <Select>
        <SelectTrigger aria-label="Data explorer">Data explorer</SelectTrigger>
      </Select>,
    );
    const trigger = getByRole("combobox", { name: "Data explorer" });
    expect(trigger.querySelectorAll("svg")).toHaveLength(1);

    rerender(
      <Select>
        <SelectTrigger aria-label="Data explorer" hideChevron={true}>
          Data explorer
        </SelectTrigger>
      </Select>,
    );
    expect(trigger.querySelectorAll("svg")).toHaveLength(0);
  });

  it.each([false, true])(
    "clears on pointer down without opening when hideChevron is %s",
    (hideChevron) => {
      const onClear = vi.fn();
      const onOpenChange = vi.fn();
      const { getByRole } = render(
        <Select onOpenChange={onOpenChange}>
          <SelectTrigger
            aria-label="Data explorer"
            hideChevron={hideChevron}
            onClear={onClear}
          >
            Data explorer
          </SelectTrigger>
        </Select>,
      );
      const trigger = getByRole("combobox", { name: "Data explorer" });
      const icon = trigger.querySelector("svg");
      expect(icon).not.toBeNull();
      if (!icon) {
        throw new Error("Expected clear icon");
      }
      const event = createEvent.pointerDown(icon, {
        bubbles: true,
        cancelable: true,
      });
      fireEvent(icon, event);

      expect(event.defaultPrevented).toBe(true);
      expect(onClear).toHaveBeenCalledOnce();
      expect(onOpenChange).not.toHaveBeenCalled();
      expect(trigger).toHaveAttribute("aria-expanded", "false");
    },
  );
});
