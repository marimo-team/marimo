/* Copyright 2024 Marimo. All rights reserved. */

import { Provider as SlotzProvider } from "@marimo-team/react-slotz";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Functions } from "@/utils/functions";
import { Sidebar } from "../sidebar";
import { normalizeWidth } from "../state";

describe("Sidebar", () => {
  it("should use default width when no width is provided", () => {
    const { container } = render(
      <SlotzProvider>
        <Sidebar isOpen={false} toggle={Functions.NOOP} />
      </SlotzProvider>,
    );
    const aside = container.querySelector("aside");
    expect(aside?.style.width).toBe("68px"); // closed width when not open
  });

  it("should use provided width when width is specified", () => {
    const { container } = render(
      <SlotzProvider>
        <Sidebar isOpen={true} toggle={Functions.NOOP} width="400px" />
      </SlotzProvider>,
    );
    const aside = container.querySelector("aside");
    expect(aside?.style.width).toBe("400px"); // open width when isOpen is true
  });

  it("should convert numeric width to px", () => {
    const { container } = render(
      <SlotzProvider>
        <Sidebar isOpen={true} toggle={Functions.NOOP} width={400} />
      </SlotzProvider>,
    );
    const aside = container.querySelector("aside");
    expect(aside?.style.width).toBe("400px"); // open width when isOpen is true
  });
});

describe("normalizeWidth", () => {
  it("should return default width when no width is provided", () => {
    expect(normalizeWidth(undefined)).toBe("288px");
  });

  it("should add px to numeric values", () => {
    expect(normalizeWidth("400")).toBe("400px");
  });

  it("should not modify values with units", () => {
    expect(normalizeWidth("20rem")).toBe("20rem");
    expect(normalizeWidth("50%")).toBe("50%");
    expect(normalizeWidth("100vh")).toBe("100vh");
  });
});
