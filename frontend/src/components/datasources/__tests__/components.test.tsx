/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DataType } from "@/core/kernel/messages";
import { ColumnName } from "../components";

describe("ColumnName", () => {
  it("renders the unknown icon for unrecognized data types", () => {
    const unrecognized = render(
      <ColumnName columnName="geom" dataType={"geometry" as DataType} />,
    );
    const unknown = render(<ColumnName columnName="geom" dataType="unknown" />);

    expect(unrecognized.container.innerHTML).toEqual(unknown.container.innerHTML);
  });
});
