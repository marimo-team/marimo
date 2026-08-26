/* Copyright 2026 Marimo. All rights reserved. */

interface SubmissionCallbacks<T> {
  prepare: () => Promise<T>;
  submit: (prepared: T) => Promise<void>;
  onError: (error: unknown, submissionStarted: boolean) => void;
}

/** Coordinates preprocessing and submission without resuming cancelled work. */
export class StagedCellSubmissionController {
  private activeAttempt: symbol | null = null;

  cancel() {
    this.activeAttempt = null;
  }

  async run<T>({ prepare, submit, onError }: SubmissionCallbacks<T>) {
    if (this.activeAttempt !== null) {
      return;
    }

    const attempt = Symbol("staged-cell-submission");
    this.activeAttempt = attempt;
    let submissionStarted = false;

    try {
      const prepared = await prepare();
      if (this.activeAttempt !== attempt) {
        return;
      }

      submissionStarted = true;
      await submit(prepared);
    } catch (error) {
      if (this.activeAttempt === attempt) {
        onError(error, submissionStarted);
      }
    } finally {
      if (this.activeAttempt === attempt) {
        this.activeAttempt = null;
      }
    }
  }
}
