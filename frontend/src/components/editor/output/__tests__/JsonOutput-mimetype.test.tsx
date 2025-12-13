/* Copyright 2024 Marimo. All rights reserved. */
import { render } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { JsonOutput } from "../JsonOutput";

// Mock window.matchMedia for JsonViewer
beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

describe("JsonOutput with enhanced mimetype handling", () => {
  it("should render data with various mimetypes without crashing", () => {
    const data = {
      text: "text/plain:Hello",
      html: "text/html:<strong>Bold</strong>",
      img: "image/png:data:image/png;base64,xyz...",
      set: "text/plain+set:[1,2,3]",
      tuple: "text/plain+tuple:[10,20]",
      custom: "application/custom:data",
      number: 42,
      boolean: true,
    };

    const { container } = render(<JsonOutput data={data} format="auto" />);

    // Verify component renders without crashing
    expect(container).toBeInTheDocument();
    expect(container.querySelector(".marimo-json-output")).toBeInTheDocument();
  });
});
