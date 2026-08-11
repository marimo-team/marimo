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
        <ColumnName columnName="geom" dataType={"geometry" as DataType} />,
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
});
