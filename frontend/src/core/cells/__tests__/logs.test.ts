/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellMessage } from "../../kernel/messages";
import { formatLogTimestamp, getCellLogsForMessage } from "../logs";

// Stable mock reference so every (re)import of use-toast sees the same spy,
// even after vi.resetModules() clears the module cache between tests.
const { toastMock } = vi.hoisted(() => ({ toastMock: vi.fn() }));
vi.mock("@/components/ui/use-toast", () => ({ toast: toastMock }));

describe("getCellLogsForMessage", () => {
  beforeEach(() => {
    // Mock console.log to avoid cluttering test output
    vi.spyOn(console, "log").mockImplementation(() => {
      // no-op
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("handles text/plain MIME type on stdout", () => {
    const cellMessage: CellMessage = {
      cell_id: cellId("cell-1"),
      console: [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Hello, World!",
          timestamp: 1_234_567_890,
        },
      ],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(1);
    expect(logs[0]).toEqual({
      timestamp: 1_234_567_890,
      level: "stdout",
      message: "Hello, World!",
      cellId: "cell-1",
    });
  });

  test("handles text/plain MIME type on stderr", () => {
    const cellMessage: CellMessage = {
      cell_id: cellId("cell-2"),
      console: [
        {
          mimetype: "text/plain",
          channel: "stderr",
          data: "Error occurred",
          timestamp: 1_234_567_890,
        },
      ],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(1);
    expect(logs[0]).toEqual({
      timestamp: 1_234_567_890,
      level: "stderr",
      message: "Error occurred",
      cellId: "cell-2",
    });
  });

  test("handles text/html MIME type and strips HTML tags", () => {
    const cellMessage: CellMessage = {
      cell_id: cellId("cell-3"),
      console: [
        {
          mimetype: "text/html",
          channel: "stdout",
          data: '<span style="color: red;">Error: Something went wrong</span>',
          timestamp: 1_234_567_890,
        },
      ],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(1);
    expect(logs[0]).toEqual({
      timestamp: 1_234_567_890,
      level: "stdout",
      message: "Error: Something went wrong",
      cellId: "cell-3",
    });
  });

  test("handles text/html MIME type on stderr", () => {
    const cellMessage: CellMessage = {
      cell_id: cellId("cell-4"),
      console: [
        {
          mimetype: "text/html",
          channel: "stderr",
          data: "<div><strong>Critical Error:</strong> System failure</div>",
          timestamp: 1_234_567_890,
        },
      ],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(1);
    expect(logs[0]).toEqual({
      timestamp: 1_234_567_890,
      level: "stderr",
      message: "Critical Error: System failure",
      cellId: "cell-4",
    });
  });

  test("handles application/vnd.marimo+traceback MIME type and strips HTML", () => {
    const cellMessage: CellMessage = {
      cell_id: cellId("cell-5"),
      console: [
        {
          mimetype: "application/vnd.marimo+traceback",
          channel: "marimo-error",
          data: '<div class="traceback"><span style="color: red;">Traceback (most recent call last):</span><pre>  File "test.py", line 1</pre></div>',
          timestamp: 1_234_567_890,
        },
      ],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(1);
    expect(logs[0].level).toBe("stderr"); // marimo-error should be treated as stderr
    expect(logs[0].message).toContain("Traceback (most recent call last):");
    expect(logs[0].message).toContain('File "test.py", line 1');
    expect(logs[0].cellId).toBe("cell-5");
  });

  test("handles multiple console outputs with different MIME types", () => {
    const cellMessage: CellMessage = {
      cell_id: cellId("cell-7"),
      console: [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Plain text output",
          timestamp: 1_234_567_890,
        },
        {
          mimetype: "text/html",
          channel: "stdout",
          data: "<span>HTML output</span>",
          timestamp: 1_234_567_891,
        },
        {
          mimetype: "application/vnd.marimo+traceback",
          channel: "stderr",
          data: "<div>Traceback error</div>",
          timestamp: 1_234_567_892,
        },
      ],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(3);
    expect(logs[0].message).toBe("Plain text output");
    expect(logs[1].message).toBe("HTML output");
    expect(logs[2].message).toBe("Traceback error");
  });

  test("uses Date.now() when timestamp is missing", () => {
    const now = Date.now();
    vi.spyOn(Date, "now").mockReturnValue(now);

    const cellMessage: CellMessage = {
      cell_id: cellId("cell-8"),
      console: [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "No timestamp",
          // timestamp is undefined
        },
      ],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(1);
    expect(logs[0].timestamp).toBe(now);
  });

  test("ignores unsupported MIME types", () => {
    const cellMessage: CellMessage = {
      cell_id: cellId("cell-9"),
      console: [
        {
          mimetype: "application/json",
          channel: "stdout",
          data: '{"key": "value"}',
          timestamp: 1_234_567_890,
        },
      ],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(0);
  });

  test("ignores non-logging channels", () => {
    const cellMessage: CellMessage = {
      cell_id: cellId("cell-10"),
      console: [
        {
          mimetype: "text/plain",
          channel: "pdb" as unknown as "stdout", // Non-logging channel
          data: "Should be ignored",
          timestamp: 1_234_567_890,
        },
      ],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(0);
  });

  test("returns empty array when console is null", () => {
    const cellMessage: CellMessage = {
      cell_id: cellId("cell-11"),
      console: null as unknown as CellMessage["console"],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(0);
  });

  test("handles complex HTML with nested elements in text/html", () => {
    const cellMessage: CellMessage = {
      cell_id: cellId("cell-12"),
      console: [
        {
          mimetype: "text/html",
          channel: "stdout",
          data: "<div><span>Nested</span> <strong>HTML</strong> <em>content</em></div>",
          timestamp: 1_234_567_890,
        },
      ],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(1);
    expect(logs[0].message).toBe("Nested HTML content");
  });

  test("handles marimo-error channel as stderr level", () => {
    const cellMessage: CellMessage = {
      cell_id: cellId("cell-13"),
      console: [
        {
          mimetype: "text/plain",
          channel: "marimo-error",
          data: "Internal error",
          timestamp: 1_234_567_890,
        },
      ],
      output: null,
      status: "idle",
      stale_inputs: null,
      timestamp: 0,
    };

    const logs = getCellLogsForMessage(cellMessage);

    expect(logs).toHaveLength(1);
    expect(logs[0].level).toBe("stderr");
  });
});

describe("getCellLogsForMessage - internal error toast", () => {
  // Re-imported per test after vi.resetModules() so the module-level
  // `didAlreadyToastError` flag starts fresh and all jotai atom references
  // (initialModeAtom, etc.) match the versions used by the reset logs.ts.
  let getLogs: typeof import("../logs").getCellLogsForMessage;
  let store: typeof import("@/core/state/jotai").store;
  let initialModeAtom: typeof import("@/core/mode").initialModeAtom;

  beforeEach(async () => {
    vi.spyOn(console, "log").mockImplementation(() => {
      // no-op
    });
    vi.resetModules();
    ({ getCellLogsForMessage: getLogs } = await import("../logs"));
    ({ store } = await import("@/core/state/jotai"));
    ({ initialModeAtom } = await import("@/core/mode"));
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  const makeErrorCellMessage = (id: CellMessage["cell_id"]): CellMessage => ({
    cell_id: id,
    console: [],
    output: {
      mimetype: "application/vnd.marimo+error",
      data: [
        {
          type: "exception",
          exception_type: "ValueError",
          msg: "something exploded",
          traceback: ["File foo.py, line 1", "ValueError: something exploded"],
        },
      ],
      channel: "marimo-error",
      timestamp: 0,
    } as unknown as CellMessage["output"],
    status: "idle",
    stale_inputs: null,
    timestamp: 0,
  });

  test("shows toast for internal errors in app (read) mode", () => {
    store.set(initialModeAtom, "read");

    getLogs(makeErrorCellMessage(cellId("cell-err-1")));

    expect(toastMock).toHaveBeenCalledTimes(1);
    expect(toastMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "An internal error occurred",
        variant: "danger",
      }),
    );
  });

  test("does not show toast for internal errors in edit mode", () => {
    store.set(initialModeAtom, "edit");

    getLogs(makeErrorCellMessage(cellId("cell-err-2")));

    expect(toastMock).not.toHaveBeenCalled();
  });

  test("edit-mode errors do not consume the once-per-session toast slot", () => {
    // Errors received while in edit mode should be silently skipped...
    store.set(initialModeAtom, "edit");
    getLogs(makeErrorCellMessage(cellId("cell-err-3")));
    expect(toastMock).not.toHaveBeenCalled();

    // ...and a subsequent error in app mode should still toast.
    store.set(initialModeAtom, "read");
    getLogs(makeErrorCellMessage(cellId("cell-err-4")));
    expect(toastMock).toHaveBeenCalledTimes(1);
  });

  test("toast only fires once across multiple app-mode errors", () => {
    store.set(initialModeAtom, "read");

    getLogs(makeErrorCellMessage(cellId("cell-err-5")));
    getLogs(makeErrorCellMessage(cellId("cell-err-6")));

    expect(toastMock).toHaveBeenCalledTimes(1);
  });

  test("suppresses toast when initial mode has not been set", () => {
    // Leave initialModeAtom at its default (undefined); getInitialAppMode
    // will throw and the logic should swallow it without toasting.
    getLogs(makeErrorCellMessage(cellId("cell-err-7")));

    expect(toastMock).not.toHaveBeenCalled();
  });
});

describe("formatLogTimestamp", () => {
  test("formats unix timestamp correctly", () => {
    // January 1, 2024, 12:00:00 PM UTC
    const timestamp = 1_704_110_400;
    const result = formatLogTimestamp(timestamp);

    // The result depends on the timezone, so we just check it's not empty
    // and contains expected time format elements
    expect(result).toBeTruthy();
    expect(result).toMatch(/\d+:\d+:\d+/); // Should contain time format
  });

  test("formats timestamp with AM/PM notation", () => {
    const timestamp = 1_704_110_400; // Noon
    const result = formatLogTimestamp(timestamp);

    // Should contain AM or PM
    expect(result).toMatch(/AM|PM/);
  });

  test("returns 'Invalid Date' for invalid timestamp", () => {
    const invalidTimestamp = Number.NaN;
    const result = formatLogTimestamp(invalidTimestamp);

    expect(result).toBe("Invalid Date");
  });

  test("handles edge case: zero timestamp", () => {
    const timestamp = 0; // Unix epoch
    const result = formatLogTimestamp(timestamp);

    // Should format successfully (Jan 1, 1970)
    expect(result).toBeTruthy();
    expect(result).toMatch(/\d+:\d+:\d+/);
  });

  test("handles recent timestamp", () => {
    // Use a recent timestamp (seconds since epoch)
    const timestamp = Math.floor(Date.now() / 1000);
    const result = formatLogTimestamp(timestamp);

    expect(result).toBeTruthy();
    expect(result).toMatch(/\d+:\d+:\d+/);
    expect(result).toMatch(/AM|PM/);
  });
});
