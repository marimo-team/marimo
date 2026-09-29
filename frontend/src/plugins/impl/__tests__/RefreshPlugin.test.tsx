/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { z } from "zod";
import type { IPluginProps } from "../../types";
import { RefreshPlugin } from "../RefreshPlugin";

type RefreshProps = IPluginProps<
  string | number | undefined,
  z.infer<typeof RefreshPlugin.prototype.validator>
>;

function createProps(defaultInterval: number): RefreshProps {
  return {
    host: document.createElement("div"),
    value: undefined,
    setValue: vi.fn(),
    data: {
      options: [1, 2, 3],
      defaultInterval,
      label: "Refresh interval",
    },
    functions: {},
  };
}

describe("RefreshPlugin", () => {
  it("resets the selection when the default interval changes", () => {
    const plugin = new RefreshPlugin();
    const props = createProps(1);
    const { getByTestId, rerender } = render(plugin.render(props));
    const select = getByTestId("marimo-plugin-refresh-select");

    fireEvent.change(select, { target: { value: "2" } });
    expect(select).toHaveValue("2");

    rerender(
      plugin.render({
        ...props,
        data: { ...props.data, defaultInterval: 3 },
      }),
    );

    expect(getByTestId("marimo-plugin-refresh-select")).toHaveValue("3");
  });
});
