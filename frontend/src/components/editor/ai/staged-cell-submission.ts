/* Copyright 2026 Marimo. All rights reserved. */

interface SubmissionCallbacks<T> {
  prepare: () => Promise<T>;
  submit: (prepared: T) => Promise<void>;
  onError: (error: unknown) => void;
}

interface SubmissionAttempt {
  cancelled: boolean;
}

/** Coordinates preprocessing and submission without resuming cancelled work. */
export class StagedCellSubmissionController {
  private activeAttempt: SubmissionAttempt | null = null;

  cancel() {
    if (this.activeAttempt) {
      this.activeAttempt.cancelled = true;
    }
  }

  async run<T>({ prepare, submit, onError }: SubmissionCallbacks<T>) {
    if (this.activeAttempt !== null) {
      return;
    }

    const attempt: SubmissionAttempt = { cancelled: false };
    this.activeAttempt = attempt;

    try {
      const prepared = await prepare();
      if (attempt.cancelled) {
        return;
      }

      await submit(prepared);
    } catch (error) {
      if (!attempt.cancelled) {
        onError(error);
      }
    } finally {
      this.activeAttempt = null;
    }
  }
}
