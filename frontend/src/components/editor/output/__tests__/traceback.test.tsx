/* Copyright 2024 Marimo. All rights reserved. */
import {
  MarimoTracebackOutput,
  replaceTracebackPrefix,
  replaceTracebackFilenames,
} from "../MarimoTracebackOutput";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { Tracebacks } from "@/__mocks__/tracebacks";
import { render } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import type { CellId } from "@/core/cells/ids";
import { TooltipProvider } from "@/components/ui/tooltip";

const cellId = "1" as CellId;

describe("traceback component", () => {
  test("extracts cell-link", () => {
    const traceback = (
      <TooltipProvider>
        <MarimoTracebackOutput traceback={Tracebacks.raw} cellId={cellId} />
      </TooltipProvider>
    );
    const { unmount, getAllByRole } = render(traceback);

    // Has traceback links
    expect(getAllByRole("link")).toHaveLength(2);
    // Check that the traceback links are parsed
    expect(getAllByRole("link")[0].textContent).toContain(
      "marimo://untitled#cell=",
    );
    expect(getAllByRole("link")[1].textContent).toContain(
      "marimo://untitled#cell=",
    );
    unmount();
  });

  test("renames File to Cell for relevant lines", () => {
    const traceback = (
      <TooltipProvider>
        <MarimoTracebackOutput traceback={Tracebacks.raw} cellId={cellId} />
      </TooltipProvider>
    );
    const { unmount, container } = render(traceback);

    expect(container).not.toBeNull();

    expect(Tracebacks.raw).not.toMatch(/Cell/);
    expect(container.textContent).toMatch(/Cell/);
    expect(Tracebacks.raw.match(/File/g)).toHaveLength(3);
    expect(container?.textContent?.match(/File/g)).toHaveLength(1);
    unmount();
  });
});

describe("traceback replacement", () => {
  test("replaces File with Cell", () => {
    const traceback = renderHTML({
      html: Tracebacks.assertion,
      additionalReplacements: [replaceTracebackPrefix],
    });
    const { unmount, container } = render(
      <TooltipProvider>{traceback}</TooltipProvider>,
    );

    expect(container).not.toBeNull();

    expect(Tracebacks.assertion).not.toMatch(/Cell/);
    expect(container.textContent).toMatch(/Cell/);
    expect(Tracebacks.assertion.match(/File/g)).toHaveLength(3);
    // Only replaces the relevant File to Cell
    expect(container?.textContent?.match(/File/g)).toHaveLength(2);
    unmount();
  });

  test("renames filenames", () => {
    const traceback = renderHTML({
      html: Tracebacks.assertion,
      additionalReplacements: [replaceTracebackFilenames],
    });
    const { unmount, getAllByRole, container } = render(
      <TooltipProvider>{traceback}</TooltipProvider>,
    );

    expect(container).not.toBeNull();

    // Has just traceback links
    expect(getAllByRole("link")).toHaveLength(1);
    // Check that the traceback links are parsed
    expect(getAllByRole("link")[0].textContent).toContain(
      "marimo://untitled#cell=",
    );

    expect(Tracebacks.assertion.match(/__marimo__cell_Hbol_/g)).toHaveLength(2);
    // Still contains the string of the filename in the trace
    expect(container?.textContent?.match(/__marimo__cell_Hbol_/g)).toHaveLength(
      1,
    );
    unmount();
  });
});
