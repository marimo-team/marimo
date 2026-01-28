export type ProgressListener = (progress: number | "indeterminate") => void;

export class ProgressState {
  private progress: number = 0;
  private total: number | "indeterminate";
  private listeners: Set<ProgressListener> = new Set();

  constructor(total: number | "indeterminate") {
    this.total = total;
  }

  static indeterminate(): ProgressState {
    return new ProgressState("indeterminate");
  }

  addTotal(total: number) {
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
  increment(increment: number) {
    this.progress += increment;
    this.notifyListeners();
  }

  /**
   * Get the progress as a percentage (0-100)
   */
  getProgress(): number | "indeterminate" {
    if (this.total === "indeterminate") {
      return "indeterminate";
    }
    return (this.progress / this.total) * 100;
  }

  /**
   * Subscribe to progress updates.
   * Returns an unsubscribe function.
   */
  subscribe(listener: ProgressListener): () => void {
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
