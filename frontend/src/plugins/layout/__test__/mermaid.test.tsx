/* Copyright 2026 Marimo. All rights reserved. */

import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import Mermaid from "../mermaid/mermaid";

// Like mermaid: config is global, renders are queued, and each render reads
// the config when it starts.
const mermaidMock = vi.hoisted(() => {
  let theme: string | undefined;
  let queue: Promise<unknown> = Promise.resolve();
  return {
    initialize: vi.fn((config: { theme?: string }) => {
      theme = config.theme;
    }),
    render: vi.fn((id: string, text: string) => {
      const result = queue.then(async () => {
        const renderedTheme = theme;
        await new Promise((resolve) => setTimeout(resolve, 5));
        return {
          diagramType: text.startsWith("gantt") ? "gantt" : "flowchart-v2",
          svg: `<svg id="${id}" data-theme="${renderedTheme}" data-time="${Date.now()}"><style>#${id} .node {}</style><text>${text}</text></svg>`,
        };
      });
      queue = result.catch(() => undefined);
      return result;
    }),
  };
});

vi.mock("mermaid", () => ({ default: mermaidMock }));

vi.mock("@/theme/useTheme", () => ({
  useTheme: () => ({ theme: "light" }),
}));

// The SVG cache is module-level, so each test uses a distinct diagram.
async function renderSvg(diagram: string, theme?: string) {
  const { container, unmount } = render(
    <Mermaid diagram={diagram} theme={theme} />,
  );
  const svg = await waitFor(() => {
    const el = container.querySelector("svg");
    if (!el) {
      throw new Error("SVG not rendered yet");
    }
    return el;
  });
  return { svg, container, unmount };
}

describe("Mermaid render cache", () => {
  beforeEach(() => {
    mermaidMock.render.mockClear();
  });

  test("re-mounting an unchanged diagram reuses the cached SVG", async () => {
    const first = await renderSvg("graph TD\nA --> B");
    first.unmount();
    const second = await renderSvg("graph TD\nA --> B");

    expect(mermaidMock.render).toHaveBeenCalledTimes(1);
    expect(second.svg.id).toMatch(/^mermaid-[a-z]{12}$/);
    expect(second.svg.id).not.toBe(first.svg.id);
    expect(second.container.innerHTML).toContain(`#${second.svg.id} .node`);
    expect(second.container.innerHTML).not.toContain(first.svg.id);
  });

  test("concurrent mounts of the same diagram render once", async () => {
    const { container } = render(
      <>
        <Mermaid diagram={"graph TD\nC --> D"} />
        <Mermaid diagram={"graph TD\nC --> D"} />
      </>,
    );

    await waitFor(() => {
      expect(container.querySelectorAll("svg")).toHaveLength(2);
    });
    expect(mermaidMock.render).toHaveBeenCalledTimes(1);
    const [a, b] = container.querySelectorAll("svg");
    expect(a.id).not.toBe(b.id);
  });

  test("a different theme is rendered separately", async () => {
    (await renderSvg("graph TD\nE --> F", "forest")).unmount();
    await renderSvg("graph TD\nE --> F", "neutral");

    expect(mermaidMock.render).toHaveBeenCalledTimes(2);
  });

  test("a failed render is not cached", async () => {
    mermaidMock.render.mockRejectedValueOnce(new Error("parse error"));
    const failed = render(<Mermaid diagram={"graph TD\nG -->"} />);
    await waitFor(() => {
      expect(failed.container.textContent).toContain("parse error");
    });
    failed.unmount();

    await renderSvg("graph TD\nG -->");

    expect(mermaidMock.render).toHaveBeenCalledTimes(2);
  });

  test("concurrent diagrams with different themes keep their own theme", async () => {
    const { container } = render(
      <>
        <Mermaid diagram={"graph TD\nH --> I"} theme="forest" />
        <Mermaid diagram={"graph TD\nJ --> K"} theme="neutral" />
      </>,
    );

    await waitFor(() => {
      expect(container.querySelectorAll("svg")).toHaveLength(2);
    });
    const themes = [...container.querySelectorAll("svg")].map((svg) =>
      svg.getAttribute("data-theme"),
    );
    expect(themes).toEqual(["forest", "neutral"]);
  });

  test("Gantt diagrams are re-rendered so the today marker stays current", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    try {
      vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
      (await renderSvg("gantt\n  title Plan")).unmount();

      vi.setSystemTime(new Date("2026-01-02T00:00:00Z"));
      const second = await renderSvg("gantt\n  title Plan");

      expect(mermaidMock.render).toHaveBeenCalledTimes(2);
      expect(second.svg.getAttribute("data-time")).toBe(
        String(Date.parse("2026-01-02T00:00:00Z")),
      );
    } finally {
      vi.useRealTimers();
    }
  });
});
