/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, screen } from "@testing-library/react";
import { useForm, useWatch } from "react-hook-form";
import { describe, expect, test } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { Form } from "@/components/ui/form";
import { SliderField } from "../components/form-fields";

SetupMocks.resizeObserver();
function Harness({ label = "Opacity" }: { label?: string }) {
  const form = useForm({ defaultValues: { xAxis: { width: 400 } } });
  const value = useWatch({ control: form.control, name: "xAxis.width" });
  return (
    <Form {...form}>
      <SliderField
        fieldName="xAxis.width"
        label={label}
        defaultValue={400}
        start={200}
        stop={800}
        step={10}
      />
      <output aria-label="Current opacity">{value}</output>
    </Form>
  );
}

describe("SliderField", () => {
  test("names the chart-form thumb and preserves keyboard value updates", () => {
    const { rerender } = render(<Harness />);
    fireEvent.keyDown(screen.getByRole("slider", { name: "Opacity" }), {
      key: "ArrowRight",
    });
    expect(screen.getByLabelText("Current opacity")).toHaveTextContent("410");
    rerender(<Harness label="Updated opacity" />);
    expect(
      screen.getByRole("slider", { name: "Updated opacity" }),
    ).toHaveAttribute("aria-valuenow", "410");
  });

  test("independently associates repeated chart form instances", () => {
    render(
      <>
        <Harness />
        <Harness />
      </>,
    );
    const thumbs = screen.getAllByRole("slider", { name: "Opacity" });
    expect(thumbs).toHaveLength(2);
    expect(thumbs[0].getAttribute("aria-labelledby")).not.toBe(
      thumbs[1].getAttribute("aria-labelledby"),
    );
  });
});
