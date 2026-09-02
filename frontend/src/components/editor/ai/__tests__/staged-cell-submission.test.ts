/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { Deferred } from "@/utils/Deferred";
import { StagedCellSubmissionController } from "../staged-cell-submission";

describe("StagedCellSubmissionController", () => {
  it("ignores duplicate submissions while preprocessing", async () => {
    const preparation = new Deferred<string>();
    const submit = vi.fn(async () => undefined);
    const onError = vi.fn();
    const controller = new StagedCellSubmissionController();

    const first = controller.run({
      prepare: () => preparation.promise,
      submit,
      onError,
    });
    await controller.run({
      prepare: vi.fn(async () => "duplicate"),
      submit,
      onError,
    });
    preparation.resolve("prepared");
    await first;

    expect(submit).toHaveBeenCalledExactlyOnceWith("prepared");
    expect(onError).not.toHaveBeenCalled();
  });

  it("does not submit after cancellation during preprocessing", async () => {
    const preparation = new Deferred<string>();
    const submit = vi.fn(async () => undefined);
    const onError = vi.fn();
    const controller = new StagedCellSubmissionController();

    const run = controller.run({
      prepare: () => preparation.promise,
      submit,
      onError,
    });
    controller.cancel();
    preparation.resolve("prepared");
    await run;

    expect(submit).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it("blocks another submission until a cancelled submission settles", async () => {
    const submission = new Deferred<void>();
    const firstSubmit = vi.fn(() => submission.promise);
    const secondSubmit = vi.fn(async () => undefined);
    const onError = vi.fn();
    const controller = new StagedCellSubmissionController();

    const firstRun = controller.run({
      prepare: async () => "first",
      submit: firstSubmit,
      onError,
    });
    await vi.waitFor(() => {
      expect(firstSubmit).toHaveBeenCalledExactlyOnceWith("first");
    });

    controller.cancel();
    await controller.run({
      prepare: async () => "second",
      submit: secondSubmit,
      onError,
    });
    expect(secondSubmit).not.toHaveBeenCalled();

    submission.resolve();
    await firstRun;
    await controller.run({
      prepare: async () => "second",
      submit: secondSubmit,
      onError,
    });

    expect(secondSubmit).toHaveBeenCalledExactlyOnceWith("second");
    expect(onError).not.toHaveBeenCalled();
  });

  it("reports preprocessing and submission errors", async () => {
    const preprocessingError = new Error("preprocessing failed");
    const submissionError = new Error("submission failed");
    const onError = vi.fn();
    const controller = new StagedCellSubmissionController();

    await controller.run({
      prepare: async () => Promise.reject(preprocessingError),
      submit: vi.fn(),
      onError,
    });
    await controller.run({
      prepare: async () => "prepared",
      submit: async () => Promise.reject(submissionError),
      onError,
    });

    expect(onError).toHaveBeenNthCalledWith(1, preprocessingError);
    expect(onError).toHaveBeenNthCalledWith(2, submissionError);
  });
});
