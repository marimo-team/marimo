/* Copyright 2024 Marimo. All rights reserved. */

export type Milliseconds = number & { __type__: "milliseconds" };

export type Seconds = number & { __type__: "seconds" };

export class Time {
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

  private constructor(private readonly ms: Milliseconds) {}

  toMilliseconds(): Milliseconds {
    return this.ms;
  }

  toSeconds(): Seconds {
    return (this.ms / 1000) as Seconds;
  }
}
