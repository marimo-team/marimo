/* Copyright 2026 Marimo. All rights reserved. */

import type { TypedNumber } from "./typed";

export type Milliseconds = TypedNumber<"milliseconds">;

export type Seconds = TypedNumber<"seconds">;

export class Time {
  private readonly ms: Milliseconds;

  static fromMilliseconds(ms: Milliseconds): Time;
  static fromMilliseconds(ms: Milliseconds | null): Time | null;
  static fromMilliseconds(ms: Milliseconds | null): Time | null {
    if (ms == null) {
      return null;
    }
    return new Time(ms);
  }

  static fromSeconds(s: Seconds): Time;
  static fromSeconds(s: Seconds | null): Time | null;
  static fromSeconds(s: Seconds | null): Time | null {
    if (s == null) {
      return null;
    }
    return new Time((s * 1000) as Milliseconds);
  }

  static now(): Time {
    return new Time(Date.now() as Milliseconds);
  }

  private constructor(ms: Milliseconds) {
    this.ms = ms;
  }

  toMilliseconds(): Milliseconds {
    return this.ms;
  }

  toSeconds(): Seconds {
    return (this.ms / 1000) as Seconds;
  }
}

/** Format a duration in milliseconds, e.g. `500ms`, `1.50s`, `1m30s`. */
export function formatElapsedTime(elapsedTime: number | null): string {
  if (elapsedTime === null) {
    return "";
  }

  const milliseconds = elapsedTime;
  const seconds = milliseconds / 1000;

  if (seconds >= 60) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m${remainingSeconds}s`;
  }
  if (seconds >= 1) {
    return `${seconds.toFixed(2).toString()}s`;
  }
  return `${milliseconds.toFixed(0).toString()}ms`;
}
