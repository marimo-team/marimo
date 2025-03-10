/* Copyright 2024 Marimo. All rights reserved. */
import {
  CellStatusComponent,
  ElapsedTime,
  formatElapsedTime,
} from "../components/editor/cell/CellStatus";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render } from "@testing-library/react";
import type { Seconds } from "@/utils/time";
import { TooltipProvider } from "@/components/ui/tooltip";

// Mock date-fns to have consistent date formatting in tests
vi.mock("date-fns", () => ({
  formatDistanceToNow: () => "5 minutes",
}));

describe("formatElapsedTime", () => {
  test("formats milliseconds correctly", () => {
    expect(formatElapsedTime(500)).toBe("500ms");
    expect(formatElapsedTime(50)).toBe("50ms");
  });

  test("formats seconds correctly", () => {
    expect(formatElapsedTime(1500)).toBe("1.50s");
    expect(formatElapsedTime(2340)).toBe("2.34s");
  });

  test("formats minutes and seconds correctly", () => {
    expect(formatElapsedTime(60 * 1000)).toBe("1m0s");
    expect(formatElapsedTime(90 * 1000)).toBe("1m30s");
    expect(formatElapsedTime(89 * 1000)).toBe("1m29s");
    expect(formatElapsedTime(91 * 1000)).toBe("1m31s");
    expect(formatElapsedTime(150 * 1000)).toBe("2m30s");
    expect(formatElapsedTime(151 * 1000)).toBe("2m31s");
  });

  test("handles null input", () => {
    expect(formatElapsedTime(null)).toBe("");
  });
});

describe("ElapsedTime component", () => {
  test("renders elapsed time correctly", () => {
    const { container } = render(
      <TooltipProvider>
        <ElapsedTime elapsedTime="1.50s" />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });
});

describe("CellStatusComponent", () => {
  // Mock date for consistent testing
  const mockDate = new Date(2024, 0, 1, 12, 0, 0);
  const originalDate = global.Date;

  beforeEach(() => {
    global.Date = class extends Date {
      static override now() {
        return mockDate.getTime();
      }
    } as typeof Date;
  });

  afterEach(() => {
    global.Date = originalDate;
  });

  // Base props that will be modified for different test cases
  const baseProps = {
    editing: true,
    edited: false,
    disabled: false,
    staleInputs: false,
    status: "idle" as const,
    interrupted: false,
    elapsedTime: null,
    runStartTimestamp: null,
    lastRunStartTimestamp: null,
    uninstantiated: false,
  };

  test("returns null when not editing", () => {
    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...baseProps} editing={false} />
      </TooltipProvider>,
    );
    expect(container.firstChild).toBeNull();
  });

  test("renders disabled and stale state", () => {
    const props = {
      ...baseProps,
      disabled: true,
      staleInputs: true,
      lastRunStartTimestamp: 1_704_096_000 as Seconds, // Jan 1, 2024 12:00:00
    };

    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...props} />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });

  test("renders disabled state", () => {
    const props = {
      ...baseProps,
      disabled: true,
      lastRunStartTimestamp: 1_704_096_000 as Seconds,
    };

    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...props} />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });

  test("renders disabled transitively state", () => {
    const props = {
      ...baseProps,
      status: "disabled-transitively" as const,
      lastRunStartTimestamp: 1_704_096_000 as Seconds,
    };

    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...props} />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });

  test("renders stale and disabled transitively state", () => {
    const props = {
      ...baseProps,
      status: "disabled-transitively" as const,
      staleInputs: true,
      lastRunStartTimestamp: 1_704_096_000 as Seconds,
    };

    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...props} />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });

  test("renders running state", () => {
    const props = {
      ...baseProps,
      status: "running" as const,
      runStartTimestamp: 1_704_096_000 as Seconds,
      lastRunStartTimestamp: 1_704_096_000 as Seconds,
    };

    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...props} />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });

  test("renders queued state", () => {
    const props = {
      ...baseProps,
      status: "queued" as const,
      lastRunStartTimestamp: 1_704_096_000 as Seconds,
    };

    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...props} />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });

  test("renders uninstantiated state", () => {
    const props = {
      ...baseProps,
      uninstantiated: true,
    };

    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...props} />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });

  test("renders interrupted state", () => {
    const props = {
      ...baseProps,
      interrupted: true,
      elapsedTime: 1500,
      lastRunStartTimestamp: 1_704_096_000 as Seconds,
    };

    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...props} />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });

  test("renders edited state", () => {
    const props = {
      ...baseProps,
      edited: true,
      elapsedTime: 1500,
      lastRunStartTimestamp: 1_704_096_000 as Seconds,
    };

    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...props} />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });

  test("renders stale inputs state", () => {
    const props = {
      ...baseProps,
      staleInputs: true,
      elapsedTime: 1500,
      lastRunStartTimestamp: 1_704_096_000 as Seconds,
    };

    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...props} />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });

  test("renders completed run with elapsed time", () => {
    const props = {
      ...baseProps,
      elapsedTime: 1500,
      lastRunStartTimestamp: 1_704_096_000 as Seconds,
    };

    const { container } = render(
      <TooltipProvider>
        <CellStatusComponent {...props} />
      </TooltipProvider>,
    );
    expect(container).toMatchSnapshot();
  });
});
