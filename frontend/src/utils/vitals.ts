/* Copyright 2026 Marimo. All rights reserved. */
import { Logger } from "./Logger";

export async function reportVitals() {
  if (typeof document === "undefined") {
    return;
  }

  const { onLCP, onINP, onCLS } = await import("web-vitals");
  Logger.debug("Reporting vitals");
  const logMetric = (metric: {
    name: string;
    value: number;
    rating: string;
  }) => {
    let color: string;
    if (metric.rating === "good") {
      color = "green";
    } else if (metric.rating === "needs-improvement") {
      color = "orange";
    } else {
      color = "red";
    }
    Logger.log(
      `%c [Metric ${metric.name}] ${metric.value}`,
      `background:${color}; color:white; padding:2px 0; border-radius:2px`,
    );
  };
  onCLS(logMetric);
  onINP(logMetric);
  onLCP(logMetric);
}
