/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { DataType } from "@/core/kernel/messages";
import { Logger } from "@/utils/Logger";
import { ColumnName } from "../components";

describe("ColumnName", () => {
  it("renders the unknown icon for unrecognized data types", () => {
    const warn = vi.spyOn(Logger, "warn").mockImplementation(() => {});

    try {
      const unrecognized = render(
        <ColumnName columnName="geom" dataType={"bogus_type" as DataType} />,
      );
      const unknown = render(
        <ColumnName columnName="geom" dataType="unknown" />,
      );

      expect(unrecognized.container.innerHTML).toEqual(
        unknown.container.innerHTML,
      );
      expect(warn).not.toHaveBeenCalled();
    } finally {
      warn.mockRestore();
    }
  });

  it("renders geometry with a distinct icon", () => {
    const geometry = render(
      <ColumnName columnName="geom" dataType="geometry" />,
    );
    const unknown = render(<ColumnName columnName="geom" dataType="unknown" />);

    expect(geometry.container.querySelector(".lucide-map-pin")).not.toBeNull();
    expect(unknown.container.querySelector(".lucide-braces")).not.toBeNull();
    expect(geometry.container.innerHTML).not.toEqual(
      unknown.container.innerHTML,
    );
  });
});
