/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, waitFor } from "@testing-library/react";
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

  test("updates use temporary IDs separate from the displayed SVG", async () => {
    const view = render(<Mermaid diagram="graph TD; UpdateA --> B" />);
    await waitFor(() =>
      expect(view.container.querySelector("svg")).not.toBeNull(),
    );
    const displayed = view.container.querySelector("svg");
    mermaidMock.render.mockImplementationOnce(async (id) => {
      expect(document.getElementById(id)).toBeNull();
      expect(displayed?.isConnected).toBe(true);
      return {
        diagramType: "flowchart-v2",
        svg: `<svg id="${id}"><text>Updated</text></svg>`,
      };
    });
    view.rerender(<Mermaid diagram="graph TD; UpdateB --> C" />);
    await waitFor(() => expect(view.container.textContent).toBe("Updated"));
    expect(mermaidMock.render).toHaveBeenCalledTimes(2);
  });

  test("shared failures clean up temporary DOM and allow queued work to continue", async () => {
    let temporaryId = "";
    mermaidMock.render.mockImplementationOnce(async (id) => {
      temporaryId = id;
      const wrapper = document.createElement("div");
      wrapper.id = `d${id}`;
      wrapper.innerHTML = `<svg id="${id}"></svg>`;
      document.body.append(wrapper);
      throw new Error("drawing failed");
    });
    const failed = render(
      <>
        <Mermaid diagram="graph TD; SharedFailure" />
        <Mermaid diagram="graph TD; SharedFailure" />
        <Mermaid diagram="graph TD; AfterFailure" />
      </>,
    );
    await waitFor(() => {
      expect(
        failed.container.textContent?.match(/drawing failed/g),
      ).toHaveLength(2);
      expect(failed.container.querySelectorAll("svg")).toHaveLength(1);
    });
    expect(document.getElementById(`d${temporaryId}`)).toBeNull();
    expect(document.getElementById(temporaryId)).toBeNull();
    await renderSvg("graph TD; SharedFailure");
    expect(mermaidMock.render).toHaveBeenCalledTimes(3);
  });

  test("initialization failures do not poison the render queue or cache", async () => {
    mermaidMock.initialize.mockImplementationOnce(() => {
      throw new Error("invalid config");
    });
    const failed = render(<Mermaid diagram="graph TD; InitFailure" />);
    await waitFor(() =>
      expect(failed.container.textContent).toContain("invalid config"),
    );
    failed.unmount();
    await renderSvg("graph TD; InitFailure");
    expect(mermaidMock.render).toHaveBeenCalledTimes(1);
  });

  test("waits for fonts before caching a measured layout", async () => {
    const original = Object.getOwnPropertyDescriptor(document, "fonts");
    const fonts = Promise.withResolvers<undefined>();
    Object.defineProperty(document, "fonts", {
      configurable: true,
      value: { ready: fonts.promise },
    });
    try {
      render(<Mermaid diagram="graph TD; FontLoading" />);
      await act(async () => {
        await Promise.resolve();
      });
      expect(mermaidMock.render).not.toHaveBeenCalled();
      await act(async () => {
        fonts.resolve(undefined);
      });
      await waitFor(() => expect(mermaidMock.render).toHaveBeenCalledTimes(1));
      await renderSvg("graph TD; FontLoading");
      expect(mermaidMock.render).toHaveBeenCalledTimes(1);
    } finally {
      fonts.resolve(undefined);
      if (original) {
        Object.defineProperty(document, "fonts", original);
      } else {
        Reflect.deleteProperty(document, "fonts");
      }
    }
  });

  test("an evicted request failing does not evict its replacement", async () => {
    const pending = Promise.withResolvers<{
      diagramType: string;
      svg: string;
    }>();
    mermaidMock.render.mockImplementationOnce(() => pending.promise);
    const first = render(<Mermaid diagram="graph TD; EvictedFailure" />);
    await waitFor(() => expect(mermaidMock.render).toHaveBeenCalledTimes(1));
    const rest = render(
      <>
        {Array.from({ length: 64 }, (_, i) => (
          <Mermaid key={i} diagram={`graph TD; Eviction${i}`} />
        ))}
        <Mermaid diagram="graph TD; EvictedFailure" />
      </>,
    );
    await act(async () => {
      pending.reject(new Error("evicted render failed"));
    });
    await waitFor(() =>
      expect(rest.container.querySelectorAll("svg")).toHaveLength(65),
    );
    first.unmount();
    await renderSvg("graph TD; EvictedFailure");
    expect(mermaidMock.render).toHaveBeenCalledTimes(66);
  });
});
