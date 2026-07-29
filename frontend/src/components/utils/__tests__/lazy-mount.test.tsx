/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { LazyActivity } from "../lazy-mount";

describe("LazyActivity", () => {
  it("preserves child state by default", () => {
    let instanceCount = 0;
    const Child = () => {
      const [instance] = useState(() => ++instanceCount);
      return <div data-testid="child">{instance}</div>;
    };

    const { rerender } = render(
      <LazyActivity mode="visible">
        <Child />
      </LazyActivity>,
    );
    expect(screen.getByTestId("child")).toHaveTextContent("1");

    rerender(
      <LazyActivity mode="hidden">
        <Child />
      </LazyActivity>,
    );
    rerender(
      <LazyActivity mode="visible">
        <Child />
      </LazyActivity>,
    );

    expect(screen.getByTestId("child")).toHaveTextContent("1");
  });

  it("creates a fresh child after hiding when unmountOnHide is true", () => {
    let instanceCount = 0;
    const Child = () => {
      const [instance] = useState(() => ++instanceCount);
      return <div data-testid="child">{instance}</div>;
    };

    const { rerender } = render(
      <LazyActivity mode="visible" unmountOnHide={true}>
        <Child />
      </LazyActivity>,
    );
    expect(screen.getByTestId("child")).toHaveTextContent("1");

    rerender(
      <LazyActivity mode="hidden" unmountOnHide={true}>
        <Child />
      </LazyActivity>,
    );
    expect(screen.queryByTestId("child")).not.toBeInTheDocument();

    rerender(
      <LazyActivity mode="visible" unmountOnHide={true}>
        <Child />
      </LazyActivity>,
    );
    expect(screen.getByTestId("child")).toHaveTextContent("2");
  });
});
