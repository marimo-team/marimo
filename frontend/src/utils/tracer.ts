/* Copyright 2024 Marimo. All rights reserved. */

/* eslint-disable @typescript-eslint/no-explicit-any */

type SpanStatus = "ok" | "error";

interface Span {
  name: string;
  startTime: number;
  endTime?: number;
  status?: SpanStatus;
  attributes: Record<string, unknown>;
  end: (status?: SpanStatus) => void;
}

/**
 * Extremely simple tracer for measuring performance of code.
 */
export class Tracer {
  private spans: Span[] = [];

  startSpan(name: string, attributes: Record<string, unknown> = {}): Span {
    const span: Span = {
      name,
      startTime: Date.now(),
      attributes,
      end: (status: SpanStatus = "ok") => this.endSpan(span, status),
    };
    this.spans.push(span);
    return span;
  }

  endSpan(span: Span, status: SpanStatus = "ok"): void {
    span.endTime = Date.now();
    span.status = status;
  }

  getSpans(): Span[] {
    return this.spans;
  }

  wrap<T>(
    fn: () => T,
    name?: string,
    attributes: Record<string, unknown> = {},
  ): T {
    const span = this.startSpan(name || fn.name, attributes);
    try {
      const result = fn();
      this.endSpan(span);
      return result;
    } catch (error) {
      this.endSpan(span, "error");
      throw error;
    }
  }

  wrapAsync<T extends (...args: any[]) => Promise<any>>(
    fn: T,
    name?: string,
    attributes: Record<string, unknown> = {},
  ): T {
    return (async (...args) => {
      const span = this.startSpan(name || fn.name, attributes);
      try {
        const result = await fn(...args);
        this.endSpan(span);
        return result;
      } catch (error) {
        this.endSpan(span, "error");
        throw error;
      }
    }) as T;
  }

  logSpans(): void {
    if (process.env.NODE_ENV !== "development") {
      return;
    }

    this.spans.forEach((span) => {
      console.log(`Span: ${span.name}`);
      const childSpans = this.spans.filter(
        (s) =>
          s.startTime > span.startTime &&
          span.endTime &&
          s.startTime < span.endTime,
      );
      if (childSpans.length > 0) {
        console.log("Child Spans:");
        childSpans.forEach((childSpan) => {
          console.log(`  - ${childSpan.name}`);
        });
      }
      console.log(`Start Time: ${new Date(span.startTime).toISOString()}`);
      if (span.endTime) {
        console.log(`End Time: ${new Date(span.endTime).toISOString()}`);
        console.log(`Duration: ${span.endTime - span.startTime}ms`);
      }
      console.log(`Status: ${span.status}`);
      console.log(`Attributes: ${JSON.stringify(span.attributes)}`);
      console.log("---");
    });
  }
}
