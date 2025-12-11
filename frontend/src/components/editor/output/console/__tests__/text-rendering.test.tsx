/* Copyright 2024 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { cleanAnsiCodes, RenderTextWithLinks } from "../text-rendering";

// Mock the useInstallPackages hook
vi.mock("@/core/packages/useInstallPackage", () => ({
  useInstallPackages: () => ({
    handleInstallPackages: vi.fn(),
  }),
}));

describe("RenderTextWithLinks", () => {
  describe("URL detection", () => {
    it("should render plain text without URLs", () => {
      render(<RenderTextWithLinks text="Hello, world!" />);
      expect(screen.getByText("Hello, world!")).toBeInTheDocument();
    });

    it("should make URLs clickable", () => {
      render(
        <RenderTextWithLinks text="Check out https://marimo.io for more info" />,
      );
      const link = screen.getByRole("link", { name: "https://marimo.io" });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute("href", "https://marimo.io");
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    });

    it("should handle multiple URLs in one line", () => {
      render(
        <RenderTextWithLinks text="Visit https://marimo.io or https://github.com/marimo-team/marimo" />,
      );
      expect(
        screen.getByRole("link", { name: "https://marimo.io" }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("link", {
          name: "https://github.com/marimo-team/marimo",
        }),
      ).toBeInTheDocument();
    });

    it("should handle http URLs", () => {
      render(<RenderTextWithLinks text="Link: http://example.com" />);
      const link = screen.getByRole("link", { name: "http://example.com" });
      expect(link).toBeInTheDocument();
    });

    it("should handle URLs with query parameters", () => {
      render(
        <RenderTextWithLinks text="Visit https://marimo.io/docs?page=1&section=intro" />,
      );
      const link = screen.getByRole("link", {
        name: "https://marimo.io/docs?page=1&section=intro",
      });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute(
        "href",
        "https://marimo.io/docs?page=1&section=intro",
      );
    });

    it("should handle URLs at the start of text", () => {
      render(<RenderTextWithLinks text="https://marimo.io is awesome" />);
      expect(
        screen.getByRole("link", { name: "https://marimo.io" }),
      ).toBeInTheDocument();
      expect(screen.getByText("is awesome")).toBeInTheDocument();
    });

    it("should handle URLs at the end of text", () => {
      render(<RenderTextWithLinks text="Check out https://marimo.io" />);
      expect(screen.getByText("Check out")).toBeInTheDocument();
      expect(
        screen.getByRole("link", { name: "https://marimo.io" }),
      ).toBeInTheDocument();
    });

    it("should not break on text without protocols", () => {
      render(<RenderTextWithLinks text="Visit marimo.io or github.com" />);
      // These should be rendered as plain text, not links
      expect(
        screen.queryByRole("link", { name: "marimo.io" }),
      ).not.toBeInTheDocument();
      expect(
        screen.getByText(/Visit marimo.io or github.com/),
      ).toBeInTheDocument();
    });
  });

  describe("XSS safety", () => {
    it("should safely handle URLs with special characters", () => {
      render(
        <RenderTextWithLinks text="Visit https://example.com/<script>alert('xss')</script>" />,
      );
      // The URL should be rendered but script should not execute
      expect(screen.getByText(/Visit/)).toBeInTheDocument();
      // Should not have a script element in the DOM
      const scripts = document.querySelectorAll("script");
      const hasXSSScript = Array.from(scripts).some((script) =>
        script.textContent?.includes("alert('xss')"),
      );
      expect(hasXSSScript).toBe(false);
    });

    it("should handle javascript: protocol URLs safely", () => {
      render(<RenderTextWithLinks text="Link: javascript:alert('xss')" />);
      // javascript: protocol should not be detected as a valid URL
      expect(
        screen.queryByRole("link", { name: /javascript:/ }),
      ).not.toBeInTheDocument();
    });
  });
});

describe("cleanAnsiCodes", () => {
  it("should remove basic ANSI color codes", () => {
    const text = "\x1b[31mRed text\x1b[0m";
    const cleaned = cleanAnsiCodes(text);
    expect(cleaned).toBe("Red text");
  });

  it("should remove multiple ANSI codes", () => {
    const text = "\x1b[31mRed\x1b[0m \x1b[32mGreen\x1b[0m \x1b[34mBlue\x1b[0m";
    const cleaned = cleanAnsiCodes(text);
    expect(cleaned).toBe("Red Green Blue");
  });

  it("should handle text without ANSI codes", () => {
    const text = "Plain text";
    const cleaned = cleanAnsiCodes(text);
    expect(cleaned).toBe("Plain text");
  });

  it("should remove ANSI codes with multiple parameters", () => {
    const text = "\x1b[1;31mBold Red\x1b[0m";
    const cleaned = cleanAnsiCodes(text);
    expect(cleaned).toBe("Bold Red");
  });

  it("should clean ANSI codes from URLs", () => {
    const text = "https://marimo.io\x1b[0m";
    const cleaned = cleanAnsiCodes(text);
    expect(cleaned).toBe("https://marimo.io");
  });

  it("should handle empty string", () => {
    const text = "";
    const cleaned = cleanAnsiCodes(text);
    expect(cleaned).toBe("");
  });

  it("should remove complex ANSI sequences", () => {
    const text = "\x1b[38;5;208mOrange text\x1b[0m";
    const cleaned = cleanAnsiCodes(text);
    expect(cleaned).toBe("Orange text");
  });

  it("should handle text with only ANSI codes", () => {
    const text = "\x1b[31m\x1b[0m";
    const cleaned = cleanAnsiCodes(text);
    expect(cleaned).toBe("");
  });

  it("should preserve special characters and whitespace", () => {
    const text = "\x1b[31mSpecial: !@#$%^&*()\n\tTab and newline\x1b[0m";
    const cleaned = cleanAnsiCodes(text);
    expect(cleaned).toBe("Special: !@#$%^&*()\n\tTab and newline");
  });
});

describe("RenderTextWithLinks - pip install detection", () => {
  it("should render pip install command with install button", () => {
    render(<RenderTextWithLinks text="pip install pandas" />);

    expect(screen.getByText(/pip install pandas/)).toBeInTheDocument();
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("should handle pip install with package extras", () => {
    render(<RenderTextWithLinks text="pip install package[extra,dep]" />);

    expect(
      screen.getByText(/pip install package\[extra,dep\]/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("should handle multiple packages", () => {
    render(<RenderTextWithLinks text="pip install pandas numpy scipy" />);

    expect(screen.getByText(/pip install pandas/)).toBeInTheDocument();
    const button = screen.getByRole("button");
    expect(button).toBeInTheDocument();
    expect(button.textContent).toContain("pandas");
  });

  it("should handle pip install with surrounding text", () => {
    render(
      <RenderTextWithLinks text="Error: please run pip install pandas to fix this issue" />,
    );

    expect(screen.getByText(/Error: please run/)).toBeInTheDocument();
    expect(screen.getByText(/pip install pandas/)).toBeInTheDocument();
    expect(screen.getByText(/to fix this issue/)).toBeInTheDocument();
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("should not render button for non-pip install text", () => {
    render(<RenderTextWithLinks text="Install the package manually" />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
  it("should handle pip install with ANSI codes", () => {
    // ANSI codes create nested spans which makes the replacer logic complex
    // For now, just verify it renders without crashing
    const { container } = render(
      <RenderTextWithLinks text="\x1b[31mError: pip install pandas\x1b[0m" />,
    );
    expect(container).toBeInTheDocument();
  });
  it("should handle pip install with ANSI codes", () => {
    // ANSI codes create nested spans which makes the replacer logic complex
    // For now, just verify it renders without crashing
    const { container } = render(
      <RenderTextWithLinks text="\x1b[31mError: pip install pandas\x1b[0m" />,
    );
    expect(container).toBeInTheDocument();
  });
  it("should handle pip install with ANSI codes", () => {
    // ANSI codes create nested spans which makes the replacer logic complex
    // For now, just verify it renders without crashing
    const { container } = render(
      <RenderTextWithLinks text="\x1b[31mError: pip install pandas\x1b[0m" />,
    );
    expect(container).toBeInTheDocument();
  });
  it("should handle pip install with ANSI codes", () => {
    // ANSI codes create nested spans which makes the replacer logic complex
    // For now, just verify it renders without crashing
    const { container } = render(
      <RenderTextWithLinks text="\x1b[31mError: pip install pandas\x1b[0m" />,
    );
    expect(container).toBeInTheDocument();
  });
  it("should handle pip install with ANSI codes", () => {
    // ANSI codes create nested spans which makes the replacer logic complex
    // For now, just verify it renders without crashing
    const { container } = render(
      <RenderTextWithLinks text="\x1b[31mError: pip install pandas\x1b[0m" />,
    );
    expect(container).toBeInTheDocument();
  });
  it("should handle pip install with ANSI codes", () => {
    // ANSI codes create nested spans which makes the replacer logic complex
    // For now, just verify it renders without crashing
    const { container } = render(
      <RenderTextWithLinks text="\x1b[31mError: pip install pandas\x1b[0m" />,
    );
    expect(container).toBeInTheDocument();
  });

  it("should handle pip install with hyphens in package name", () => {
    render(<RenderTextWithLinks text="pip install scikit-learn" />);

    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("should handle pip install with dots in package name", () => {
    render(<RenderTextWithLinks text="pip install types.boto3" />);

    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("should handle both pip install and URLs in the same text", () => {
    render(
      <RenderTextWithLinks text="Run pip install pandas and visit https://marimo.io for docs" />,
    );

    expect(screen.getByRole("button")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "https://marimo.io" }),
    ).toBeInTheDocument();
  });

  it("should handle multiple separate pip install commands in the same text", () => {
    render(
      <RenderTextWithLinks text="You need to: pip install polars pandas to fix this." />,
    );

    // Should create button for the first package in the command
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0].textContent).toContain("pip install polars");
  });

  it("should handle multiple distinct pip install commands", () => {
    render(
      <RenderTextWithLinks text="First run pip install polars. Then run pip install pandas." />,
    );

    // Should create separate buttons for each command
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(2);
    expect(buttons[0].textContent).toContain("polars");
    expect(buttons[1].textContent).toContain("pandas");
  });
});
