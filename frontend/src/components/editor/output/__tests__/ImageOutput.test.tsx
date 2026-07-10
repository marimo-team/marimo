/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ImageOutput } from "../ImageOutput";

const src = "data:image/png;base64,iVBORw0KGgo=";

describe("ImageOutput", () => {
  it("renders numeric dimensions as HTML attributes", () => {
    // Attributes (not inline styles) let stylesheet rules like
    // `max-width: 100%; height: auto` shrink the image proportionally,
    // preserving its aspect ratio in width-constrained containers.
    const { container } = render(
      <ImageOutput src={src} width={640} height={480} />,
    );
    const img = container.querySelector("img");
    expect(img).toHaveAttribute("width", "640");
    expect(img).toHaveAttribute("height", "480");
    expect(img?.style.width).toBe("");
    expect(img?.style.height).toBe("");
  });

  it("renders string dimensions as inline styles", () => {
    const { container } = render(
      <ImageOutput src={src} width="50%" height="100%" />,
    );
    const img = container.querySelector("img");
    expect(img).not.toHaveAttribute("width");
    expect(img).not.toHaveAttribute("height");
    expect(img?.style.width).toBe("50%");
    expect(img?.style.height).toBe("100%");
  });

  it("supports mixed numeric and string dimensions", () => {
    const { container } = render(
      <ImageOutput src={src} width={640} height="100%" />,
    );
    const img = container.querySelector("img");
    expect(img).toHaveAttribute("width", "640");
    expect(img).not.toHaveAttribute("height");
    expect(img?.style.height).toBe("100%");
  });

  it("renders without dimensions", () => {
    const { container } = render(<ImageOutput src={src} />);
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    expect(img).not.toHaveAttribute("width");
    expect(img).not.toHaveAttribute("height");
    expect(img).toHaveAttribute("src", src);
  });
});
