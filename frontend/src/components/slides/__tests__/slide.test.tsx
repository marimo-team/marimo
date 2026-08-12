/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { OutputMessage } from "@/core/kernel/messages";
import type { Seconds } from "@/utils/time";
import { Slide } from "../slide";

const cellId = "cell-1" as CellId;

const output: OutputMessage = {
  channel: "output",
  mimetype: "text/plain",
  data: "hello",
  timestamp: 0 as Seconds,
};

describe("Slide", () => {
  it("does not grey out the output when stale is false", () => {
    const { container } = render(
      <Slide cellId={cellId} status="running" output={output} stale={false} />,
    );
    expect(container.querySelector(".marimo-output-stale")).toBeNull();
  });

  it("greys out the output when stale is true", () => {
    const { container } = render(
      <Slide cellId={cellId} status="queued" output={output} stale={true} />,
    );
    expect(container.querySelector(".marimo-output-stale")).not.toBeNull();
  });
});
