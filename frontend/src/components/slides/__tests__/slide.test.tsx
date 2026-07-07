/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { CellRuntimeState } from "@/core/cells/types";
import type { OutputMessage } from "@/core/kernel/messages";
import type { Seconds } from "@/utils/time";
import { Slide } from "../slide";

const cellId = "cell-1" as CellId;

const makeOutput = (timestamp: number): OutputMessage => ({
  channel: "output",
  mimetype: "text/plain",
  data: "streaming...",
  timestamp: timestamp as Seconds,
});

type SlideProps = Pick<
  CellRuntimeState,
  "output" | "status" | "interrupted" | "staleInputs" | "runStartTimestamp"
> & { cellId: CellId };

const renderSlide = (props: SlideProps) => render(<Slide {...props} />);

describe("Slide", () => {
  it("does not mark output stale while it is streaming during a run", () => {
    // Output received after the run started must not be greyed out.
    const { container } = renderSlide({
      cellId,
      status: "running",
      output: makeOutput(100),
      runStartTimestamp: 50 as Seconds,
      interrupted: false,
      staleInputs: false,
    });

    expect(container.querySelector(".marimo-output-stale")).toBeNull();
  });

  it("marks output stale when the cell is queued to run", () => {
    const { container } = renderSlide({
      cellId,
      status: "queued",
      output: makeOutput(100),
      runStartTimestamp: null,
      interrupted: false,
      staleInputs: false,
    });

    expect(container.querySelector(".marimo-output-stale")).not.toBeNull();
  });
});
