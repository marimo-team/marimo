/* Copyright 2026 Marimo. All rights reserved. */
export type ProgressListener = (progress: number | "indeterminate") => void;

export class ProgressState {
  private progress = 0;
  private total: number | "indeterminate";
  private listeners = new Set<ProgressListener>();

  public constructor(total: number | "indeterminate") {
    this.total = total;
  }

  public static indeterminate(): ProgressState {
    return new ProgressState("indeterminate");
  }

  public addTotal(total: number) {
    if (this.total === "indeterminate") {
      this.total = total;
    } else {
      this.total += total;
    }
    this.notifyListeners();
  }

  /**
   * Update the progress by the given increment.
   */
  public increment(increment: number) {
    this.progress += increment;
    this.notifyListeners();
  }

  /**
   * Get the progress as a percentage (0-100)
   */
  public getProgress(): number | "indeterminate" {
    if (this.total === "indeterminate") {
      return "indeterminate";
    }
    return (this.progress / this.total) * 100;
  }

  /**
   * Subscribe to progress updates.
   * Returns an unsubscribe function.
   */
  public subscribe(listener: ProgressListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notifyListeners() {
    const progress = this.getProgress();
    for (const listener of this.listeners) {
      listener(progress);
    }
  }
}
